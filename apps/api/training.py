import json
import re
import shutil
import subprocess
import time
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from apps.api.auth import audit, editor, language, owner, principal, scoped
from apps.api.config import settings
from apps.api.db import Session, now, session
from apps.api.models import Dataset, Deployment, Identity, ModelRecord, RunEvent, Source, TrainingRun
from apps.api.schemas import TrainCreate
from apps.api.serialization import serialize
from apps.api.storage import store
from apps.worker.jobs import environment

router = APIRouter(tags=["Training & registry"])
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}


def resolve_plan(body, dataset):
    config = body.hyperparameters.model_dump()
    expected = {
        "embeddings": "contrastive",
        "language-identification": "char-ngram",
        "dictionary-adapter": "lora",
    }[body.task]
    if body.strategy not in {"auto", expected}:
        raise HTTPException(422, "Strategy is incompatible with task")
    config["strategy"] = expected
    # Default CPU works on every deployment. Engineers opt into GPU on GPU-equipped workers.
    config["device"] = "cpu" if config["device"] == "auto" else config["device"]
    config["batch_size"] = config["batch_size"] or (8 if config["device"] == "cpu" else 32)
    config["epochs"] = config["epochs"] or (4 if dataset.entry_count < 1000 else 6)
    config["learning_rate"] = config["learning_rate"] or (2e-5 if body.task == "embeddings" else 2e-4)
    base = body.base_model
    revision = body.base_model_revision
    if body.task == "language-identification":
        base, revision = "scikit-learn/char-ngram", "1"
    elif base == "test-tiny":
        if not settings().allow_test_encoder or body.task != "embeddings":
            raise HTTPException(422, "Test encoder is disabled")
        revision = "1"
    else:
        if body.task == "dictionary-adapter" and not settings().enable_experimental:
            raise HTTPException(403, "Experimental adapters are disabled by the deployment owner")
        if base == "auto":
            base = settings().base_model if body.task == "embeddings" else settings().generative_model
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", base):
            raise HTTPException(422, "Base model must be an explicit Hugging Face repository ID")
        revision = settings().model_revision if revision == "auto" else revision
        try:
            if settings().local_files_only:
                from huggingface_hub import snapshot_download
                from pathlib import Path

                revision = Path(
                    snapshot_download(
                        base, revision=None if revision == "auto" else revision, local_files_only=True
                    )
                ).name
            else:
                from huggingface_hub import HfApi

                revision = (
                    HfApi()
                    .model_info(base, revision=None if revision == "auto" else revision, timeout=15)
                    .sha
                )
        except Exception:
            raise HTTPException(
                422, "Cannot resolve base model revision. Pre-download it or check repository access."
            )
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise HTTPException(422, "A pinned 40-character model commit is required")
    return base, revision, config


@router.post("/languages/{language_id}/training-runs", status_code=202)
def train(language_id: str, body: TrainCreate, user=Depends(editor), db=Depends(session)):
    lang = language(db, language_id, user)
    dataset = scoped(db, Dataset, body.dataset_id, user)
    if dataset.language_id != lang.id:
        raise HTTPException(422, "Dataset belongs to another language")
    if not all(g["training_allowed"] for g in dataset.governance):
        raise HTTPException(403, "Training permission required")
    snapshot = store().json(dataset.object_key, dataset.sha256)
    if body.task == "language-identification" and not snapshot["negative_corpus"]:
        raise HTTPException(
            422, "Configure an explicitly approved negative corpus before training language identification"
        )
    if body.task == "embeddings" and not any(
        s["label"] == 0 and s["split"] == "train" for s in snapshot["views"]["semantic"]
    ):
        raise HTTPException(422, "Need at least two unrelated training concepts after grouping")
    base, revision, config = resolve_plan(body, dataset)
    commit = settings().git_commit
    if commit == "unknown" and shutil.which("git"):
        from pathlib import Path

        project_root = Path(__file__).resolve().parents[2]
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=project_root, capture_output=True, text=True
        )
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project_root, capture_output=True, text=True
        )
        is_project_repo = top.returncode == 0 and Path(top.stdout.strip()) == project_root
        commit = (
            result.stdout.strip()
            if result.returncode == 0 and is_project_repo
            else "unversioned-working-tree"
        )
    elif commit == "unknown":
        commit = "unversioned-build"
    run = TrainingRun(
        language_id=lang.id,
        dataset_id=dataset.id,
        task=body.task,
        base_model=base,
        base_model_revision=revision,
        hyperparameters=config,
        random_seed=body.random_seed,
        git_commit=commit,
        environment=environment(),
    )
    db.add(run)
    db.flush()
    db.add(RunEvent(run_id=run.id, message="Queued for local training worker", data={"progress": 0}))
    audit(db, user, "training.queue", run.id)
    db.commit()  # Durable outbox; dispatcher schedules it even if Redis is temporarily unavailable.
    return serialize(run)


@router.get("/languages/{language_id}/training-runs")
def runs(language_id: str, user=Depends(principal), db=Depends(session)):
    lang = language(db, language_id, user)
    return [
        serialize(r)
        for r in db.scalars(
            select(TrainingRun)
            .where(TrainingRun.language_id == lang.id)
            .order_by(TrainingRun.created_at.desc())
        )
    ]


@router.get("/training-runs/{run_id}")
def run(run_id: str, user=Depends(principal), db=Depends(session)):
    return serialize(scoped(db, TrainingRun, run_id, user))


@router.post("/training-runs/{run_id}/cancel")
def cancel(run_id: str, user=Depends(editor), db=Depends(session)):
    record = scoped(db, TrainingRun, run_id, user)
    record = db.scalar(select(TrainingRun).where(TrainingRun.id == record.id).with_for_update())
    if record.status in TERMINAL:
        raise HTTPException(409, "Run is already terminal")
    record.cancel_requested = True
    if record.status == "QUEUED":
        record.status, record.completed_at = "CANCELLED", now()
    audit(db, user, "training.cancel", record.id)
    db.commit()
    return serialize(record)


@router.get("/training-runs/{run_id}/events")
def events(run_id: str, after: int = Query(0, ge=0), user=Depends(principal), db=Depends(session)):
    scoped(db, TrainingRun, run_id, user)
    return [
        serialize(e)
        for e in db.scalars(
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.id > after)
            .order_by(RunEvent.id)
            .limit(500)
        )
    ]


@router.get("/training-runs/{run_id}/stream")
def stream(run_id: str, after: int = Query(0, ge=0), user=Depends(principal), db=Depends(session)):
    scoped(db, TrainingRun, run_id, user)
    from fastapi.encoders import jsonable_encoder

    def generate():
        cursor = after
        # Bounded stream; browser reconnects with last event ID through query parameter.
        for _ in range(120):
            with Session() as current:
                rows = list(
                    current.scalars(
                        select(RunEvent)
                        .where(RunEvent.run_id == run_id, RunEvent.id > cursor)
                        .order_by(RunEvent.id)
                        .limit(500)
                    )
                )
                identity = current.get(Identity, user.id)
                if not identity or not identity.active:
                    return
                record = current.get(TrainingRun, run_id)
                for row in rows:
                    cursor = row.id
                    yield f"id: {row.id}\ndata: {json.dumps(jsonable_encoder(serialize(row)))}\n\n"
                if record.status in TERMINAL and len(rows) < 500:
                    yield "event: complete\ndata: {}\n\n"
                    return
            yield ": heartbeat\n\n"
            time.sleep(1)

    db.close()
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/languages/{language_id}/models")
def models(language_id: str, user=Depends(principal), db=Depends(session)):
    lang = language(db, language_id, user)
    return [
        serialize(m)
        for m in db.scalars(
            select(ModelRecord)
            .where(ModelRecord.language_id == lang.id)
            .order_by(ModelRecord.created_at.desc())
        )
    ]


@router.get("/models/{model_id}")
def model(model_id: str, user=Depends(principal), db=Depends(session)):
    return serialize(scoped(db, ModelRecord, model_id, user))


@router.get("/models/{model_id}/evaluation")
def evaluate(model_id: str, user=Depends(principal), db=Depends(session)):
    return scoped(db, ModelRecord, model_id, user).metrics


@router.get("/models/{model_id}/lineage")
def lineage(model_id: str, user=Depends(principal), db=Depends(session)):
    record = scoped(db, ModelRecord, model_id, user)
    dataset = db.get(Dataset, record.dataset_id)
    deployment = db.scalar(select(Deployment).where(Deployment.model_id == record.id))
    return {
        "model": serialize(record),
        "training_run": serialize(db.get(TrainingRun, record.training_run_id)),
        "dataset": serialize(dataset),
        "sources": [serialize(db.get(Source, ref)) for ref in dataset.source_ids],
        "deployment": serialize(deployment) if deployment else None,
    }


@router.post("/models/{model_id}/approve")
def approve(model_id: str, user=Depends(owner), db=Depends(session)):
    record = scoped(db, ModelRecord, model_id, user)
    record = db.scalar(select(ModelRecord).where(ModelRecord.id == record.id).with_for_update())
    if record.status != "EVALUATED":
        raise HTTPException(409, "Only evaluated models can be approved")
    record.status, record.approved_by = "APPROVED", user.id
    audit(db, user, "model.approve", record.id)
    db.commit()
    return serialize(record)


@router.get("/models/{model_id}/artifact")
def artifact(model_id: str, user=Depends(principal), db=Depends(session)):
    from fastapi.responses import Response

    record = scoped(db, ModelRecord, model_id, user)
    return Response(
        store().get(record.artifact, record.artifact_sha256),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="model-{record.id}.zip"'},
    )

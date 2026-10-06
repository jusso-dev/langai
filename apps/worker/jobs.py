import importlib.metadata
import io
import os
import platform
import shutil
import tempfile
import threading
import zipfile
from pathlib import Path
from sqlalchemy import select, update, func
from apps.api.config import settings
from apps.api.db import Session, now
from apps.api.models import Dataset, Language, ModelRecord, RunEvent, TrainingRun
from apps.api.storage import store, json_bytes

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}


class Cancelled(Exception):
    pass


def emit(run_id, message, data=None, status=None):
    with Session() as db:
        run = db.get(TrainingRun, run_id)
        if run.cancel_requested:
            raise Cancelled()
        if run.status in TERMINAL:
            raise Cancelled()
        if status:
            run.status = status
        run.heartbeat_at = now()
        db.add(RunEvent(run_id=run_id, message=message, data=data or {}))
        db.commit()


def heartbeat(run_id, stop):
    while not stop.wait(15):
        with Session() as db:
            db.execute(
                update(TrainingRun)
                .where(TrainingRun.id == run_id, TrainingRun.status.notin_(TERMINAL))
                .values(heartbeat_at=now())
            )
            db.commit()


def source_fingerprint():
    import hashlib

    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for folder in ["apps/api", "apps/worker", "ml"]:
        for path in sorted((root / folder).rglob("*.py")):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def environment():
    packages = {}
    for name in ["torch", "transformers", "sentence-transformers", "datasets", "scikit-learn", "peft"]:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "source_sha256": source_fingerprint(),
    }


def execute(run_id):
    with Session() as db:
        # Atomic claim makes duplicate deliveries harmless, including dispatcher recovery.
        result = db.execute(
            update(TrainingRun)
            .where(TrainingRun.id == run_id, TrainingRun.status == "QUEUED")
            .values(status="PREPARING", started_at=now(), heartbeat_at=now())
        )
        db.commit()
        if result.rowcount != 1:
            return
        run = db.get(TrainingRun, run_id)
        dataset = db.get(Dataset, run.dataset_id)
        config = {**run.hyperparameters, "seed": run.random_seed}
    stop = threading.Event()
    thread = threading.Thread(target=heartbeat, args=(run_id, stop), daemon=True)
    thread.start()
    try:
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["DO_NOT_TRACK"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        snapshot = store().json(dataset.object_key, dataset.sha256)
        emit(
            run_id,
            "Verified frozen dataset and split manifest",
            {"sha256": dataset.sha256, "environment": environment()},
        )
        with tempfile.TemporaryDirectory(prefix="langai-train-") as temp:
            output = Path(temp)
            # Bundle only implementation and dependency locks, never credentials or workspace files.
            project_root = Path(__file__).resolve().parents[2]
            for folder in ["apps/api", "apps/worker", "ml"]:
                for path in sorted((project_root / folder).rglob("*.py")):
                    target = output / "source" / path.relative_to(project_root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
            for name in ["pyproject.toml", "uv.lock"]:
                shutil.copy2(project_root / name, output / "source" / name)
            import torch

            if config["device"] == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("Requested CUDA is unavailable on this worker")
            if config["device"] == "mps" and not torch.backends.mps.is_available():
                raise RuntimeError("Requested MPS is unavailable on this worker")
            if run.task == "embeddings":
                if run.base_model == "test-tiny":
                    from ml.encoders.tiny import TinyEncoder

                    encoder = TinyEncoder(run.random_seed)
                else:
                    from ml.encoders.sentence import SentenceEncoder

                    encoder = SentenceEncoder(
                        run.base_model, run.base_model_revision, config["device"], settings().local_files_only
                    )
                    encoder.model.max_seq_length = config["max_length"]
                encoder.save(output / "base")
                from ml.evaluation.retrieval import retrieval

                test_ids = {k for k, v in snapshot["manifest"]["entry_splits"].items() if v == "test"}
                emit(run_id, "Evaluating unmodified encoder on held-out entries")
                baseline = retrieval(encoder, snapshot["entries"], test_ids)
                emit(run_id, "Base model evaluation complete", baseline, "TRAINING")
                training = encoder.train(snapshot, config, lambda message, data: emit(run_id, message, data))
                emit(run_id, "Evaluating selected checkpoint on held-out test entries", status="EVALUATING")
                tuned = retrieval(encoder, snapshot["entries"], test_ids)
                encoder.save(output / "encoder")
                metrics = {
                    "baseline": baseline,
                    "fine_tuned": tuned,
                    "training": training,
                    "delta": {
                        k: tuned[k] - baseline[k]
                        for k in ["recall_at_1", "recall_at_5", "recall_at_10", "mrr"]
                    },
                    "limitations": "Dictionary representations only; small held-out sets have high uncertainty.",
                    "test_only_encoder": run.base_model == "test-tiny",
                }
            elif run.task == "language-identification":
                from ml.classifiers.ngram import train

                emit(run_id, "Training character n-gram baselines", status="TRAINING")
                model, metrics = train(snapshot, lambda message, data: emit(run_id, message, data))
                emit(run_id, "Classifier evaluation complete", status="EVALUATING")
                model.save(output / "classifier")
            else:
                from huggingface_hub import snapshot_download
                from ml.generative.adapter import train_adapter

                base_path = snapshot_download(
                    run.base_model,
                    revision=run.base_model_revision,
                    local_files_only=settings().local_files_only,
                    ignore_patterns=["*.bin", "*.h5", "*.msgpack", "*.onnx"],
                )
                emit(run_id, "Starting EXPERIMENTAL dictionary LoRA adapter", status="TRAINING")
                metrics = train_adapter(snapshot, base_path, output, config, lambda m, d: emit(run_id, m, d))
                emit(run_id, "Adapter evaluation complete", status="EVALUATING")
                shutil.rmtree(output / "checkpoints", ignore_errors=True)
            (output / "lineage.json").write_bytes(
                json_bytes(
                    {
                        "training_run_id": run_id,
                        "dataset_id": dataset.id,
                        "dataset_sha256": dataset.sha256,
                        "base_model": run.base_model,
                        "base_model_revision": run.base_model_revision,
                        "hyperparameters": config,
                        "environment": environment(),
                        "git_commit": run.git_commit,
                        "metrics": metrics,
                    }
                )
            )
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(output.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(output))
            key = f"languages/{run.language_id}/runs/{run_id}/artifact.zip"
            sha = store().put(key, buffer.getvalue(), "application/zip")
        with Session() as db:
            current = db.scalar(select(TrainingRun).where(TrainingRun.id == run_id).with_for_update())
            if current.cancel_requested or current.status in TERMINAL:
                raise Cancelled()
            # Lock parent to serialize version allocation across independent training workers.
            db.scalar(select(Language).where(Language.id == run.language_id).with_for_update())
            version = (
                db.scalar(
                    select(func.max(ModelRecord.version)).where(
                        ModelRecord.language_id == run.language_id, ModelRecord.task == run.task
                    )
                )
                or 0
            ) + 1
            model = ModelRecord(
                language_id=run.language_id,
                training_run_id=run_id,
                dataset_id=run.dataset_id,
                task=run.task,
                version=version,
                base_model=run.base_model,
                base_model_revision=run.base_model_revision,
                metrics=metrics,
                artifact=key,
                artifact_sha256=sha,
                experimental=run.task == "dictionary-adapter",
            )
            db.add(model)
            current.status, current.metrics, current.artifact_location, current.completed_at = (
                "COMPLETED",
                metrics,
                key,
                now(),
            )
            db.add(
                RunEvent(
                    run_id=run_id,
                    message="Model registered privately. Approval and deployment are separate actions.",
                    data={"progress": 1},
                )
            )
            db.commit()
    except BaseException as exc:
        with Session() as db:
            current = db.scalar(select(TrainingRun).where(TrainingRun.id == run_id).with_for_update())
            # A watchdog or another coordinator may have terminated the run while
            # this worker was blocked. Never rewrite that historical outcome.
            if current.status in TERMINAL:
                return
            current.status = (
                "CANCELLED" if isinstance(exc, Cancelled) or current.cancel_requested else "FAILED"
            )
            # Do not log training rows or exception payloads that could contain private text.
            current.error = (
                None
                if current.status == "CANCELLED"
                else f"{type(exc).__name__}: training failed. Check worker diagnostics."
            )
            current.completed_at = now()
            db.add(RunEvent(run_id=run_id, message=current.error or "Training cancelled", data={}))
            db.commit()
        if not isinstance(exc, Cancelled):
            import logging
            import traceback

            frames = [
                {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                for f in traceback.extract_tb(exc.__traceback__)
            ]
            logging.getLogger(__name__).error(
                "Training run %s failed: %s; frames=%s", run_id, type(exc).__name__, frames
            )
    finally:
        stop.set()
        thread.join(timeout=2)

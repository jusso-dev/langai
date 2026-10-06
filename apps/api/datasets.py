from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from apps.api.auth import audit, editor, language, principal, scoped
from apps.api.db import session, uid
from apps.api.models import Dataset, Entry, Language, NegativeCorpus, Source
from apps.api.schemas import DatasetCreate, NegativeCreate
from apps.api.serialization import entry_snapshot, serialize
from apps.api.storage import store, json_bytes
from ml.datasets.generation import generate

router = APIRouter(tags=["Datasets"])


@router.post("/languages/{language_id}/negative-corpora", status_code=201)
def create_negatives(language_id: str, body: NegativeCreate, user=Depends(editor), db=Depends(session)):
    lang = language(db, language_id, user)
    if not body.governance.training_allowed:
        raise HTTPException(403, "Training permission is required for external negative data")
    if any(not t.strip() or len(t) > 4000 for t in body.texts):
        raise HTTPException(422, "Negative texts must contain 1–4000 characters")
    ref = uid()
    key = f"languages/{lang.id}/negative-corpora/{ref}.json"
    sha = store().put(key, json_bytes(body.texts), "application/json")
    record = NegativeCorpus(
        id=ref,
        language_id=lang.id,
        name=body.name,
        governance=body.governance.model_dump(),
        object_key=key,
        sha256=sha,
    )
    db.add(record)
    audit(db, user, "negative-corpus.approve", ref)
    db.commit()
    return serialize(record)


@router.get("/languages/{language_id}/negative-corpora")
def list_negatives(language_id: str, user=Depends(principal), db=Depends(session)):
    lang = language(db, language_id, user)
    return [
        serialize(n) for n in db.scalars(select(NegativeCorpus).where(NegativeCorpus.language_id == lang.id))
    ]


@router.post("/languages/{language_id}/datasets", status_code=201)
def create_dataset(language_id: str, body: DatasetCreate, user=Depends(editor), db=Depends(session)):
    lang = language(db, language_id, user)
    db.scalar(select(Language).where(Language.id == lang.id).with_for_update())
    sources = [scoped(db, Source, ref, user) for ref in sorted(set(body.source_ids))]
    if any(s.language_id != lang.id for s in sources):
        raise HTTPException(422, "A dataset may only contain this language's dictionaries")
    if any(s.status != "APPROVED" or not s.governance["training_allowed"] for s in sources):
        raise HTTPException(403, "Every source must be approved and allow training")
    rows = list(
        db.scalars(
            select(Entry).where(
                Entry.source_id.in_([s.id for s in sources]),
                Entry.approved.is_(True),
                Entry.training_eligible.is_(True),
            )
        )
    )
    negatives = None
    if body.negative_corpus_id:
        corpus = scoped(db, NegativeCorpus, body.negative_corpus_id, user)
        if corpus.language_id != lang.id:
            raise HTTPException(422, "Negative corpus belongs to another language")
        negatives = {
            "id": corpus.id,
            "texts": store().json(corpus.object_key, corpus.sha256),
            "sha256": corpus.sha256,
            "governance": corpus.governance,
        }
    try:
        snapshot = generate([entry_snapshot(e) for e in rows], body.seed, negatives)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    dataset_id = uid()
    version = (db.scalar(select(func.max(Dataset.version)).where(Dataset.language_id == lang.id)) or 0) + 1
    key = f"languages/{lang.id}/datasets/{dataset_id}.json"
    governance = [{"source_id": s.id, **s.governance} for s in sources]
    if negatives:
        governance.append({"negative_corpus_id": negatives["id"], **negatives["governance"]})
    snapshot.update({"id": dataset_id, "language_id": lang.id, "version": version, "governance": governance})
    sha = store().put(key, json_bytes(snapshot), "application/json")
    record = Dataset(
        id=dataset_id,
        language_id=lang.id,
        version=version,
        source_ids=[s.id for s in sources],
        governance=governance,
        object_key=key,
        sha256=sha,
        manifest=snapshot["manifest"],
        seed=body.seed,
        entry_count=len(rows),
    )
    db.add(record)
    audit(db, user, "dataset.create", dataset_id, sha256=sha)
    db.commit()
    return serialize(record)


@router.get("/languages/{language_id}/datasets")
def list_datasets(language_id: str, user=Depends(principal), db=Depends(session)):
    lang = language(db, language_id, user)
    return [
        serialize(d)
        for d in db.scalars(
            select(Dataset).where(Dataset.language_id == lang.id).order_by(Dataset.version.desc())
        )
    ]


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, user=Depends(principal), db=Depends(session)):
    return serialize(scoped(db, Dataset, dataset_id, user))


@router.get("/datasets/{dataset_id}/samples")
def samples(dataset_id: str, user=Depends(principal), db=Depends(session)):
    dataset = scoped(db, Dataset, dataset_id, user)
    snapshot = store().json(dataset.object_key, dataset.sha256)
    return {
        "views": {k: {"count": len(v), "samples": v[:10]} for k, v in snapshot["views"].items()},
        "manifest": snapshot["manifest"],
    }


@router.get("/datasets/{dataset_id}/export")
def export(dataset_id: str, user=Depends(principal), db=Depends(session)):
    from fastapi.responses import Response

    dataset = scoped(db, Dataset, dataset_id, user)
    return Response(
        store().get(dataset.object_key, dataset.sha256),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="dataset-{dataset.id}.json"'},
    )

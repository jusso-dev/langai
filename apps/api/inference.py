import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, cast
from pgvector.sqlalchemy import Vector
from apps.api.auth import audit, language, owner, principal, scoped
from apps.api.db import now, session
from apps.api.models import ConceptVector, Dataset, Deployment, Entry, Language, ModelRecord
from apps.api.schemas import (
    Embed,
    Match,
    Query,
    EmbedResponse,
    SearchResponse,
    MatchResponse,
    ClassificationResponse,
    DictionaryResponse,
)
from apps.api.serialization import serialize
from apps.api.storage import store
from ml.datasets.generation import identity
from ml.inference.artifacts import classifier, encoder

router = APIRouter(tags=["Deployment & inference"])


def deployed(db, lang, task):
    deployment = db.scalar(
        select(Deployment).where(Deployment.language_id == lang.id, Deployment.task == task)
    )
    if not deployment:
        raise HTTPException(409, f"No deployed {task} model for this language")
    return db.get(ModelRecord, deployment.model_id)


@router.post("/models/{model_id}/deploy")
def deploy(model_id: str, user=Depends(owner), db=Depends(session)):
    model = scoped(db, ModelRecord, model_id, user)
    db.scalar(select(Language).where(Language.id == model.language_id).with_for_update())
    model = db.scalar(select(ModelRecord).where(ModelRecord.id == model.id).with_for_update())
    if model.status not in {"APPROVED", "DEPLOYED"}:
        raise HTTPException(409, "Approve the evaluated model before deployment")
    if model.task == "dictionary-adapter":
        raise HTTPException(
            422, "Experimental adapters are downloadable research artifacts, not public fluency endpoints"
        )
    if model.task == "embeddings":
        model_encoder = encoder(model.artifact, model.artifact_sha256)
        dataset = db.get(Dataset, model.dataset_id)
        snapshot = store().json(dataset.object_key, dataset.sha256)
        db.execute(delete(ConceptVector).where(ConceptVector.model_id == model.id))
        for start in range(0, len(snapshot["entries"]), 128):
            rows = snapshot["entries"][start : start + 128]
            for kind in ["headword", "definition", "combined"]:
                texts = [
                    e["normalized_headword"]
                    if kind == "headword"
                    else "; ".join(e["definitions"])
                    if kind == "definition"
                    else e["normalized_headword"] + ": " + "; ".join(e["definitions"])
                    for e in rows
                ]
                vectors = model_encoder.encode(texts)
                db.add_all(
                    [
                        ConceptVector(
                            language_id=model.language_id,
                            model_id=model.id,
                            entry_id=e["id"],
                            kind=kind,
                            concept={
                                "headword": e["headword"],
                                "normalized_headword": e["normalized_headword"],
                                "definitions": e["definitions"],
                                "source_id": e["source_id"],
                                "dialect": e["dialect"],
                            },
                            embedding=v.tolist(),
                        )
                        for e, v in zip(rows, vectors)
                    ]
                )
    else:
        classifier(model.artifact, model.artifact_sha256)  # Verify loadability before switching deployment.
    deployment = db.scalar(
        select(Deployment).where(Deployment.language_id == model.language_id, Deployment.task == model.task)
    )
    if deployment:
        old = db.get(ModelRecord, deployment.model_id)
        if old.id != model.id:
            old.status = "APPROVED"
        deployment.model_id, deployment.deployed_at = model.id, now()
    else:
        db.add(Deployment(language_id=model.language_id, task=model.task, model_id=model.id))
    model.status = "DEPLOYED"
    audit(db, user, "model.deploy", model.id)
    db.commit()
    return serialize(model)


@router.post("/models/{model_id}/archive")
def archive(model_id: str, user=Depends(owner), db=Depends(session)):
    model = scoped(db, ModelRecord, model_id, user)
    db.scalar(select(Language).where(Language.id == model.language_id).with_for_update())
    model = db.scalar(select(ModelRecord).where(ModelRecord.id == model.id).with_for_update())
    if model.status == "DEPLOYED":
        raise HTTPException(409, "Deploy a replacement before archiving the active model")
    model.status = "ARCHIVED"
    audit(db, user, "model.archive", model.id)
    db.commit()
    return serialize(model)


@router.post("/v1/embed", response_model=EmbedResponse)
def embed(body: Embed, user=Depends(principal), db=Depends(session)):
    lang = language(db, body.language, user)
    model = deployed(db, lang, "embeddings")
    values = encoder(model.artifact, model.artifact_sha256).encode(body.texts)
    return {
        "language": lang.id,
        "model_id": model.id,
        "dimensions": values.shape[1],
        "embeddings": values.tolist(),
    }


def search_model(db, model, body):
    kind = {
        "semantic": "combined",
        "word-to-meaning": "definition",
        "meaning-to-word": "headword",
        "similar-words": "headword",
    }[body.mode]
    vector = encoder(model.artifact, model.artifact_sha256).encode([body.query])[0]
    stmt = select(ConceptVector).where(
        ConceptVector.model_id == model.id,
        ConceptVector.language_id == model.language_id,
        ConceptVector.kind == kind,
    )
    if db.bind.dialect.name == "postgresql":
        # Exact pgvector cosine search; no approximate index recall tradeoffs for small dictionaries.
        distance = cast(ConceptVector.embedding, Vector(len(vector))).cosine_distance(vector.tolist())
        rows = db.execute(
            stmt.add_columns(distance.label("distance"))
            .order_by(distance, ConceptVector.entry_id)
            .limit(body.limit)
        ).all()
        matches = [
            {"entry_id": row.entry_id, **row.concept, "score": float(np.clip(1 - distance, -1, 1))}
            for row, distance in rows
        ]
    else:
        candidates = list(db.scalars(stmt))
        matches = [
            {
                "entry_id": row.entry_id,
                **row.concept,
                "score": float(np.clip(np.dot(np.asarray(row.embedding), vector), -1, 1)),
            }
            for row in candidates
        ]
        matches.sort(key=lambda row: (-row["score"], row["entry_id"]))
        matches = matches[: body.limit]
    return {
        "language": model.language_id,
        "model_id": model.id,
        "score_type": "cosine_similarity",
        "matches": matches,
    }


@router.post("/v1/search", response_model=SearchResponse)
def search(body: Query, user=Depends(principal), db=Depends(session)):
    lang = language(db, body.language, user)
    return search_model(db, deployed(db, lang, "embeddings"), body)


@router.post("/v1/match", response_model=MatchResponse)
def match(body: Match, user=Depends(principal), db=Depends(session)):
    lang = language(db, body.language, user)
    result = search_model(
        db,
        deployed(db, lang, "embeddings"),
        Query(language=lang.id, query=body.word, limit=body.limit, mode="word-to-meaning"),
    )
    result["matches"] = [{**row, "definition": "; ".join(row["definitions"])} for row in result["matches"]]
    return result


@router.post("/v1/classify-language", response_model=ClassificationResponse)
def classify(body: Query, user=Depends(principal), db=Depends(session)):
    lang = language(db, body.language, user)
    model = deployed(db, lang, "language-identification")
    result = classifier(model.artifact, model.artifact_sha256).predict([body.query])[0]
    return {
        "language": lang.name if result["is_language"] else "other",
        "configured_language": lang.name,
        "model_id": model.id,
        **result,
        "scope": "configured language versus approved negative corpus",
    }


@router.get("/v1/dictionary/{word:path}", response_model=DictionaryResponse)
def dictionary_word(word: str, language: str, user=Depends(principal), db=Depends(session)):
    from apps.api.auth import language as get_language

    lang = get_language(db, language, user)
    entries = db.scalars(select(Entry).where(Entry.language_id == lang.id, Entry.approved.is_(True)))
    return {
        "language": lang.id,
        "entries": [
            serialize(e)
            for e in entries
            if identity(word)
            in {identity(e.normalized_headword), *(identity(v) for v in e.alternate_spellings)}
        ],
    }


@router.post("/models/{model_id}/playground")
def playground(model_id: str, body: Query, user=Depends(principal), db=Depends(session)):
    model = scoped(db, ModelRecord, model_id, user)
    lang = language(db, body.language, user)
    if model.language_id != lang.id:
        raise HTTPException(422, "Model belongs to another language")
    if model.task == "language-identification":
        return {
            "model_id": model.id,
            "classification": classifier(model.artifact, model.artifact_sha256).predict([body.query])[0],
        }
    if model.task != "embeddings":
        raise HTTPException(422, "This playground supports encoders and classifiers")
    dataset = db.get(Dataset, model.dataset_id)
    entries = store().json(dataset.object_key, dataset.sha256)["entries"]
    texts = [
        "; ".join(e["definitions"])
        if body.mode == "word-to-meaning"
        else e["normalized_headword"]
        if body.mode in {"meaning-to-word", "similar-words"}
        else e["normalized_headword"] + ": " + "; ".join(e["definitions"])
        for e in entries
    ]
    result = {}
    for label, base in [("baseline", True), ("fine_tuned", False)]:
        model_encoder = encoder(model.artifact, model.artifact_sha256, base)
        scores = model_encoder.encode(texts) @ model_encoder.encode([body.query])[0]
        indices = np.argsort(-scores, kind="stable")[: body.limit]
        result[label] = [
            {
                "entry_id": entries[i]["id"],
                "headword": entries[i]["headword"],
                "definitions": entries[i]["definitions"],
                "score": float(np.clip(scores[i], -1, 1)),
            }
            for i in indices
        ]
    return {"model_id": model.id, "score_type": "cosine_similarity", **result}

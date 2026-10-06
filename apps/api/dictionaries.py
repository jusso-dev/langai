from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import Response
from sqlalchemy import delete, func, select
from pydantic import ValidationError
from apps.api.auth import audit, editor, language, principal, scoped
from apps.api.config import settings
from apps.api.db import session, uid
from apps.api.models import Entry, Source
from apps.api.schemas import Governance, ImportConfig, Review
from apps.api.serialization import serialize
from apps.api.storage import store, digest
from ml.datasets.importers import parse_file, ALIASES
from ml.datasets.normalization import canonicalize, quality

router = APIRouter(tags=["Dictionary"])


@router.post("/languages/{language_id}/dictionaries", status_code=201)
def upload(
    language_id: str,
    file: UploadFile = File(...),
    governance: str = Form(...),
    user=Depends(editor),
    db=Depends(session),
):
    lang = language(db, language_id, user)
    try:
        permission = Governance.model_validate_json(governance)
    except (ValidationError, ValueError):
        raise HTTPException(422, "Provide valid dictionary ownership, source and licence metadata")
    content = bytearray()
    while chunk := file.file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > settings().max_upload_bytes:
            raise HTTPException(413, "Dictionary exceeds the 25 MB upload limit")
    filename = Path(file.filename or "dictionary.txt").name[:255]
    try:
        rows, columns, suggested = parse_file(filename, bytes(content), settings().max_rows)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    source_id = uid()
    key = f"languages/{lang.id}/sources/{source_id}/original{Path(filename).suffix.lower()}"
    store().put(key, bytes(content), file.content_type or "application/octet-stream")
    source = Source(
        id=source_id,
        language_id=lang.id,
        filename=filename,
        object_key=key,
        sha256=digest(content),
        governance=permission.model_dump(),
        columns=columns,
        mapping=suggested,
    )
    db.add(source)
    audit(db, user, "dictionary.upload", source_id, sha256=source.sha256)
    db.commit()
    return {
        **serialize(source),
        "suggested_mapping": suggested,
        "preview_rows": rows[:10],
        "row_count": len(rows),
    }


@router.get("/languages/{language_id}/dictionaries")
def list_sources(language_id: str, user=Depends(principal), db=Depends(session)):
    lang = language(db, language_id, user)
    return [
        serialize(s)
        for s in db.scalars(
            select(Source).where(Source.language_id == lang.id).order_by(Source.created_at.desc())
        )
    ]


@router.get("/dictionaries/{source_id}")
def get_source(source_id: str, user=Depends(principal), db=Depends(session)):
    return serialize(scoped(db, Source, source_id, user))


@router.get("/dictionaries/{source_id}/original")
def original(source_id: str, user=Depends(principal), db=Depends(session)):
    source = scoped(db, Source, source_id, user)
    return Response(
        store().get(source.object_key, source.sha256),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=dictionary-original"},
    )


def preview_entries(source, config):
    if any(field not in ALIASES for field in config.mapping):
        raise HTTPException(422, "Unknown canonical field in mapping")
    if any(column not in source.columns for column in config.mapping.values()):
        raise HTTPException(422, "Mapped column not present in source")
    rows, _, _ = parse_file(
        source.filename, store().get(source.object_key, source.sha256), settings().max_rows
    )
    try:
        return canonicalize(
            rows, config.mapping, config.normalization.model_dump(), source.id, source.language_id
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/dictionaries/{source_id}/preview")
def preview(source_id: str, config: ImportConfig, user=Depends(editor), db=Depends(session)):
    source = scoped(db, Source, source_id, user)
    entries = preview_entries(source, config)
    return {"quality": quality(entries), "entries": entries[:100], "preview_limit": 100}


@router.post("/dictionaries/{source_id}/import")
def import_dictionary(source_id: str, config: ImportConfig, user=Depends(editor), db=Depends(session)):
    source = scoped(db, Source, source_id, user)
    source = db.scalar(select(Source).where(Source.id == source.id).with_for_update())
    if source.status == "APPROVED":
        raise HTTPException(
            409, "Approved dictionaries are immutable. Upload a new version to change mappings."
        )
    entries = preview_entries(source, config)
    db.execute(delete(Entry).where(Entry.source_id == source.id))
    db.add_all([Entry(**e) for e in entries])
    source.mapping, source.normalization = config.mapping, config.normalization.model_dump()
    source.quality, source.status = quality(entries), "REVIEW"
    audit(db, user, "dictionary.import", source.id, normalization=source.normalization)
    db.commit()
    return serialize(source)


@router.get("/dictionaries/{source_id}/entries")
def entries(
    source_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    issue: str | None = None,
    q: str = "",
    user=Depends(principal),
    db=Depends(session),
):
    source = scoped(db, Source, source_id, user)
    stmt = select(Entry).where(Entry.source_id == source.id)
    if q:
        stmt = stmt.where(Entry.normalized_headword.contains(q, autoescape=True))
    # JSON issues are filtered portably; upload size is explicitly bounded.
    if issue:
        rows = [e for e in db.scalars(stmt.order_by(Entry.row_number)) if issue in e.issues]
        return {"items": [serialize(e) for e in rows[offset : offset + limit]], "total": len(rows)}
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    return {
        "items": [
            serialize(e) for e in db.scalars(stmt.order_by(Entry.row_number).offset(offset).limit(limit))
        ],
        "total": total,
    }


@router.patch("/entries/{entry_id}")
def review_entry(entry_id: str, review: Review, user=Depends(editor), db=Depends(session)):
    entry = scoped(db, Entry, entry_id, user)
    source = db.scalar(select(Source).where(Source.id == entry.source_id).with_for_update())
    if source.status == "APPROVED":
        raise HTTPException(409, "Source is frozen. Upload a new version to change approval decisions.")
    if review.training_eligible and (
        not review.approved or not entry.normalized_headword or not entry.definitions
    ):
        raise HTTPException(422, "Eligible entries require approval, a headword and definitions")
    entry.approved, entry.training_eligible = review.approved, review.training_eligible
    entry.entry_metadata = {**entry.entry_metadata, "reviewed_by": user.id, "explicit_review": True}
    audit(db, user, "entry.review", entry.id, **review.model_dump())
    db.commit()
    return serialize(entry)


@router.post("/dictionaries/{source_id}/approve")
def approve(source_id: str, user=Depends(editor), db=Depends(session)):
    source = scoped(db, Source, source_id, user)
    source = db.scalar(select(Source).where(Source.id == source.id).with_for_update())
    if source.status != "REVIEW":
        raise HTTPException(409, "Import and review the dictionary first")
    if not source.governance["training_allowed"]:
        raise HTTPException(403, "The dictionary owner has not granted training permission")
    eligible = 0
    for entry in db.scalars(select(Entry).where(Entry.source_id == source.id)):
        if not entry.issues and not entry.entry_metadata.get("explicit_review"):
            entry.approved, entry.training_eligible = True, True
        eligible += bool(entry.approved and entry.training_eligible)
    if not eligible:
        raise HTTPException(422, "No eligible entries. Review flagged rows first.")
    source.status, source.approved_by = "APPROVED", user.id
    audit(db, user, "dictionary.approve", source.id, eligible_entries=eligible)
    db.commit()
    return {**serialize(source), "eligible_entries": eligible}

"""Portable dictionary matching packs; no neural weights or training required."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import select

from apps.api.auth import audit, language, principal, scoped
from apps.api.db import session
from apps.api.models import Entry, Source
from apps.api.schemas import Strict
from apps.api.storage import digest, json_bytes

router = APIRouter(tags=["Offline dictionary"])
MAX_PACK_BYTES = 32 * 1024 * 1024


class OfflineExportCreate(Strict):
    source_ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/languages/{language_id}/offline-export")
def export_offline(language_id: str, body: OfflineExportCreate, user=Depends(principal), db=Depends(session)):
    lang = language(db, language_id, user)
    sources = [scoped(db, Source, ref, user) for ref in sorted(set(body.source_ids))]
    if any(source.language_id != lang.id for source in sources):
        raise HTTPException(422, "An offline pack may only contain this language's dictionaries")
    if any(source.status != "APPROVED" for source in sources):
        raise HTTPException(403, "Approve every source before exporting an offline pack")
    rows = db.scalars(
        select(Entry)
        .where(
            Entry.source_id.in_([source.id for source in sources]),
            Entry.approved.is_(True),
            Entry.training_eligible.is_(True),
        )
        .order_by(Entry.id)
        .limit(100001)
    ).all()
    if not rows:
        raise HTTPException(422, "No approved, eligible entries to export")
    if len(rows) > 100000:
        raise HTTPException(422, "Choose fewer sources: offline packs support at most 100,000 entries")
    indexed_characters = sum(
        min(len(text), 256)
        for row in rows
        for text in [row.headword, *row.alternate_spellings, *row.definitions]
    )
    if indexed_characters > 2_000_000:
        raise HTTPException(
            422, "Choose fewer sources: phone search supports 2 million indexed characters per pack"
        )
    # Explicit allowlist: omit original rows, arbitrary metadata, negatives and training samples.
    payload = json_bytes(
        {
            "engine": "langai-lexical-v1",
            "language": {"id": lang.id, "name": lang.name},
            "sources": [
                {
                    "id": source.id,
                    "filename": source.filename,
                    "sha256": source.sha256,
                    "governance": source.governance,
                }
                for source in sources
            ],
            "entries": [
                {
                    "id": row.id,
                    "source_id": row.source_id,
                    "headword": row.headword,
                    "definitions": row.definitions,
                    "alternate_spellings": row.alternate_spellings,
                    "part_of_speech": row.part_of_speech,
                    "dialect": row.dialect,
                }
                for row in rows
            ],
        }
    )
    # Hash the exact UTF-8 string, avoiding cross-runtime JSON canonicalization differences.
    sha = digest(payload)
    data = json_bytes({"format": "langai-offline-v1", "sha256": sha, "payload": payload.decode("utf-8")})
    if len(data) > MAX_PACK_BYTES:
        raise HTTPException(422, "Choose fewer sources: offline packs must be smaller than 32 MiB")
    audit(
        db,
        user,
        "dictionary.offline-export",
        lang.id,
        sha256=sha,
        source_ids=body.source_ids,
        entry_count=len(rows),
    )
    db.commit()
    return Response(
        data,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="dictionary-{lang.id}.langai.json"',
        },
    )

import re
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from apps.api.auth import audit, bootstrap, editor, language, new_key, owner, principal, token_hash
from apps.api.db import session
from apps.api.models import AuditEvent, Dataset, Entry, Identity, Language, ModelRecord
from apps.api.schemas import KeyCreate, LanguageCreate
from apps.api.serialization import serialize
from apps.api import datasets, dictionaries, inference, offline, training


@asynccontextmanager
async def lifespan(app):
    bootstrap()
    yield


app = FastAPI(
    title="LangAI",
    version="0.1.0",
    lifespan=lifespan,
    description="Private dictionary representation training. Lexical knowledge is not conversational fluency.",
)
for router in [dictionaries.router, datasets.router, training.router, inference.router, offline.router]:
    app.include_router(router)


@app.middleware("http")
async def private_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse(
        status_code=409, content={"detail": "Conflicting update or duplicate name. Refresh and try again."}
    )


@app.get("/health", tags=["System"])
def health(db=Depends(session)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/me", tags=["Access"])
def me(user=Depends(principal)):
    return {"id": user.id, "name": user.name, "role": user.role, "workspace_id": user.workspace_id}


@app.post("/keys", status_code=201, tags=["Access"])
def create_key(body: KeyCreate, user=Depends(owner), db=Depends(session)):
    token = new_key()
    record = Identity(
        name=body.name, role=body.role, workspace_id=user.workspace_id, token_hash=token_hash(token)
    )
    db.add(record)
    db.flush()
    audit(db, user, "key.create", record.id, role=record.role)
    db.commit()
    return {**serialize(record), "token": token}


@app.get("/keys", tags=["Access"])
def keys(user=Depends(owner), db=Depends(session)):
    return [
        serialize(k) for k in db.scalars(select(Identity).where(Identity.workspace_id == user.workspace_id))
    ]


@app.delete("/keys/{key_id}", tags=["Access"])
def revoke_key(key_id: str, user=Depends(owner), db=Depends(session)):
    key = db.get(Identity, key_id)
    if not key or key.workspace_id != user.workspace_id:
        raise HTTPException(404, "Key not found")
    if key.id == user.id:
        raise HTTPException(409, "Use another owner key to revoke your current key")
    key.active = False
    audit(db, user, "key.revoke", key.id)
    db.commit()
    return {"revoked": True}


@app.get("/audit", tags=["Access"])
def audit_log(user=Depends(owner), db=Depends(session)):
    return [
        serialize(a)
        for a in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.workspace_id == user.workspace_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(200)
        )
    ]


@app.post("/languages", status_code=201, tags=["Languages"])
def create_language(body: LanguageCreate, user=Depends(editor), db=Depends(session)):
    slug = re.sub(r"[^\w]+", "-", body.name.lower()).strip("-") or "language"
    record = Language(workspace_id=user.workspace_id, slug=slug, **body.model_dump())
    db.add(record)
    db.flush()
    audit(db, user, "language.create", record.id)
    db.commit()
    return serialize(record)


@app.get("/languages", tags=["Languages"])
def languages(user=Depends(principal), db=Depends(session)):
    result = []
    for lang in db.scalars(
        select(Language).where(Language.workspace_id == user.workspace_id).order_by(Language.created_at)
    ):
        counts = {
            "entry_count": db.scalar(
                select(func.count()).select_from(Entry).where(Entry.language_id == lang.id)
            ),
            "model_count": db.scalar(
                select(func.count()).select_from(ModelRecord).where(ModelRecord.language_id == lang.id)
            ),
            "dataset_count": db.scalar(
                select(func.count()).select_from(Dataset).where(Dataset.language_id == lang.id)
            ),
        }
        result.append({**serialize(lang), **counts})
    return result


@app.get("/languages/{language_id}", tags=["Languages"])
def get_language(language_id: str, user=Depends(principal), db=Depends(session)):
    return serialize(language(db, language_id, user))


@app.patch("/languages/{language_id}", tags=["Languages"])
def update_language(language_id: str, body: LanguageCreate, user=Depends(editor), db=Depends(session)):
    record = language(db, language_id, user)
    for key, value in body.model_dump().items():
        setattr(record, key, value)
    audit(db, user, "language.update", record.id)
    db.commit()
    return serialize(record)

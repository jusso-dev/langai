import hashlib
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from apps.api.db import Session, session
from apps.api.models import AuditEvent, Identity, Language
from apps.api.config import settings

bearer = HTTPBearer(auto_error=False)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def bootstrap():
    with Session() as db:
        hashed = token_hash(settings().bootstrap_token)
        if not db.scalar(select(Identity).where(Identity.token_hash == hashed)):
            # Stable workspace across bootstrap secret rotation. Previous bootstrap keys are revoked.
            for key in db.scalars(select(Identity).where(Identity.name == "Bootstrap owner")):
                key.active = False
            db.add(
                Identity(name="Bootstrap owner", token_hash=hashed, workspace_id="local-owner", role="owner")
            )
            db.commit()


def principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(session)):
    if not credentials:
        raise HTTPException(401, "API key required", headers={"WWW-Authenticate": "Bearer"})
    key = db.scalar(
        select(Identity).where(
            Identity.token_hash == token_hash(credentials.credentials), Identity.active.is_(True)
        )
    )
    if not key:
        raise HTTPException(401, "Invalid API key")
    return key


def editor(user=Depends(principal)):
    if user.role not in {"editor", "owner"}:
        raise HTTPException(403, "Editor access required")
    return user


def owner(user=Depends(principal)):
    if user.role != "owner":
        raise HTTPException(403, "Owner access required")
    return user


def language(db, ref, user):
    lang = db.scalar(
        select(Language).where(
            Language.workspace_id == user.workspace_id, (Language.id == ref) | (Language.slug == ref)
        )
    )
    if not lang:
        raise HTTPException(404, "Language not found")
    return lang


def scoped(db, cls, ref, user):
    record = db.get(cls, ref)
    if not record:
        raise HTTPException(404, "Resource not found")
    language(db, record.language_id, user)
    return record


def audit(db, user, action, resource_id, **details):
    db.add(
        AuditEvent(
            workspace_id=user.workspace_id,
            actor_id=user.id,
            action=action,
            resource_id=resource_id,
            details=details,
        )
    )


def new_key():
    return "lai_" + secrets.token_urlsafe(36)

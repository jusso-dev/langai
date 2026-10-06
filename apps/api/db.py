from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from apps.api.config import settings


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


def make_engine(url):
    if url.startswith("sqlite"):
        from pathlib import Path

        Path("data").mkdir(exist_ok=True)
    engine = create_engine(
        url, pool_pre_ping=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def sqlite_fk(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine(settings().database_url)
Session = sessionmaker(engine, expire_on_commit=False)


def session():
    with Session() as db:
        yield db


def protect_fields(mapper, connection, target):
    for field in target.IMMUTABLE:
        if inspect(target).attrs[field].history.has_changes():
            raise ValueError(f"{type(target).__name__}.{field} is immutable")

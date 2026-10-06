"""SQLite developer/test setup only. PostgreSQL deployments use Alembic."""

from apps.api.db import Base, engine
from apps.api.auth import bootstrap

if engine.dialect.name != "sqlite":
    raise SystemExit("Use alembic upgrade head for PostgreSQL")
Base.metadata.create_all(engine)
bootstrap()
print("Local SQLite workspace initialized")

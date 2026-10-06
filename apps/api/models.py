from datetime import datetime
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from apps.api.db import Base, now, protect_fields, uid


class Identity(Base):
    __tablename__ = "identities"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String, default="owner")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Language(Base):
    __tablename__ = "languages"
    __table_args__ = (UniqueConstraint("workspace_id", "slug"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    slug: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    alternate_names: Mapped[list] = mapped_column(JSON, default=list)
    iso_code: Mapped[str | None] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    default_dialect: Mapped[str] = mapped_column(String, default="")
    orthography_notes: Mapped[str] = mapped_column(Text, default="")
    source_community: Mapped[str] = mapped_column(Text, default="")
    governance_notes: Mapped[str] = mapped_column(Text, default="")
    visibility: Mapped[str] = mapped_column(String, default="PRIVATE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    language_id: Mapped[str] = mapped_column(ForeignKey("languages.id"), index=True)
    filename: Mapped[str] = mapped_column(String)
    object_key: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String)
    governance: Mapped[dict] = mapped_column(JSON)
    columns: Mapped[list] = mapped_column(JSON)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    normalization: Mapped[dict] = mapped_column(JSON, default=dict)
    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    visibility: Mapped[str] = mapped_column(String, default="PRIVATE")
    approved_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Entry(Base):
    __tablename__ = "entries"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    language_id: Mapped[str] = mapped_column(ForeignKey("languages.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    original_row: Mapped[dict] = mapped_column(JSON)
    headword: Mapped[str] = mapped_column(Text)
    normalized_headword: Mapped[str] = mapped_column(Text)
    definitions: Mapped[list] = mapped_column(JSON)
    alternate_spellings: Mapped[list] = mapped_column(JSON, default=list)
    part_of_speech: Mapped[str] = mapped_column(String, default="")
    dialect: Mapped[str] = mapped_column(String, default="")
    examples: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="")
    entry_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    training_eligible: Mapped[bool] = mapped_column(Boolean, default=False)


class NegativeCorpus(Base):
    __tablename__ = "negative_corpora"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    language_id: Mapped[str] = mapped_column(ForeignKey("languages.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    governance: Mapped[dict] = mapped_column(JSON)
    object_key: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("language_id", "version"),)
    IMMUTABLE = (
        "language_id",
        "version",
        "object_key",
        "sha256",
        "manifest",
        "seed",
        "generation_version",
        "source_ids",
        "governance",
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    language_id: Mapped[str] = mapped_column(ForeignKey("languages.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    source_ids: Mapped[list] = mapped_column(JSON)
    governance: Mapped[list] = mapped_column(JSON)
    object_key: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String)
    manifest: Mapped[dict] = mapped_column(JSON)
    seed: Mapped[int] = mapped_column(Integer)
    generation_version: Mapped[str] = mapped_column(String, default="1.0.0")
    entry_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TrainingRun(Base):
    __tablename__ = "training_runs"
    IMMUTABLE = (
        "language_id",
        "dataset_id",
        "task",
        "base_model",
        "base_model_revision",
        "hyperparameters",
        "random_seed",
        "git_commit",
        "environment",
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    language_id: Mapped[str] = mapped_column(ForeignKey("languages.id"), index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    task: Mapped[str] = mapped_column(String)
    base_model: Mapped[str] = mapped_column(String)
    base_model_revision: Mapped[str] = mapped_column(String)
    hyperparameters: Mapped[dict] = mapped_column(JSON)
    random_seed: Mapped[int] = mapped_column(Integer)
    git_commit: Mapped[str] = mapped_column(String)
    environment: Mapped[dict] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_location: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="QUEUED", index=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RunEvent(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("training_runs.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class ModelRecord(Base):
    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("language_id", "task", "version"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    language_id: Mapped[str] = mapped_column(ForeignKey("languages.id"), index=True)
    training_run_id: Mapped[str] = mapped_column(ForeignKey("training_runs.id"), unique=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    task: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer)
    base_model: Mapped[str] = mapped_column(String)
    base_model_revision: Mapped[str] = mapped_column(String)
    metrics: Mapped[dict] = mapped_column(JSON)
    artifact: Mapped[str] = mapped_column(String)
    artifact_sha256: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="EVALUATED")
    visibility: Mapped[str] = mapped_column(String, default="PRIVATE")
    experimental: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (UniqueConstraint("language_id", "task"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    language_id: Mapped[str] = mapped_column(ForeignKey("languages.id"))
    task: Mapped[str] = mapped_column(String)
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id"))
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConceptVector(Base):
    __tablename__ = "concept_vectors"
    __table_args__ = (UniqueConstraint("model_id", "entry_id", "kind"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    language_id: Mapped[str] = mapped_column(ForeignKey("languages.id"), index=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id"), index=True)
    entry_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    concept: Mapped[dict] = mapped_column(JSON)
    embedding: Mapped[list] = mapped_column(JSON().with_variant(Vector(), "postgresql"))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    actor_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    resource_id: Mapped[str] = mapped_column(String)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


for cls in (Dataset, TrainingRun):
    event.listen(cls, "before_update", protect_fields)

from functools import lru_cache
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LANGAI_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/langai.db"
    redis_url: str = "redis://localhost:56379/0"
    storage_backend: str = "local"
    storage_dir: Path = Path("data/objects")
    artifact_dir: Path = Path("data/artifacts")
    s3_endpoint: str = "http://localhost:59000"
    s3_bucket: str = "langai-private"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    bootstrap_token: str = ""
    base_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    model_revision: str = "auto"
    local_files_only: bool = False
    generative_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    enable_experimental: bool = False
    allow_test_encoder: bool = False
    max_upload_bytes: int = 25 * 1024 * 1024
    max_rows: int = 100_000
    job_timeout_seconds: int = 21600
    git_commit: str = "unknown"

    @model_validator(mode="after")
    def secure(self):
        if len(self.bootstrap_token) < 32 or self.bootstrap_token.startswith("replace-"):
            raise ValueError("Set LANGAI_BOOTSTRAP_TOKEN to a random secret of at least 32 characters")
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("storage_backend must be local or s3")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()

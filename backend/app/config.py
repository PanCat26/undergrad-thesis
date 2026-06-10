from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, driven entirely by environment variables.

    APP_ENV selects dev vs prod behaviour; the individual service settings
    (database, storage, Qdrant, Cognito) are switched purely by their values,
    not by branching on the environment in application code.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"

    cors_origins: str = "http://localhost:3000"

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/app"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "source_chunks"

    storage_backend: Literal["local", "s3"] = "local"
    local_storage_dir: str = "/data/sources"
    s3_bucket: str | None = None

    max_upload_mb: int = 25

    aws_region: str = "eu-central-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None
    cognito_client_secret: str | None = None

    guest_token_secret: str = "change-me-in-prod"
    guest_token_ttl_minutes: int = 720

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    # Second selectable OpenAI chat model (offered in Settings alongside the default).
    openai_alt_model: str | None = "gpt-5.4-mini"
    openai_alt_label: str = "gpt-5.4-mini"

    # Citation metadata lookup at ingestion (arXiv/Crossref). Disable in tests/offline.
    citation_lookup_enabled: bool = True
    citation_lookup_timeout: float = 10.0

    rag_top_k: int = 8
    rag_min_score: float = 0.2
    chat_history_limit: int = 12
    moderation_model: str = "omni-moderation-latest"

    # Abuse guardrails (see app/core/ratelimit.py for the per-scope limit table).
    # The chat message size cap lives on the MessageCreate schema (max_length).
    rate_limit_enabled: bool = True
    rate_limit_backend: Literal["db", "memory"] = "db"
    global_daily_agent_runs: int = 2000  # app-wide circuit breaker on LLM runs/day

    @model_validator(mode="after")
    def _validate_prod_secrets(self) -> "Settings":
        """Fail fast in prod if security-critical secrets are missing or left at defaults."""
        if self.app_env != "prod":
            return self
        problems: list[str] = []
        if self.guest_token_secret == "change-me-in-prod":
            problems.append("GUEST_TOKEN_SECRET must be set to a strong, unique value")
        if not self.openai_api_key:
            problems.append("OPENAI_API_KEY is required")
        if not (self.cognito_user_pool_id and self.cognito_client_id):
            problems.append("COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID are required")
        if "localhost" in self.database_url or "127.0.0.1" in self.database_url:
            problems.append("DATABASE_URL must not point at localhost in prod")
        if problems:
            raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def cognito_jwks_url(self) -> str:
        return (
            f"https://cognito-idp.{self.aws_region}.amazonaws.com/"
            f"{self.cognito_user_pool_id}/.well-known/jwks.json"
        )

    @property
    def cognito_issuer(self) -> str:
        return f"https://cognito-idp.{self.aws_region}.amazonaws.com/{self.cognito_user_pool_id}"

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from typing import Literal

from pydantic import Field
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

    storage_backend: Literal["local", "s3"] = "local"
    local_storage_dir: str = "/data/sources"
    s3_bucket: str | None = None

    aws_region: str = "eu-central-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None
    cognito_client_secret: str | None = None

    guest_token_secret: str = "change-me-in-prod"
    guest_token_ttl_minutes: int = 720

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

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

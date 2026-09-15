"""Server-only configuration for the central OSINTXZ Registry Backend.

This module deliberately does not import ``app.core.config``.  Desktop settings
and Registry Backend infrastructure settings are separate deployment domains.
For local development, backend settings may fall back to the existing generic
POSTGRES_* values from ``.env``; production can override them with dedicated
REGISTRY_BACKEND_* read and ingestion credentials in ``.env.registry-backend``.
"""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RegistryBackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.registry-backend"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = Field(
        default="development",
        validation_alias=AliasChoices(
            "REGISTRY_BACKEND_ENVIRONMENT",
            "ENVIRONMENT",
        ),
    )
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "REGISTRY_BACKEND_DEBUG",
            "DEBUG",
        ),
    )
    host: str = Field(
        default="127.0.0.1",
        validation_alias="REGISTRY_BACKEND_HOST",
    )
    port: int = Field(
        default=8011,
        validation_alias="REGISTRY_BACKEND_PORT",
    )
    api_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "REGISTRY_BACKEND_API_TOKEN",
            "REGISTRY_API_TOKEN",
        ),
    )

    postgres_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices(
            "REGISTRY_BACKEND_POSTGRES_HOST",
            "POSTGRES_HOST",
        ),
    )
    postgres_port: int = Field(
        default=5432,
        validation_alias=AliasChoices(
            "REGISTRY_BACKEND_POSTGRES_PORT",
            "POSTGRES_PORT",
        ),
    )
    postgres_db: str = Field(
        default="intelligence",
        validation_alias=AliasChoices(
            "REGISTRY_BACKEND_POSTGRES_DB",
            "POSTGRES_DB",
        ),
    )

    # API/read path. Production should grant this role SELECT only.
    read_postgres_user: str = Field(
        default="intelligence",
        validation_alias=AliasChoices(
            "REGISTRY_BACKEND_READ_POSTGRES_USER",
            "REGISTRY_BACKEND_POSTGRES_USER",
            "POSTGRES_USER",
        ),
    )
    read_postgres_password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "REGISTRY_BACKEND_READ_POSTGRES_PASSWORD",
            "REGISTRY_BACKEND_POSTGRES_PASSWORD",
            "POSTGRES_PASSWORD",
        ),
    )

    # Ingestion path. Production should grant INSERT/UPDATE/DELETE/COPY only to
    # this role and never expose these credentials to desktop clients.
    ingest_postgres_user: str = Field(
        default="intelligence",
        validation_alias=AliasChoices(
            "REGISTRY_BACKEND_INGEST_POSTGRES_USER",
            "REGISTRY_BACKEND_POSTGRES_USER",
            "POSTGRES_USER",
        ),
    )
    ingest_postgres_password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "REGISTRY_BACKEND_INGEST_POSTGRES_PASSWORD",
            "REGISTRY_BACKEND_POSTGRES_PASSWORD",
            "POSTGRES_PASSWORD",
        ),
    )

    @field_validator("port", "postgres_port")
    @classmethod
    def _positive_port(cls, value: int) -> int:
        value = int(value)
        if not (1 <= value <= 65535):
            raise ValueError("port must be between 1 and 65535")
        return value

    @property
    def read_database_url(self) -> str:
        return self._database_url(
            user=self.read_postgres_user,
            password=self.read_postgres_password,
            role="read",
        )

    @property
    def ingestion_database_url(self) -> str:
        return self._database_url(
            user=self.ingest_postgres_user,
            password=self.ingest_postgres_password,
            role="ingestion",
        )

    def _database_url(
        self,
        *,
        user: str,
        password: SecretStr | None,
        role: str,
    ) -> str:
        username = (user or "").strip()
        if not username:
            raise RuntimeError(f"Registry Backend {role} database user is not configured.")
        if password is None or not password.get_secret_value():
            raise RuntimeError(
                f"Registry Backend {role} database password is not configured."
            )
        return (
            "postgresql+psycopg://"
            f"{quote_plus(username)}:"
            f"{quote_plus(password.get_secret_value())}@"
            f"{self.postgres_host}:"
            f"{self.postgres_port}/"
            f"{quote_plus(self.postgres_db)}"
        )

    def api_token_value(self) -> str | None:
        if self.api_token is None:
            return None
        value = self.api_token.get_secret_value().strip()
        return value or None


@lru_cache(maxsize=1)
def get_registry_backend_settings() -> RegistryBackendSettings:
    return RegistryBackendSettings()


backend_settings = get_registry_backend_settings()

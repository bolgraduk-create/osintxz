"""
Global application configuration.

This module is the single source of truth for the entire project.
Every module must obtain configuration only through `settings`.

Do not read environment variables directly anywhere else.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


# ==========================================================
# Project paths
# ==========================================================

BASE_DIR = Path(__file__).resolve().parents[2]

APP_DIR = BASE_DIR / "app"

DATA_DIR = BASE_DIR / "storage"

CACHE_DIR = BASE_DIR / "cache"

EXPORT_DIR = BASE_DIR / "exports"

LOG_DIR = BASE_DIR / "logs"

TEMP_DIR = BASE_DIR / "storage" / "temp"

MEDIA_DIR = BASE_DIR / "storage" / "media"

DOCUMENTS_DIR = BASE_DIR / "storage" / "documents"


class Settings(BaseSettings):
    """
    Global immutable application settings.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ======================================================
    # Application
    # ======================================================

    app_name: str = Field(default="Intelligence Platform")

    app_version: str = Field(default="0.1.0")

    environment: str = Field(default="development")

    debug: bool = Field(default=True)

    # ======================================================
    # Security
    # ======================================================

    secret_key: SecretStr

    access_token_expire_minutes: int = 1440

    # ======================================================
    # API
    # ======================================================

    host: str = "0.0.0.0"

    port: int = 8000

    # ======================================================
    # PostgreSQL
    # ======================================================

    postgres_host: str

    postgres_port: int

    postgres_db: str

    postgres_user: str

    postgres_password: SecretStr



    # ======================================================
    # OSINT API Keys
    # ======================================================

    abuseipdb_api_key: str | None = None

    otx_api_key: str | None = None

    greynoise_api_key: str | None = None

    haveibeenpwned_api_key: str | None = None

    hybrid_analysis_api_key: str | None = None

    intelligencex_api_key: str | None = None

    urlscan_api_key: str | None = None

    virustotal_api_key: str | None = None

    # ======================================================
    # Redis
    # ======================================================

    redis_host: str

    redis_port: int

    # ======================================================
    # Ollama
    # ======================================================

    ollama_host: str

    default_model: str

    # ======================================================
    # Storage
    # ======================================================

    storage_path: str = "storage"

    export_path: str = "exports"

    cache_path: str = "cache"

    # ======================================================
    # URLs
    # ======================================================

    @property
    def database_url(self) -> str:
        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:"
            f"{self.postgres_port}/"
            f"{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def ollama_url(self) -> str:
        return self.ollama_host.rstrip("/")

    # ======================================================
    # Directories
    # ======================================================

    def create_directories(self) -> None:
        """
        Creates every required directory for the application.
        Safe to call multiple times.
        """

        directories = [
            DATA_DIR,
            CACHE_DIR,
            EXPORT_DIR,
            LOG_DIR,
            TEMP_DIR,
            MEDIA_DIR,
            DOCUMENTS_DIR,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns singleton application settings.
    """

    settings = Settings()

    settings.create_directories()

    return settings


settings = get_settings()
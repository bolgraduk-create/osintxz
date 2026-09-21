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

THUMBNAILS_DIR = (
    BASE_DIR
    / "storage"
    / "media"
    / "thumbnails"
)

PREVIEWS_DIR = (
    BASE_DIR
    / "storage"
    / "media"
    / "previews"
)

DOCUMENTS_DIR = BASE_DIR / "storage" / "documents"


# ==========================================================
# Bundled tools
# ==========================================================

TOOLS_DIR = BASE_DIR / "tools"

EXIFTOOL_DIR = (
    TOOLS_DIR
    / "exiftool"
)

EXIFTOOL_EXECUTABLE = (
    EXIFTOOL_DIR
    / "exiftool.exe"
)


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

    app_name: str = Field(
        default="Intelligence Platform"
    )

    app_version: str = Field(
        default="0.1.0"
    )

    environment: str = Field(
        default="development"
    )

    debug: bool = Field(
        default=True
    )

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
    # Central Registry Backend
    # ======================================================

    # Desktop-facing endpoint.  Public deployments must use HTTPS.  Plain HTTP
    # is accepted by the Registry API client only for localhost development.
    registry_api_url: str = "http://127.0.0.1:8011"

    registry_api_timeout: int = 20

    # Transitional service token for development/private deployments.  Final
    # public authentication is owned by the IAM stage and must not rely on an
    # embedded static desktop secret.
    registry_api_token: SecretStr | None = None

    # ASGI bind address used when this repository is deployed as Registry
    # Backend infrastructure.  End-user desktop installations do not need to
    # run this service.
    registry_backend_host: str = "127.0.0.1"

    registry_backend_port: int = 8011

    # ======================================================
    # External Registry Credentials
    # ======================================================

    # Optional. OpenCorporates currently requires an API token.
    # If absent, the provider remains registered but is blocked by the
    # existing RegistryQueryRouter credential-access policy.
    opencorporates_api_token: SecretStr | None = None

    # Optional token for CourtListener API v4 automatic access.
    courtlistener_api_token: SecretStr | None = None

    # ======================================================
    # UK Companies House
    # ======================================================

    # Optional official Companies House Public Data API key.
    # Without it, the provider remains registered but the existing
    # RegistryQueryRouter blocks automatic execution.
    companies_house_api_key: SecretStr | None = None


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

    abuseipdb_api_key: SecretStr | None = None

    otx_api_key: SecretStr | None = None

    greynoise_api_key: str | None = None

    haveibeenpwned_api_key: str | None = None


    # ======================================================
    # Dark Web / Tor
    # ======================================================

    # Local Tor SOCKS endpoint only. R13.7 never falls back to a direct
    # internet connection when a .onion request cannot be completed.
    darkweb_tor_socks_proxy: str = "socks5h://127.0.0.1:9050"

    hybrid_analysis_api_key: str | None = None

    intelligencex_api_key: str | None = None
    # Use the API instance assigned to your Intelligence X account/license.
    intelligencex_api_url: str = "https://2.intelx.io"
    # Optional token used only for repository-scoped GitHub Secret Scanning.
    # The adapter always requests hide_secret=true and requires verified_scope.
    github_secret_scanning_token: str | None = None

    # R13.15 — optional free/public API keys. All adapters work without these
    # values; keys only increase quota where the upstream service supports it.
    nvd_api_key: str | None = None
    openfda_api_key: str | None = None
    fec_api_key: str | None = None

    openalex_api_key: str | None = None
    sam_gov_api_key: str | None = None
    trade_gov_api_key: str | None = None
    sec_edgar_user_agent: str | None = None
    abn_lookup_guid: str | None = None
    canada_corporations_api_key: str | None = None
    uk_charity_commission_api_key: str | None = None
    poland_regon_api_key: str | None = None

    urlscan_api_key: SecretStr | None = None

    virustotal_api_key: SecretStr | None = None

    # Brave Search credentials are optional and remain disabled by default.
    brave_search_api_key: SecretStr | None = None

    # ======================================================
    # Redis
    # ======================================================

    redis_host: str

    redis_port: int

    # ======================================================
    # AI Analysis Provider
    # ======================================================

    # Generation/reasoning provider used by the investigation analysis stack.
    # Embeddings remain independently configured and may continue to use
    # Ollama even when AI analysis uses OpenAI.
    ai_provider: str = "ollama"

    # OpenAI API credentials/configuration. The secret is read from the local
    # environment/.env only and must never be exposed through desktop payloads.
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.6"
    openai_reasoning_effort: str = "medium"
    openai_timeout_seconds: float = 120.0
    openai_store_responses: bool = False

    # Legacy/local model selectors remain centralized here for compatibility.
    # OPENAI ignores these values; they apply only to Ollama.
    ai_model: str | None = None
    ollama_model: str | None = None

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
    def database_url(
        self,
    ) -> str:
        """
        Return SQLAlchemy PostgreSQL connection URL.
        """

        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:"
            f"{self.postgres_port}/"
            f"{self.postgres_db}"
        )

    @property
    def redis_url(
        self,
    ) -> str:
        """
        Return Redis connection URL.
        """

        return (
            f"redis://"
            f"{self.redis_host}:"
            f"{self.redis_port}"
        )

    @property
    def ollama_url(
        self,
    ) -> str:
        """
        Return normalized Ollama URL.
        """

        return self.ollama_host.rstrip(
            "/"
        )

    # ======================================================
    # Directories
    # ======================================================

    def create_directories(
        self,
    ) -> None:
        """
        Create every required application directory.

        Safe to call multiple times.
        """

        directories = [
            DATA_DIR,
            CACHE_DIR,
            EXPORT_DIR,
            LOG_DIR,
            TEMP_DIR,
            MEDIA_DIR,
            THUMBNAILS_DIR,
            PREVIEWS_DIR,
            DOCUMENTS_DIR,
            TOOLS_DIR,
            EXIFTOOL_DIR,
        ]

        for directory in directories:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )


@lru_cache(
    maxsize=1
)
def get_settings(
) -> Settings:
    """
    Return singleton application settings.
    """

    application_settings = Settings()

    application_settings.create_directories()

    return application_settings


settings = get_settings()

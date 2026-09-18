from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IntelligenceSourceCategory(str, Enum):
    REGISTRY = "registry"
    OPEN_DATA = "open_data"
    WEB_OSINT = "web_osint"
    ARCHIVE = "archive"
    BREACH_INTELLIGENCE = "breach_intelligence"
    DARK_WEB = "dark_web"
    THREAT_INTELLIGENCE = "threat_intelligence"
    SANCTIONS = "sanctions"
    PROCUREMENT = "procurement"
    FINANCIAL = "financial"
    SECURITIES = "securities"
    ACADEMIC = "academic"
    CHARITY = "charity"
    PROFESSIONAL = "professional"
    PROPERTY = "property"
    PUBLIC_OFFICIAL = "public_official"


class IntelligenceTransport(str, Enum):
    REST = "rest"
    SOAP = "soap"
    GRAPHQL = "graphql"
    SPARQL = "sparql"
    PUBLIC_HTTP = "public_http"
    TOR_HTTP = "tor_http"
    CONNECTOR = "connector"
    REMOTE_BACKEND = "remote_backend"


class IntelligenceAccessMode(str, Enum):
    NO_AUTH = "no_auth"
    FREE_API_KEY = "free_api_key"
    FREE_ACCOUNT = "free_account"
    VERIFIED_SCOPE = "verified_scope"
    MANUAL_ASSISTED = "manual_assisted"
    CONTRACT = "contract"
    PAID = "paid"
    RESTRICTED = "restricted"


class IntelligenceCost(str, Enum):
    FREE = "free"
    MIXED = "mixed"
    PAID = "paid"
    UNKNOWN = "unknown"


class IntelligenceDeliveryMode(str, Enum):
    REMOTE_QUERY = "remote_query"
    HYBRID = "hybrid"
    BULK_ONLY = "bulk_only"


class IntelligenceSourceOrigin(str, Enum):
    OFFICIAL_API = "official_api"
    OFFICIAL_OPEN_DATA = "official_open_data"
    OFFICIAL_PORTAL = "official_portal"
    CONTRACT_API = "contract_api"
    AGGREGATOR = "aggregator"
    COMMUNITY_INDEX = "community_index"
    BREACH_PROVIDER = "breach_provider"
    DARKWEB_PUBLICATION = "darkweb_publication"
    USER_AUTHORIZED_DATASET = "user_authorized_dataset"
    OTHER = "other"


class DataSensitivity(str, Enum):
    PUBLIC = "public"
    PUBLIC_SENSITIVE = "public_sensitive"
    BREACH_METADATA = "breach_metadata"
    DARKWEB_PUBLIC = "darkweb_public"
    RESTRICTED = "restricted"
    SECRET_MATERIAL = "secret_material"
    PROHIBITED = "prohibited"


@dataclass(frozen=True, slots=True)
class DataHandlingDecision:
    ingest_allowed: bool
    persist_allowed: bool
    analyze_allowed: bool
    display_allowed: bool
    export_allowed: bool
    redact_value: bool
    reason: str


@dataclass(frozen=True, slots=True)
class IntelligenceSourceDescriptor:
    """
    Declarative metadata for one remotely queryable intelligence source.

    This object does not execute the source. Existing Registry providers and
    OSINT connectors remain responsible for execution.
    """

    code: str
    display_name: str
    categories: frozenset[IntelligenceSourceCategory]
    capabilities: frozenset[str]
    transport: IntelligenceTransport
    access_mode: IntelligenceAccessMode
    cost: IntelligenceCost = IntelligenceCost.FREE
    delivery_mode: IntelligenceDeliveryMode = IntelligenceDeliveryMode.REMOTE_QUERY
    origin: IntelligenceSourceOrigin = IntelligenceSourceOrigin.OTHER

    countries: frozenset[str] = field(default_factory=frozenset)
    global_scope: bool = False

    requires_credentials: bool = False
    default_enabled: bool = False
    remote_query_supported: bool = True
    bulk_download_required: bool = False

    default_sensitivity: DataSensitivity = DataSensitivity.PUBLIC
    raw_secret_storage_allowed: bool = False
    redistribution_allowed: bool = False

    documentation_url: str | None = None
    terms_url: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        code = self.code.strip().casefold()
        if not code:
            raise ValueError("Intelligence source code must not be empty.")
        object.__setattr__(self, "code", code)

        display_name = self.display_name.strip()
        if not display_name:
            raise ValueError("Intelligence source display_name must not be empty.")
        object.__setattr__(self, "display_name", display_name)

        if not self.categories:
            raise ValueError("Intelligence source must declare at least one category.")
        if not self.capabilities:
            raise ValueError("Intelligence source must declare at least one capability.")

        capabilities = frozenset(
            item.strip().casefold()
            for item in self.capabilities
            if item and item.strip()
        )
        if not capabilities:
            raise ValueError("Intelligence source capabilities must not be empty.")
        object.__setattr__(self, "capabilities", capabilities)

        countries = frozenset(
            item.strip().upper()
            for item in self.countries
            if item and item.strip()
        )
        if any(len(code) != 2 or not code.isalpha() for code in countries):
            raise ValueError("Source countries must use ISO alpha-2 codes.")
        object.__setattr__(self, "countries", countries)

        if not self.global_scope and not countries:
            raise ValueError(
                "A non-global source must declare at least one country."
            )

        if (
            self.delivery_mode is IntelligenceDeliveryMode.BULK_ONLY
            and self.remote_query_supported
        ):
            raise ValueError(
                "A BULK_ONLY source cannot declare remote_query_supported=True."
            )

        if self.bulk_download_required and self.remote_query_supported:
            raise ValueError(
                "Sources requiring a bulk download cannot be remote-query sources."
            )

        if self.raw_secret_storage_allowed:
            raise ValueError(
                "Federation Core forbids raw secret storage in ordinary sources."
            )

    def supports_country(self, country: str | None) -> bool:
        if self.global_scope or country is None:
            return True
        return country.strip().upper() in self.countries

    def supports_capability(self, capability: str) -> bool:
        return capability.strip().casefold() in self.capabilities

    def automatic_eligible(
        self,
        *,
        credentials_available: bool = False,
        verified_scope: bool = False,
    ) -> bool:
        if not self.default_enabled:
            return False
        if not self.remote_query_supported:
            return False
        if self.delivery_mode is IntelligenceDeliveryMode.BULK_ONLY:
            return False
        if self.bulk_download_required:
            return False
        if self.cost is IntelligenceCost.PAID:
            return False

        if self.access_mode is IntelligenceAccessMode.NO_AUTH:
            return True

        if self.access_mode in {
            IntelligenceAccessMode.FREE_API_KEY,
            IntelligenceAccessMode.FREE_ACCOUNT,
        }:
            return credentials_available

        if self.access_mode is IntelligenceAccessMode.VERIFIED_SCOPE:
            return credentials_available and verified_scope

        return False

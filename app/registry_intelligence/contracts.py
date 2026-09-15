from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RegistryDomain(str, Enum):
    BUSINESS = "business"
    COURT = "court"
    PROCUREMENT = "procurement"
    LEGAL = "legal"
    INSOLVENCY = "insolvency"
    PROPERTY = "property"
    ENFORCEMENT = "enforcement"
    PUBLIC_OFFICIAL = "public_official"
    WANTED = "wanted"


class RegistryEntityKind(str, Enum):
    COMPANY = "company"
    SOLE_TRADER = "sole_trader"
    PERSON = "person"
    LEGAL_ENTITY = "legal_entity"
    COURT_CASE = "court_case"
    COURT_DECISION = "court_decision"
    INSOLVENCY = "insolvency"
    PROPERTY_RECORD = "property_record"
    ENFORCEMENT_RECORD = "enforcement_record"
    PUBLIC_OFFICIAL = "public_official"
    WANTED_PERSON = "wanted_person"


class RegistryQueryKind(str, Enum):
    NAME = "name"
    PERSON_NAME = "person_name"
    REGISTRATION_ID = "registration_id"
    LEI = "lei"
    TAX_ID = "tax_id"
    VAT_ID = "vat_id"
    CASE_NUMBER = "case_number"
    PHONE = "phone"
    EMAIL = "email"
    ADDRESS = "address"


class RegistryAccessMode(str, Enum):
    """How a registry source may be accessed by the application."""

    API = "api"
    PUBLIC_AUTOMATED = "public_automated"
    MANUAL_ASSISTED = "manual_assisted"
    RESTRICTED = "restricted"


class RegistrySourceType(str, Enum):
    OFFICIAL_OPEN_DATA = "official_open_data"
    OFFICIAL_API = "official_api"
    OFFICIAL_PORTAL = "official_portal"
    CONTRACT_API = "contract_api"
    AGGREGATOR = "aggregator"


class RegistryResultStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NOT_SUPPORTED = "not_supported"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RegistryProviderInfo:
    name: str
    display_name: str
    domains: frozenset[RegistryDomain]
    query_kinds: frozenset[RegistryQueryKind]
    countries: frozenset[str] = field(default_factory=frozenset)
    global_scope: bool = False
    public_data_only: bool = True
    requires_credentials: bool = False
    default_enabled: bool = False
    priority: int = 100
    access_mode: RegistryAccessMode = RegistryAccessMode.PUBLIC_AUTOMATED
    source_type: RegistrySourceType = RegistrySourceType.OFFICIAL_OPEN_DATA
    trust_score: float = 0.8
    sensitive_legal_data: bool = False

    def __post_init__(self) -> None:
        normalized_name = self.name.strip().casefold()
        if not normalized_name:
            raise ValueError("Registry provider name must not be empty.")
        object.__setattr__(self, "name", normalized_name)

        display_name = self.display_name.strip()
        if not display_name:
            raise ValueError("Registry provider display_name must not be empty.")
        object.__setattr__(self, "display_name", display_name)

        countries = frozenset(code.strip().upper() for code in self.countries if code.strip())
        if any(len(code) != 2 or not code.isalpha() for code in countries):
            raise ValueError("Registry provider countries must use ISO alpha-2 codes.")
        object.__setattr__(self, "countries", countries)

        if not 0.0 <= float(self.trust_score) <= 1.0:
            raise ValueError("Registry provider trust_score must be within 0..1.")

    @property
    def automatic_eligible(self) -> bool:
        return (
            self.default_enabled
            and self.public_data_only
            and not self.requires_credentials
            and self.access_mode in {
                RegistryAccessMode.API,
                RegistryAccessMode.PUBLIC_AUTOMATED,
            }
        )


@dataclass(frozen=True, slots=True)
class RegistryQuery:
    domain: RegistryDomain
    kind: RegistryQueryKind
    value: str
    country: str | None = None
    limit: int = 20
    timeout: int = 30
    sources: tuple[str, ...] = ()
    entity_kind: RegistryEntityKind | None = None

    def __post_init__(self) -> None:
        value = self.value.strip()
        if not value:
            raise ValueError("RegistryQuery value must not be empty.")
        object.__setattr__(self, "value", value)

        if not 1 <= self.limit <= 100:
            raise ValueError("RegistryQuery limit must be between 1 and 100.")
        if self.timeout < 1:
            raise ValueError("RegistryQuery timeout must be positive.")

        if self.country is not None:
            code = self.country.strip().upper()
            if len(code) != 2 or not code.isalpha():
                raise ValueError("RegistryQuery country must be ISO alpha-2.")
            object.__setattr__(self, "country", code)

        normalized_sources = tuple(
            dict.fromkeys(
                source.strip().casefold()
                for source in self.sources
                if source and source.strip()
            )
        )
        object.__setattr__(self, "sources", normalized_sources)


@dataclass(slots=True)
class RegistryRecord:
    provider: str
    domain: RegistryDomain
    record_id: str
    display_name: str
    country: str | None = None
    jurisdiction: str | None = None
    status: str | None = None
    registration_id: str | None = None
    lei: str | None = None
    legal_form: str | None = None
    legal_address: str | None = None
    headquarters_address: str | None = None
    source_url: str | None = None
    confidence: float = 0.8
    reliability: float = 0.8
    identifiers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    entity_kind: RegistryEntityKind = RegistryEntityKind.LEGAL_ENTITY
    source_type: RegistrySourceType = RegistrySourceType.OFFICIAL_OPEN_DATA
    trust_score: float = 0.8
    retrieved_at: str | None = None
    raw_reference: str | None = None
    sensitive_legal_data: bool = False

    def __post_init__(self) -> None:
        self.provider = self.provider.strip().casefold()
        self.record_id = self.record_id.strip()
        self.display_name = self.display_name.strip()
        if not self.provider or not self.record_id or not self.display_name:
            raise ValueError("RegistryRecord provider, record_id and display_name are required.")

        if self.country is not None:
            country = self.country.strip().upper()
            if len(country) != 2 or not country.isalpha():
                raise ValueError("RegistryRecord country must be ISO alpha-2.")
            self.country = country

        for value, field_name in (
            (self.confidence, "confidence"),
            (self.reliability, "reliability"),
            (self.trust_score, "trust_score"),
        ):
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"RegistryRecord {field_name} must be within 0..1.")

        if self.retrieved_at is None:
            self.retrieved_at = datetime.now(timezone.utc).isoformat()
        if self.raw_reference is None:
            self.raw_reference = self.record_id

    @property
    def identity_key(self) -> tuple[str, str]:
        return (self.provider.strip().casefold(), self.record_id.strip().casefold())


@dataclass(slots=True)
class RegistryProviderResult:
    provider: str
    status: RegistryResultStatus
    records: list[RegistryRecord] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.status in {RegistryResultStatus.SUCCESS, RegistryResultStatus.PARTIAL}


@dataclass(slots=True)
class RegistrySearchResult:
    query: RegistryQuery
    provider_results: list[RegistryProviderResult] = field(default_factory=list)
    records: list[RegistryRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

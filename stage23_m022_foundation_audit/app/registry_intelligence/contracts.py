from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class RegistryDomain(str, Enum):
    BUSINESS = "business"
    COURT = "court"
    PROCUREMENT = "procurement"
    LEGAL = "legal"

class RegistryQueryKind(str, Enum):
    NAME = "name"
    REGISTRATION_ID = "registration_id"
    LEI = "lei"
    TAX_ID = "tax_id"
    PHONE = "phone"
    EMAIL = "email"
    ADDRESS = "address"

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

    @property
    def automatic_eligible(self) -> bool:
        return self.public_data_only and not self.requires_credentials and self.default_enabled

@dataclass(frozen=True, slots=True)
class RegistryQuery:
    domain: RegistryDomain
    kind: RegistryQueryKind
    value: str
    country: str | None = None
    limit: int = 20
    timeout: int = 30

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("RegistryQuery value must not be empty.")
        if not 1 <= self.limit <= 100:
            raise ValueError("RegistryQuery limit must be between 1 and 100.")
        if self.timeout < 1:
            raise ValueError("RegistryQuery timeout must be positive.")
        if self.country is not None:
            code = self.country.strip().upper()
            if len(code) != 2 or not code.isalpha():
                raise ValueError("RegistryQuery country must be ISO alpha-2.")

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

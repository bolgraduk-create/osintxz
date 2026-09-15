"""Declarative registry-source coverage catalog used by country plugins."""
from __future__ import annotations

from dataclasses import dataclass

from app.registry_intelligence.contracts import (
    RegistryAccessMode,
    RegistryDomain,
    RegistryQueryKind,
    RegistrySourceType,
)


@dataclass(frozen=True, slots=True)
class RegistrySourceDescriptor:
    code: str
    display_name: str
    country: str
    domains: frozenset[RegistryDomain]
    query_kinds: frozenset[RegistryQueryKind]
    access_mode: RegistryAccessMode
    source_type: RegistrySourceType
    trust_score: float
    public_data_only: bool
    requires_credentials: bool
    sensitive_legal_data: bool = False
    default_enabled: bool = False
    implementation_status: str = "planned"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("Registry source code must not be empty.")
        if len(self.country.strip()) != 2 or not self.country.strip().isalpha():
            raise ValueError("Registry source country must be ISO alpha-2.")
        if not 0.0 <= float(self.trust_score) <= 1.0:
            raise ValueError("Registry source trust_score must be within 0..1.")
        if not self.domains:
            raise ValueError("Registry source must declare at least one domain.")
        if not self.query_kinds:
            raise ValueError("Registry source must declare at least one query kind.")

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

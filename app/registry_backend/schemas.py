from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
)


class RegistryQueryRequest(BaseModel):
    domain: RegistryDomain
    kind: RegistryQueryKind
    value: str = Field(min_length=1, max_length=2048)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    limit: int = Field(default=20, ge=1, le=100)
    timeout: int = Field(default=20, ge=1, le=30)
    sources: list[str] = Field(default_factory=list, max_length=16)
    entity_kind: RegistryEntityKind | None = None

    @field_validator("value")
    @classmethod
    def normalize_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("country must be ISO alpha-2")
        return normalized

    def to_contract(self) -> RegistryQuery:
        return RegistryQuery(
            domain=self.domain,
            kind=self.kind,
            value=self.value,
            country=self.country,
            limit=self.limit,
            timeout=self.timeout,
            sources=tuple(self.sources),
            entity_kind=self.entity_kind,
        )

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RemoteAdapterStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NOT_CONFIGURED = "not_configured"
    NOT_SUPPORTED = "not_supported"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RemoteSourceQuery:
    capability: str
    value: str
    country: str | None = None
    limit: int = 20
    timeout: int = 30
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        value = self.value.strip()
        if not value:
            raise ValueError("RemoteSourceQuery value must not be empty.")
        object.__setattr__(self, "value", value)

        capability = self.capability.strip().casefold()
        if not capability:
            raise ValueError("RemoteSourceQuery capability must not be empty.")
        object.__setattr__(self, "capability", capability)

        if not 1 <= self.limit <= 100:
            raise ValueError("RemoteSourceQuery limit must be 1..100.")

        if self.country is not None:
            country = self.country.strip().upper()
            if len(country) != 2 or not country.isalpha():
                raise ValueError("country must be ISO alpha-2.")
            object.__setattr__(self, "country", country)

        object.__setattr__(
            self,
            "sources",
            tuple(
                dict.fromkeys(
                    item.strip().casefold()
                    for item in self.sources
                    if item and item.strip()
                )
            ),
        )


@dataclass(slots=True)
class RemoteSourceRecord:
    source: str
    record_id: str
    record_type: str
    display_name: str
    source_url: str | None = None
    country: str | None = None
    identifiers: dict[str, str] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.source = self.source.strip().casefold()
        self.record_id = self.record_id.strip()
        self.record_type = self.record_type.strip().casefold()
        self.display_name = self.display_name.strip()
        if not all((self.source, self.record_id, self.record_type, self.display_name)):
            raise ValueError("RemoteSourceRecord core fields are required.")


@dataclass(slots=True)
class RemoteAdapterResult:
    source: str
    status: RemoteAdapterStatus
    records: list[RemoteSourceRecord] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.status in {
            RemoteAdapterStatus.SUCCESS,
            RemoteAdapterStatus.PARTIAL,
        }

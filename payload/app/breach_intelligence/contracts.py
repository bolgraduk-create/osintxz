from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BreachQueryKind(str, Enum):
    EMAIL = "email"
    PASSWORD = "password"


class BreachResultStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NOT_CONFIGURED = "not_configured"
    NOT_SUPPORTED = "not_supported"
    FAILED = "failed"


@dataclass(slots=True)
class BreachFinding:
    source: str
    record_id: str
    subject_type: str
    subject_value: str | None = None

    breach_name: str | None = None
    breach_title: str | None = None
    breach_domain: str | None = None
    breach_date: str | None = None
    added_date: str | None = None
    modified_date: str | None = None

    exposed_data_classes: tuple[str, ...] = ()
    password_exposed: bool = False
    occurrence_count: int | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.source = self.source.strip().casefold()
        self.record_id = self.record_id.strip()
        if not self.source or not self.record_id:
            raise ValueError("BreachFinding source and record_id are required.")

        if self.subject_type == "password":
            # Ordinary breach results never contain the queried password.
            self.subject_value = None


@dataclass(slots=True)
class BreachSearchResult:
    source: str
    kind: BreachQueryKind
    status: BreachResultStatus
    findings: list[BreachFinding] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

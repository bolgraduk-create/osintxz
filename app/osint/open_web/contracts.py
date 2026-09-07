"""M021.7 Open-Web Discovery core contracts.

These objects represent public web/index discovery leads before identifier
extraction. A WebDocument is not proof of identity or ownership.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.osint.models import OsintTargetType


class OpenWebStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_SUPPORTED = "not_supported"
    NOT_AVAILABLE = "not_available"


@dataclass(frozen=True, slots=True)
class OpenWebProviderInfo:
    name: str
    display_name: str
    supported_targets: frozenset[OsintTargetType]
    passive: bool = True
    public_data_only: bool = True
    requires_credentials: bool = False
    default_enabled: bool = False
    priority: int = 100

    @property
    def automatic_eligible(self) -> bool:
        return (
            self.passive
            and self.public_data_only
            and not self.requires_credentials
            and self.default_enabled
        )


@dataclass(frozen=True, slots=True)
class OpenWebQuery:
    target_type: OsintTargetType
    value: str
    case_id: str | None = None
    limit: int = 25
    timeout: int = 30
    depth: int = 0
    parent_entity_id: str | None = None

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("OpenWebQuery value must not be empty.")
        if self.limit < 1 or self.limit > 250:
            raise ValueError("OpenWebQuery limit must be between 1 and 250.")
        if self.timeout < 1:
            raise ValueError("OpenWebQuery timeout must be greater than zero.")
        if self.depth < 0:
            raise ValueError("OpenWebQuery depth must not be negative.")


@dataclass(slots=True)
class OpenWebDocument:
    url: str
    provider: str
    title: str | None = None
    snippet: str | None = None
    text: str | None = None
    captured_at: str | None = None
    content_type: str | None = None
    confidence: float = 0.5
    reliability: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def extraction_text(self) -> str:
        parts = [self.title or "", self.snippet or "", self.text or ""]
        return "\n".join(part.strip() for part in parts if part and part.strip())

    @property
    def identity_key(self) -> tuple[str, str]:
        return (self.provider.strip().casefold(), self.url.strip())


@dataclass(slots=True)
class OpenWebResult:
    provider: str
    status: OpenWebStatus
    documents: list[OpenWebDocument] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.status in {OpenWebStatus.SUCCESS, OpenWebStatus.PARTIAL}

    @property
    def total_documents(self) -> int:
        return len(self.documents)

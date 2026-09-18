from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DarkWebFetchStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    NOT_CONFIGURED = "not_configured"
    FAILED = "failed"


class DarkWebIndicatorKind(str, Enum):
    EMAIL = "email"
    DOMAIN = "domain"
    USERNAME = "username"
    ONION_URL = "onion_url"
    CLEARNET_URL = "clearnet_url"
    BITCOIN_ADDRESS = "bitcoin_address"
    ETHEREUM_ADDRESS = "ethereum_address"


@dataclass(frozen=True, slots=True)
class DarkWebIndicator:
    kind: DarkWebIndicatorKind
    value: str
    confidence: float = 0.8

    def __post_init__(self) -> None:
        value = self.value.strip()
        if not value:
            raise ValueError("Dark-web indicator value must not be empty.")
        object.__setattr__(self, "value", value)
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("Indicator confidence must be within 0..1.")


@dataclass(slots=True)
class DarkWebPageObservation:
    source_url: str
    status_code: int
    title: str | None
    content_sha256: str
    indicators: list[DarkWebIndicator] = field(default_factory=list)
    retrieved_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.retrieved_at is None:
            self.retrieved_at = datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class DarkWebFetchResult:
    status: DarkWebFetchStatus
    observation: DarkWebPageObservation | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

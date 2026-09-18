from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OnionDiscoveryStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    NOT_CONFIGURED = "not_configured"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class OnionDiscoveryRequest:
    seeds: tuple[str, ...]
    max_pages: int = 25
    max_depth: int = 2
    per_host_limit: int = 5
    max_links_per_page: int = 25
    timeout: int = 30
    require_ahmia_blocklist: bool = True

    def __post_init__(self) -> None:
        seeds = tuple(dict.fromkeys((item or "").strip() for item in self.seeds if (item or "").strip()))
        if not seeds:
            raise ValueError("At least one onion seed URL is required.")
        object.__setattr__(self, "seeds", seeds)
        if not 1 <= self.max_pages <= 100:
            raise ValueError("max_pages must be 1..100.")
        if not 0 <= self.max_depth <= 4:
            raise ValueError("max_depth must be 0..4.")
        if not 1 <= self.per_host_limit <= 20:
            raise ValueError("per_host_limit must be 1..20.")
        if not 1 <= self.max_links_per_page <= 100:
            raise ValueError("max_links_per_page must be 1..100.")
        if not 1 <= self.timeout <= 120:
            raise ValueError("timeout must be 1..120 seconds.")


@dataclass(slots=True)
class OnionDiscoveryPage:
    url: str
    depth: int
    status: OnionDiscoveryStatus
    title: str | None = None
    content_sha256: str | None = None
    discovered_onion_urls: tuple[str, ...] = ()
    indicator_count: int = 0
    indicators: tuple[dict[str, Any], ...] = ()
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OnionDiscoveryResult:
    request: OnionDiscoveryRequest
    status: OnionDiscoveryStatus
    pages: list[OnionDiscoveryPage] = field(default_factory=list)
    discovered_onion_urls: list[str] = field(default_factory=list)
    blocked_onion_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def fetched_pages(self) -> int:
        return sum(1 for page in self.pages if page.status is OnionDiscoveryStatus.SUCCESS)

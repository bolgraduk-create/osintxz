from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class GeoProviderStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class GeoPoint:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        latitude = float(self.latitude)
        longitude = float(self.longitude)
        if not -90.0 <= latitude <= 90.0:
            raise ValueError("latitude must be between -90 and 90.")
        if not -180.0 <= longitude <= 180.0:
            raise ValueError("longitude must be between -180 and 180.")
        object.__setattr__(self, "latitude", latitude)
        object.__setattr__(self, "longitude", longitude)


@dataclass(frozen=True, slots=True)
class GeoEnrichmentRequest:
    point: GeoPoint
    radius_m: int = 750
    historical_date: date | None = None
    poi_limit: int = 40
    timeout_seconds: int = 20

    def __post_init__(self) -> None:
        radius = int(self.radius_m)
        if not 100 <= radius <= 2_000:
            raise ValueError("radius_m must be 100..2000.")
        limit = int(self.poi_limit)
        if not 1 <= limit <= 100:
            raise ValueError("poi_limit must be 1..100.")
        timeout = int(self.timeout_seconds)
        if not 3 <= timeout <= 45:
            raise ValueError("timeout_seconds must be 3..45.")
        if self.historical_date is not None:
            if self.historical_date < date(1940, 1, 1):
                raise ValueError("Historical weather is available from 1940.")
            if self.historical_date > date.today():
                raise ValueError("historical_date cannot be in the future.")
        object.__setattr__(self, "radius_m", radius)
        object.__setattr__(self, "poi_limit", limit)
        object.__setattr__(self, "timeout_seconds", timeout)


@dataclass(slots=True)
class GeoProviderResult:
    source: str
    status: GeoProviderStatus
    records: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.status in {
            GeoProviderStatus.SUCCESS,
            GeoProviderStatus.PARTIAL,
        }

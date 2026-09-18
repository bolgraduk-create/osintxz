from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SourceImplementationStatus(str, Enum):
    ACTIVE = "active"
    EXISTING_CONNECTOR = "existing_connector"
    CATALOGED = "cataloged"
    MANUAL_ASSISTED = "manual_assisted"


@dataclass(frozen=True, slots=True)
class SourceCoverageEntry:
    source_code: str
    status: SourceImplementationStatus
    component_hint: str | None = None
    stage: str | None = None


class RemoteSourceCoverage:
    def __init__(self, entries: tuple[SourceCoverageEntry, ...]) -> None:
        seen: set[str] = set()
        normalized: list[SourceCoverageEntry] = []
        for entry in entries:
            code = entry.source_code.strip().casefold()
            if not code:
                raise ValueError("Coverage source_code must not be empty.")
            if code in seen:
                raise ValueError(f"Duplicate coverage source: {code}")
            seen.add(code)
            normalized.append(
                SourceCoverageEntry(
                    source_code=code,
                    status=entry.status,
                    component_hint=entry.component_hint,
                    stage=entry.stage,
                )
            )
        self._entries = tuple(normalized)

    def all(self) -> tuple[SourceCoverageEntry, ...]:
        return self._entries

    def by_status(
        self,
        status: SourceImplementationStatus,
    ) -> tuple[SourceCoverageEntry, ...]:
        return tuple(item for item in self._entries if item.status is status)

    def get(self, code: str) -> SourceCoverageEntry | None:
        key = (code or "").strip().casefold()
        return next((item for item in self._entries if item.source_code == key), None)

    def summary(self) -> dict[str, int]:
        out = {item.value: 0 for item in SourceImplementationStatus}
        for entry in self._entries:
            out[entry.status.value] += 1
        out["total"] = len(self._entries)
        return out

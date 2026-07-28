"""
OSINT result mapper.

Converts connector results into
objects understood by the platform.

Responsibilities:

- normalize connector output
- prepare evidence candidates
- prepare entity candidates

Does NOT:

- create database objects
- resolve duplicates
- save data
- call AI
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from app.osint.result import OsintFinding
from app.osint.result import OsintResult


@dataclass(slots=True)
class EntityCandidate:
    """
    Candidate entity extracted
    from OSINT.
    """

    entity_type: str

    value: str

    confidence: float

    source: str | None = None

    metadata: dict = field(
        default_factory=dict,
    )


@dataclass(slots=True)
class EvidenceCandidate:
    """
    Candidate evidence extracted
    from OSINT.
    """

    category: str

    value: str

    source: str | None = None

    url: str | None = None

    reliability: float = 1.0

    metadata: dict = field(
        default_factory=dict,
    )


@dataclass(slots=True)
class MappedOsintResult:
    """
    Normalized OSINT result.
    """

    connector: str

    entities: list[EntityCandidate] = field(
        default_factory=list,
    )

    evidence: list[EvidenceCandidate] = field(
        default_factory=list,
    )


class ResultMapper:
    """
    Maps connector output into
    platform candidates.
    """

    def map(
        self,
        result: OsintResult,
    ) -> MappedOsintResult:

        mapped = MappedOsintResult(
            connector=result.connector,
        )

        for finding in result.findings:

            self._map_finding(
                mapped,
                finding,
            )

        return mapped

    def _map_finding(
        self,
        mapped: MappedOsintResult,
        finding: OsintFinding,
    ) -> None:

        mapped.evidence.append(

            EvidenceCandidate(

                category=finding.category,

                value=finding.value,

                source=finding.source,

                url=finding.url,

                reliability=finding.reliability,

                metadata=finding.metadata,

            )

        )

        mapped.entities.append(

            EntityCandidate(

                entity_type=finding.category,

                value=finding.value,

                confidence=finding.confidence,

                source=finding.source,

                metadata=finding.metadata,

            )

        )
"""
M021.5 — Recursive OSINT pivot candidate policy.

Only normalized/persisted Entity objects may become recursive pivots.
Raw finding text/metadata is never pivoted directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.osint_enrichment_service import OsintTargetEnrichmentResult
from app.models.entity import Entity, EntityType
from app.osint.models import OsintTargetType


_ENTITY_TO_TARGET: dict[EntityType, OsintTargetType] = {
    EntityType.USERNAME: OsintTargetType.USERNAME,
    EntityType.EMAIL: OsintTargetType.EMAIL,
    EntityType.PHONE: OsintTargetType.PHONE,
    EntityType.DOMAIN: OsintTargetType.DOMAIN,
    EntityType.URL: OsintTargetType.URL,
    EntityType.IP: OsintTargetType.IP,
}


@dataclass(frozen=True, slots=True)
class RecursivePivotCandidate:
    entity_id: UUID
    entity_type: EntityType
    target_type: OsintTargetType
    value: str
    depth: int
    discovered_from_entity_id: UUID | None
    evidence_id: UUID | None

    @property
    def identity_key(self) -> tuple[OsintTargetType, str]:
        return (
            self.target_type,
            self.value.strip().casefold(),
        )


class OsintPivotCandidatePolicy:
    """
    Convert persisted Entity objects into safe automatic pivot candidates.

    This class never executes OSINT and never reads connector metadata.
    """

    def target_type_for_entity(
        self,
        entity_type: EntityType,
    ) -> OsintTargetType | None:
        return _ENTITY_TO_TARGET.get(entity_type)

    def is_supported_entity_type(
        self,
        entity_type: EntityType,
    ) -> bool:
        return entity_type in _ENTITY_TO_TARGET


    def from_persistence_results(
        self,
        persistence_results,
        *,
        next_depth: int,
        discovered_from_entity_id: UUID | None = None,
    ) -> tuple[RecursivePivotCandidate, ...]:
        """Build recursive candidates only from persisted Entity objects."""
        candidates: list[RecursivePivotCandidate] = []
        seen: set[tuple[UUID, OsintTargetType, str]] = set()

        for persistence_result in persistence_results:
            for persisted_finding in persistence_result.persisted:
                evidence_id = getattr(
                    persisted_finding.evidence,
                    "id",
                    None,
                )

                for entity in persisted_finding.entities:
                    candidate = self.from_entity(
                        entity,
                        depth=next_depth,
                        discovered_from_entity_id=discovered_from_entity_id,
                        evidence_id=evidence_id,
                    )

                    if candidate is None:
                        continue

                    key = (
                        candidate.entity_id,
                        candidate.target_type,
                        candidate.value.strip().casefold(),
                    )

                    if key in seen:
                        continue

                    seen.add(key)
                    candidates.append(candidate)

        return tuple(candidates)

    def from_enrichment_result(
        self,
        result: OsintTargetEnrichmentResult,
        *,
        next_depth: int,
    ) -> tuple[RecursivePivotCandidate, ...]:
        return self.from_persistence_results(
            result.persistence,
            next_depth=next_depth,
            discovered_from_entity_id=result.parent_entity_id,
        )

    def from_entity(
        self,
        entity: Entity,
        *,
        depth: int,
        discovered_from_entity_id: UUID | None = None,
        evidence_id: UUID | None = None,
    ) -> RecursivePivotCandidate | None:
        target_type = self.target_type_for_entity(
            entity.entity_type
        )
        if target_type is None:
            return None

        value = str(
            entity.normalized_value
            or entity.value
            or ""
        ).strip()
        if not value:
            return None

        return RecursivePivotCandidate(
            entity_id=entity.id,
            entity_type=entity.entity_type,
            target_type=target_type,
            value=value,
            depth=depth,
            discovered_from_entity_id=(
                discovered_from_entity_id
            ),
            evidence_id=evidence_id,
        )

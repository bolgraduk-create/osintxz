"""R14.3c relationship corroboration for identity candidates.

The service treats social-graph overlap as a supporting identity signal, never
as proof of ownership.  It keeps the original Entity.confidence untouched and
returns a separate effective confidence plus an explainable WHY payload.

A target PERSON linked to associate B and a candidate account independently
linked to the same B may increase confidence.  Shared provenance is suppressed
so one observation cannot confirm itself circularly.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import prod
from typing import Any
from uuid import UUID

from app.models.entity import EntityType


_TYPE_FACTORS: dict[str, float] = {
    "knows": 1.00,
    "messaged": 0.92,
    "contacted": 0.86,
    "called": 0.86,
    "emailed": 0.86,
    "related_to": 0.68,
    "member_of": 0.52,
    "owns": 0.45,
    "located_at": 0.35,
    "other": 0.45,
    "metadata_mention": 0.65,
}

_PROVENANCE_KEYS = (
    "evidence_id",
    "evidence_ids",
    "source_evidence_id",
    "supporting_evidence_id",
    "supporting_evidence_ids",
    "source_id",
    "source_ids",
    "finding_id",
    "message_id",
    "message_ids",
)


@dataclass(frozen=True, slots=True)
class RelationshipCorroborationSignal:
    associate_entity_id: str
    associate_label: str
    known_relationship_type: str
    candidate_relationship_type: str
    strength: float
    independent_lineage: bool
    known_provenance: tuple[str, ...]
    candidate_provenance: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "associateEntityId": self.associate_entity_id,
            "associateLabel": self.associate_label,
            "knownRelationshipType": self.known_relationship_type,
            "candidateRelationshipType": self.candidate_relationship_type,
            "strength": self.strength,
            "independentLineage": self.independent_lineage,
            "knownProvenance": list(self.known_provenance),
            "candidateProvenance": list(self.candidate_provenance),
            "why": (
                f"Both the person and candidate are independently linked to "
                f"{self.associate_label}."
                if self.independent_lineage
                else (
                    f"Both are linked to {self.associate_label}, but provenance "
                    "is incomplete, so the contribution is downweighted."
                )
            ),
        }


@dataclass(frozen=True, slots=True)
class RelationshipCorroborationResult:
    base_confidence: float
    effective_confidence: float
    support: float
    boost: float
    signals: tuple[RelationshipCorroborationSignal, ...] = ()
    suppressed_circular: int = 0

    @property
    def has_support(self) -> bool:
        return bool(self.signals) and self.boost > 0.0

    @property
    def summary(self) -> str:
        if not self.signals:
            if self.suppressed_circular:
                return "Relationship overlap found, but shared provenance was suppressed."
            return "No independent known-associate overlap was found."
        labels = ", ".join(signal.associate_label for signal in self.signals[:3])
        return (
            f"Known-associate corroboration: {labels}. "
            f"Effective confidence {self.base_confidence:.2f} -> "
            f"{self.effective_confidence:.2f}."
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "baseConfidence": self.base_confidence,
            "effectiveConfidence": self.effective_confidence,
            "support": self.support,
            "boost": self.boost,
            "signals": [signal.to_payload() for signal in self.signals],
            "suppressedCircular": self.suppressed_circular,
            "summary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class _AssociationObservation:
    associate_id: UUID
    relationship_type: str
    confidence: float
    provenance: frozenset[str]
    lineage_known: bool


class IdentityRelationshipCorroborationService:
    """Compare a candidate's social neighborhood with a known PERSON."""

    MAX_SOCIAL_SUPPORT = 0.45
    MAX_PER_ASSOCIATE_CONTRIBUTION = 0.25
    INCOMPLETE_LINEAGE_FACTOR = 0.55

    def __init__(
        self,
        *,
        relationship_service: Any,
        entity_service: Any,
    ) -> None:
        self.relationship_service = relationship_service
        self.entity_service = entity_service

    def assess(
        self,
        *,
        person: Any,
        candidate: Any,
        relationships: list[Any] | None = None,
        base_confidence: float | None = None,
    ) -> RelationshipCorroborationResult:
        self._validate(person=person, candidate=candidate)

        base = self._confidence(
            getattr(candidate, "confidence", 0.0)
            if base_confidence is None
            else base_confidence
        )

        case_relationships = list(
            relationships
            if relationships is not None
            else (
                self.relationship_service
                .get_case_relationships(
                    getattr(person, "case_id")
                )
                or []
            )
        )

        known = self._relationship_observations(
            entity_id=getattr(person, "id"),
            relationships=case_relationships,
            excluded_ids={
                getattr(person, "id"),
                getattr(candidate, "id"),
            },
        )
        observed = self._relationship_observations(
            entity_id=getattr(candidate, "id"),
            relationships=case_relationships,
            excluded_ids={
                getattr(person, "id"),
                getattr(candidate, "id"),
            },
        )

        observed.extend(
            self._metadata_observations(candidate)
        )

        known_by_associate = self._strongest_by_associate(known)
        candidate_by_associate = self._strongest_by_associate(observed)

        signals: list[RelationshipCorroborationSignal] = []
        suppressed_circular = 0

        for associate_id in sorted(
            set(known_by_associate) & set(candidate_by_associate),
            key=str,
        ):
            known_observation = known_by_associate[associate_id]
            candidate_observation = candidate_by_associate[associate_id]

            associate = self._person_entity(associate_id)
            if associate is None:
                continue

            shared_provenance = (
                known_observation.provenance
                & candidate_observation.provenance
            )

            if shared_provenance:
                suppressed_circular += 1
                continue

            independent_lineage = (
                known_observation.lineage_known
                and candidate_observation.lineage_known
            )
            lineage_factor = (
                1.0
                if independent_lineage
                else self.INCOMPLETE_LINEAGE_FACTOR
            )

            strength = (
                min(
                    known_observation.confidence,
                    candidate_observation.confidence,
                )
                * min(
                    self._type_factor(known_observation.relationship_type),
                    self._type_factor(candidate_observation.relationship_type),
                )
                * lineage_factor
            )
            strength = round(
                max(0.0, min(1.0, strength)),
                6,
            )

            if strength <= 0.0:
                continue

            signals.append(
                RelationshipCorroborationSignal(
                    associate_entity_id=str(associate_id),
                    associate_label=str(
                        getattr(associate, "value", "")
                        or associate_id
                    ),
                    known_relationship_type=(
                        known_observation.relationship_type
                    ),
                    candidate_relationship_type=(
                        candidate_observation.relationship_type
                    ),
                    strength=strength,
                    independent_lineage=independent_lineage,
                    known_provenance=tuple(
                        sorted(known_observation.provenance)
                    ),
                    candidate_provenance=tuple(
                        sorted(candidate_observation.provenance)
                    ),
                )
            )

        signals.sort(
            key=lambda signal: (
                -signal.strength,
                signal.associate_label.casefold(),
            )
        )

        contributions = [
            min(
                self.MAX_PER_ASSOCIATE_CONTRIBUTION,
                signal.strength
                * self.MAX_PER_ASSOCIATE_CONTRIBUTION,
            )
            for signal in signals
        ]

        support = (
            1.0 - prod(1.0 - value for value in contributions)
            if contributions
            else 0.0
        )
        support = round(
            min(self.MAX_SOCIAL_SUPPORT, support),
            6,
        )

        effective = round(
            base + (1.0 - base) * support,
            6,
        )
        boost = round(
            effective - base,
            6,
        )

        return RelationshipCorroborationResult(
            base_confidence=base,
            effective_confidence=effective,
            support=support,
            boost=boost,
            signals=tuple(signals),
            suppressed_circular=suppressed_circular,
        )

    def _relationship_observations(
        self,
        *,
        entity_id: UUID,
        relationships: list[Any],
        excluded_ids: set[Any],
    ) -> list[_AssociationObservation]:
        observations: list[_AssociationObservation] = []

        for relationship in relationships:
            source_id = getattr(
                relationship,
                "source_entity_id",
                None,
            )
            target_id = getattr(
                relationship,
                "target_entity_id",
                None,
            )

            if source_id == entity_id:
                associate_id = target_id
            elif target_id == entity_id:
                associate_id = source_id
            else:
                continue

            if (
                not isinstance(associate_id, UUID)
                or associate_id in excluded_ids
            ):
                continue

            metadata = self._metadata_dict(
                getattr(
                    relationship,
                    "metadata_json",
                    None,
                )
            )
            provenance = self._provenance_tokens(metadata)
            lineage_known = bool(provenance)

            observations.append(
                _AssociationObservation(
                    associate_id=associate_id,
                    relationship_type=self._relationship_type(
                        relationship
                    ),
                    confidence=self._confidence(
                        getattr(
                            relationship,
                            "confidence",
                            0.0,
                        )
                    ),
                    provenance=provenance,
                    lineage_known=lineage_known,
                )
            )

        return observations

    def _metadata_observations(
        self,
        candidate: Any,
    ) -> list[_AssociationObservation]:
        metadata = self._metadata_dict(
            getattr(candidate, "metadata_json", None)
        )
        provenance = self._provenance_tokens(metadata)
        values: list[Any] = []

        for key in (
            "related_entity_id",
            "related_entity_ids",
            "mentioned_entity_id",
            "mentioned_entity_ids",
            "associated_entity_ids",
            "known_associate_ids",
        ):
            raw = metadata.get(key)
            if isinstance(raw, (list, tuple, set, frozenset)):
                values.extend(raw)
            elif raw not in (None, ""):
                values.append(raw)

        observations: list[_AssociationObservation] = []
        seen: set[UUID] = set()

        for raw in values[:100]:
            try:
                associate_id = UUID(str(raw))
            except (TypeError, ValueError, AttributeError):
                continue

            if associate_id in seen:
                continue
            seen.add(associate_id)

            observations.append(
                _AssociationObservation(
                    associate_id=associate_id,
                    relationship_type="metadata_mention",
                    confidence=0.60,
                    provenance=provenance,
                    lineage_known=bool(provenance),
                )
            )

        return observations

    @staticmethod
    def _strongest_by_associate(
        observations: list[_AssociationObservation],
    ) -> dict[UUID, _AssociationObservation]:
        result: dict[UUID, _AssociationObservation] = {}

        for observation in observations:
            existing = result.get(observation.associate_id)
            if (
                existing is None
                or observation.confidence
                * IdentityRelationshipCorroborationService._type_factor(
                    observation.relationship_type
                )
                >
                existing.confidence
                * IdentityRelationshipCorroborationService._type_factor(
                    existing.relationship_type
                )
            ):
                result[observation.associate_id] = observation

        return result

    def _person_entity(
        self,
        entity_id: UUID,
    ) -> Any | None:
        try:
            entity = self.entity_service.get_entity(entity_id)
        except Exception:
            return None

        if entity is None:
            return None

        raw_type = getattr(entity, "entity_type", None)
        value = str(
            getattr(raw_type, "value", raw_type)
            or ""
        )

        if value != EntityType.PERSON.value:
            return None

        return entity

    @staticmethod
    def _relationship_type(
        relationship: Any,
    ) -> str:
        raw = getattr(
            relationship,
            "relationship_type",
            "other",
        )
        return str(
            getattr(raw, "value", raw)
            or "other"
        ).strip().lower()

    @staticmethod
    def _type_factor(
        relationship_type: str,
    ) -> float:
        return _TYPE_FACTORS.get(
            str(
                relationship_type
                or "other"
            ).strip().lower(),
            _TYPE_FACTORS["other"],
        )

    @staticmethod
    def _confidence(
        value: Any,
    ) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return round(
            max(0.0, min(1.0, number)),
            6,
        )

    @classmethod
    def _provenance_tokens(
        cls,
        metadata: dict[str, Any],
    ) -> frozenset[str]:
        tokens: set[str] = set()

        for key in _PROVENANCE_KEYS:
            raw = metadata.get(key)
            values = (
                list(raw)
                if isinstance(raw, (list, tuple, set, frozenset))
                else [raw]
            )

            if key in {
                "evidence_id",
                "evidence_ids",
                "source_evidence_id",
                "supporting_evidence_id",
                "supporting_evidence_ids",
            }:
                namespace = "evidence"
            elif key in {
                "source_id",
                "source_ids",
            }:
                namespace = "source"
            elif key in {
                "message_id",
                "message_ids",
            }:
                namespace = "message"
            else:
                namespace = "finding"

            for value in values:
                text = str(value or "").strip()
                if text:
                    tokens.add(
                        f"{namespace}:{text}"
                    )

        lineage = metadata.get("provenance")
        if isinstance(lineage, dict):
            tokens.update(cls._provenance_tokens(lineage))

        return frozenset(tokens)

    @staticmethod
    def _metadata_dict(
        value: Any,
    ) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _validate(
        *,
        person: Any,
        candidate: Any,
    ) -> None:
        if person is None or candidate is None:
            raise ValueError("Person and candidate are required.")

        person_type = str(
            getattr(
                getattr(person, "entity_type", None),
                "value",
                getattr(person, "entity_type", ""),
            )
        )
        if person_type != EntityType.PERSON.value:
            raise ValueError("Relationship corroboration requires a PERSON target.")

        if getattr(person, "case_id", None) != getattr(candidate, "case_id", None):
            raise ValueError("Person and candidate must belong to the same investigation.")


__all__ = [
    "IdentityRelationshipCorroborationService",
    "RelationshipCorroborationResult",
    "RelationshipCorroborationSignal",
]

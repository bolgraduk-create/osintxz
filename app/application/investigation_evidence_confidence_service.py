"""Case-level adapter from persisted Evidence provenance to canonical confidence math.

M024 does not introduce a second confidence formula. This application service
translates real, already-persisted extraction provenance into the existing
Evidence domain contracts and delegates every score to the canonical Evidence
services.

Only propositions that can be reconstructed without guessing are emitted.
At present that means extraction-derived Entity observations where:
- Evidence.metadata_json contains extraction_provenance,
- a persisted EvidenceEntity link exposes the linked Entity,
- the persisted candidate type and normalized value exactly match that Entity.

Arbitrary Evidence title/value text is never promoted into a proposition.
Different Source IDs alone are never treated as proof of independence.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping
from uuid import UUID

from app.evidence.contracts import (
    EvidenceSignal,
    EvidenceSignalDirection,
    EvidenceSignalProvenance,
    EvidenceSignalType,
)
from app.evidence.contradiction_detection import (
    EvidenceContradictionBreakdown,
    EvidenceContradictionDetectionService,
    EvidenceContradictionObservation,
)
from app.evidence.corroboration import (
    EvidenceCorroborationBreakdown,
    EvidenceCorroborationObservation,
    EvidenceCorroborationService,
)
from app.evidence.evidence_confidence import (
    EvidenceConfidenceAggregationService,
    EvidenceConfidenceBreakdown,
)
from app.evidence.evidence_strength import (
    EvidenceStrengthBreakdown,
    EvidenceStrengthScoringService,
)
from app.evidence.source_independence import (
    EvidenceSourceIndependenceBreakdown,
    EvidenceSourceIndependenceObservation,
    EvidenceSourceIndependenceService,
)
from app.evidence.source_reliability import (
    SourceReliabilityBreakdown,
)


@dataclass(frozen=True, slots=True)
class InvestigationEvidencePropositionConfidenceResult:
    """One explainable confidence result backed by persisted observations."""

    proposition_key: str
    entity_id: UUID
    entity_type: str
    entity_label: str
    primary_evidence_id: UUID
    evidence_ids: tuple[UUID, ...]
    source_ids: tuple[UUID, ...]
    origin_objects: tuple[tuple[str, str], ...]
    signal_count: int
    confidence: EvidenceConfidenceBreakdown
    strength: EvidenceStrengthBreakdown
    corroboration: EvidenceCorroborationBreakdown
    contradiction: EvidenceContradictionBreakdown
    independence: EvidenceSourceIndependenceBreakdown

    @property
    def confidence_score(self) -> float:
        return float(self.confidence.confidence_score)

    @property
    def assessment_coverage(self) -> float:
        return float(self.confidence.assessment_coverage)


@dataclass(frozen=True, slots=True)
class InvestigationEvidenceConfidenceAnalysisResult:
    """Read-only proposition confidence package for one investigation."""

    case_id: UUID
    propositions: tuple[
        InvestigationEvidencePropositionConfidenceResult,
        ...,
    ] = ()
    eligible_signal_count: int = 0
    skipped_evidence_count: int = 0
    invalid_metadata_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _PersistedObservation:
    proposition_key: str
    entity_id: UUID
    entity_type: str
    entity_label: str
    evidence: object
    source: object
    signal: EvidenceSignal
    origin_object_type: str | None
    origin_object_id: str | None
    origin_key: str | None
    lineage_keys: tuple[str, ...]
    content_fingerprint: str | None


class InvestigationEvidenceConfidenceService:
    """Adapt persisted extraction provenance to the existing Evidence pipeline."""

    def __init__(
        self,
        *,
        strength_scoring_service: EvidenceStrengthScoringService,
        corroboration_service: EvidenceCorroborationService,
        contradiction_service: EvidenceContradictionDetectionService,
        source_independence_service: EvidenceSourceIndependenceService,
        confidence_aggregation_service: EvidenceConfidenceAggregationService,
    ) -> None:
        self.strength_scoring_service = strength_scoring_service
        self.corroboration_service = corroboration_service
        self.contradiction_service = contradiction_service
        self.source_independence_service = source_independence_service
        self.confidence_aggregation_service = confidence_aggregation_service

    def analyze(
        self,
        *,
        case_id: UUID,
        evidence: tuple[object, ...] | list[object],
        source_reliability_by_source_key: Mapping[
            str,
            SourceReliabilityBreakdown,
        ],
    ) -> InvestigationEvidenceConfidenceAnalysisResult:
        if not isinstance(case_id, UUID):
            raise TypeError("case_id must be UUID.")

        observations: list[_PersistedObservation] = []
        skipped_evidence_count = 0
        invalid_metadata_count = 0
        warnings: list[str] = []

        for evidence_item in evidence:
            item_observations, invalid_metadata = self._observations_for_evidence(
                case_id=case_id,
                evidence=evidence_item,
            )
            if invalid_metadata:
                invalid_metadata_count += 1
            if not item_observations:
                skipped_evidence_count += 1
            observations.extend(item_observations)

        grouped: dict[str, list[_PersistedObservation]] = {}
        for observation in observations:
            grouped.setdefault(
                observation.proposition_key,
                [],
            ).append(observation)

        proposition_results: list[
            InvestigationEvidencePropositionConfidenceResult
        ] = []

        for proposition_key in sorted(grouped):
            proposition_observations = grouped[proposition_key]
            result = self._score_proposition(
                proposition_key=proposition_key,
                observations=proposition_observations,
                source_reliability_by_source_key=(
                    source_reliability_by_source_key
                ),
            )
            if result is None:
                warnings.append(
                    "Evidence proposition "
                    + proposition_key
                    + " was skipped because Source reliability "
                    "for its strongest persisted observation was unavailable."
                )
                continue
            proposition_results.append(result)

        if evidence and not proposition_results:
            warnings.append(
                "No persisted extraction-provenance Entity proposition was "
                "eligible for final Evidence Confidence."
            )

        return InvestigationEvidenceConfidenceAnalysisResult(
            case_id=case_id,
            propositions=tuple(proposition_results),
            eligible_signal_count=len(observations),
            skipped_evidence_count=skipped_evidence_count,
            invalid_metadata_count=invalid_metadata_count,
            warnings=tuple(self._deduplicate(warnings)),
        )

    def _score_proposition(
        self,
        *,
        proposition_key: str,
        observations: list[_PersistedObservation],
        source_reliability_by_source_key: Mapping[
            str,
            SourceReliabilityBreakdown,
        ],
    ) -> InvestigationEvidencePropositionConfidenceResult | None:
        if not observations:
            return None

        ordered = sorted(
            observations,
            key=lambda item: (
                -float(item.signal.weighted_strength),
                str(getattr(item.evidence, "id", "")),
                item.signal.name,
            ),
        )
        primary = ordered[0]
        primary_evidence_id = self._uuid_attr(
            primary.evidence,
            "id",
        )
        primary_source_id = self._uuid_attr(
            primary.source,
            "id",
        )
        if primary_evidence_id is None or primary_source_id is None:
            return None

        reliability = source_reliability_by_source_key.get(
            str(primary_source_id)
        )
        if reliability is None:
            return None

        primary_signals = [
            observation.signal
            for observation in ordered
            if self._uuid_attr(observation.evidence, "id")
            == primary_evidence_id
        ]
        strength = self.strength_scoring_service.score(
            primary_signals
        )

        corroboration_observations = [
            EvidenceCorroborationObservation(
                proposition_key=proposition_key,
                signal=observation.signal,
                details={
                    "adapter": "persisted_extraction_provenance",
                },
            )
            for observation in observations
        ]
        corroboration = self.corroboration_service.analyze(
            proposition_key,
            corroboration_observations,
        )

        contradiction_observations = [
            EvidenceContradictionObservation(
                proposition_key=proposition_key,
                signal=observation.signal,
                hard_conflict=False,
                details={
                    "adapter": "persisted_extraction_provenance",
                },
            )
            for observation in observations
        ]
        contradiction = self.contradiction_service.analyze(
            proposition_key,
            contradiction_observations,
        )

        independence_by_evidence: dict[
            UUID,
            EvidenceSourceIndependenceObservation,
        ] = {}
        for observation in ordered:
            evidence_id = self._uuid_attr(
                observation.evidence,
                "id",
            )
            source_id = self._uuid_attr(
                observation.source,
                "id",
            )
            if evidence_id is None or source_id is None:
                continue
            independence_by_evidence.setdefault(
                evidence_id,
                EvidenceSourceIndependenceObservation(
                    evidence_id=evidence_id,
                    source_id=source_id,
                    source_type=(
                        self._enum_text(
                            getattr(
                                observation.source,
                                "source_type",
                                None,
                            )
                        )
                        or None
                    ),
                    origin_key=observation.origin_key,
                    lineage_keys=observation.lineage_keys,
                    content_fingerprint=(
                        observation.content_fingerprint
                    ),
                    details={
                        "adapter": "persisted_extraction_provenance",
                    },
                ),
            )

        independence = self.source_independence_service.analyze(
            independence_by_evidence.values()
        )

        confidence = self.confidence_aggregation_service.aggregate(
            strength=strength,
            source_reliability=reliability,
            corroboration=corroboration,
            contradiction=contradiction,
            independence=independence,
        )

        evidence_ids = self._unique_uuid_attrs(
            [
                observation.evidence
                for observation in observations
            ],
            "id",
        )
        source_ids = self._unique_uuid_attrs(
            [
                observation.source
                for observation in observations
            ],
            "id",
        )
        origin_objects = tuple(
            sorted(
                {
                    (
                        observation.origin_object_type,
                        observation.origin_object_id,
                    )
                    for observation in observations
                    if (
                        observation.origin_object_type
                        and observation.origin_object_id
                    )
                }
            )
        )

        return InvestigationEvidencePropositionConfidenceResult(
            proposition_key=proposition_key,
            entity_id=primary.entity_id,
            entity_type=primary.entity_type,
            entity_label=primary.entity_label,
            primary_evidence_id=primary_evidence_id,
            evidence_ids=evidence_ids,
            source_ids=source_ids,
            origin_objects=origin_objects,
            signal_count=len(observations),
            confidence=confidence,
            strength=strength,
            corroboration=corroboration,
            contradiction=contradiction,
            independence=independence,
        )

    def _observations_for_evidence(
        self,
        *,
        case_id: UUID,
        evidence: object,
    ) -> tuple[list[_PersistedObservation], bool]:
        evidence_case_id = self._uuid_attr(
            evidence,
            "case_id",
        )
        evidence_id = self._uuid_attr(
            evidence,
            "id",
        )
        source_id = self._uuid_attr(
            evidence,
            "source_id",
        )
        source = getattr(evidence, "source", None)

        if (
            evidence_case_id != case_id
            or evidence_id is None
            or source_id is None
            or source is None
        ):
            return [], False

        metadata, invalid_metadata = self._metadata(
            getattr(evidence, "metadata_json", None)
        )
        provenance = metadata.get("extraction_provenance")
        if not isinstance(provenance, dict):
            return [], invalid_metadata

        candidates = provenance.get("candidates")
        if not isinstance(candidates, list):
            return [], invalid_metadata

        linked_entities = self._linked_entities(evidence)
        if not linked_entities:
            return [], invalid_metadata

        extractor = self._text(
            provenance.get("extractor")
        )
        origin = (
            provenance.get("origin")
            if isinstance(provenance.get("origin"), dict)
            else {}
        )
        origin_object_type = self._text(
            origin.get("object_type")
        ).casefold() or None
        origin_object_id = self._text(
            origin.get("object_id")
        ) or None

        origin_key = self._explicit_origin_key(
            provenance=provenance,
            origin=origin,
            evidence_metadata=metadata,
        )
        lineage_keys = self._explicit_lineage_keys(
            provenance=provenance,
            origin=origin,
            evidence_metadata=metadata,
        )
        fingerprint = self._content_fingerprint(
            evidence=evidence,
            source=source,
            provenance=provenance,
            origin=origin,
            evidence_metadata=metadata,
        )

        observations: list[_PersistedObservation] = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            candidate_type = self._text(
                candidate.get("entity_type")
            ).casefold()
            candidate_normalized = self._text(
                candidate.get("normalized_value")
            )
            confidence = self._unit_float(
                candidate.get("confidence")
            )
            if (
                not candidate_type
                or not candidate_normalized
                or confidence is None
            ):
                continue

            for entity in linked_entities:
                entity_id = self._uuid_attr(
                    entity,
                    "id",
                )
                entity_type = self._enum_text(
                    getattr(entity, "entity_type", None)
                ).casefold()
                entity_normalized = self._text(
                    getattr(entity, "normalized_value", None)
                )
                if (
                    entity_id is None
                    or entity_type != candidate_type
                    or entity_normalized != candidate_normalized
                ):
                    continue

                entity_label = self._text(
                    getattr(entity, "value", None)
                ) or candidate_normalized
                proposition_key = (
                    "entity_observed:"
                    + str(entity_id)
                )

                signal = EvidenceSignal(
                    name=(
                        "persisted_extraction_candidate:"
                        + candidate_type
                    ),
                    signal_type=EvidenceSignalType.CONTENT,
                    direction=EvidenceSignalDirection.SUPPORT,
                    strength=confidence,
                    weight=1.0,
                    reason=(
                        "Persisted extraction provenance records this "
                        "Entity candidate in the Evidence object."
                    ),
                    provenance=EvidenceSignalProvenance(
                        case_id=case_id,
                        evidence_id=evidence_id,
                        source_id=source_id,
                        evidence_type=self._enum_text(
                            getattr(
                                evidence,
                                "evidence_type",
                                None,
                            )
                        ) or None,
                        source_type=self._enum_text(
                            getattr(
                                source,
                                "source_type",
                                None,
                            )
                        ) or None,
                        origin=extractor or None,
                        details={
                            "adapter": (
                                "persisted_extraction_provenance"
                            ),
                        },
                    ),
                    details={
                        "entity_id": str(entity_id),
                        "entity_type": entity_type,
                        "normalized_value": entity_normalized,
                    },
                )

                observations.append(
                    _PersistedObservation(
                        proposition_key=proposition_key,
                        entity_id=entity_id,
                        entity_type=entity_type,
                        entity_label=entity_label,
                        evidence=evidence,
                        source=source,
                        signal=signal,
                        origin_object_type=origin_object_type,
                        origin_object_id=origin_object_id,
                        origin_key=origin_key,
                        lineage_keys=lineage_keys,
                        content_fingerprint=fingerprint,
                    )
                )

        return observations, invalid_metadata

    @staticmethod
    def _linked_entities(evidence: object) -> list[object]:
        result: list[object] = []
        for link in list(
            getattr(evidence, "entity_links", None)
            or []
        ):
            entity = getattr(link, "entity", None)
            if entity is not None:
                result.append(entity)
        return result

    @classmethod
    def _explicit_origin_key(
        cls,
        *,
        provenance: dict[str, Any],
        origin: dict[str, Any],
        evidence_metadata: dict[str, Any],
    ) -> str | None:
        origin_metadata = (
            origin.get("metadata")
            if isinstance(origin.get("metadata"), dict)
            else {}
        )
        for mapping in (
            origin_metadata,
            origin,
            provenance,
            evidence_metadata,
        ):
            for key in (
                "origin_key",
                "primary_origin_key",
                "canonical_origin_key",
            ):
                value = cls._text(mapping.get(key))
                if value:
                    return value
        return None

    @classmethod
    def _explicit_lineage_keys(
        cls,
        *,
        provenance: dict[str, Any],
        origin: dict[str, Any],
        evidence_metadata: dict[str, Any],
    ) -> tuple[str, ...]:
        values: set[str] = set()
        origin_metadata = (
            origin.get("metadata")
            if isinstance(origin.get("metadata"), dict)
            else {}
        )
        for mapping in (
            origin_metadata,
            origin,
            provenance,
            evidence_metadata,
        ):
            raw = mapping.get("lineage_keys")
            if isinstance(raw, (list, tuple, set)):
                for item in raw:
                    value = cls._text(item)
                    if value:
                        values.add(value)
        return tuple(sorted(values))

    @classmethod
    def _content_fingerprint(
        cls,
        *,
        evidence: object,
        source: object,
        provenance: dict[str, Any],
        origin: dict[str, Any],
        evidence_metadata: dict[str, Any],
    ) -> str | None:
        sha256 = cls._text(
            getattr(evidence, "sha256", None)
        ).casefold()
        if sha256:
            return "sha256:" + sha256

        origin_metadata = (
            origin.get("metadata")
            if isinstance(origin.get("metadata"), dict)
            else {}
        )
        for mapping in (
            origin_metadata,
            origin,
            provenance,
            evidence_metadata,
        ):
            value = cls._text(
                mapping.get("content_fingerprint")
            )
            if value:
                return value.casefold()

        source_checksum = cls._text(
            getattr(source, "checksum", None)
        ).casefold()
        if source_checksum:
            return "source_checksum:" + source_checksum

        return None

    @staticmethod
    def _metadata(value: Any) -> tuple[dict[str, Any], bool]:
        if value is None:
            return {}, False
        if isinstance(value, dict):
            return dict(value), False
        try:
            payload = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}, True
        if not isinstance(payload, dict):
            return {}, True
        return dict(payload), False

    @staticmethod
    def _uuid_attr(value: object, name: str) -> UUID | None:
        raw = getattr(value, name, None)
        if isinstance(raw, UUID):
            return raw
        try:
            return UUID(str(raw))
        except (TypeError, ValueError, AttributeError):
            return None

    @classmethod
    def _unique_uuid_attrs(
        cls,
        values: list[object],
        name: str,
    ) -> tuple[UUID, ...]:
        found: set[UUID] = set()
        for value in values:
            parsed = cls._uuid_attr(
                value,
                name,
            )
            if parsed is not None:
                found.add(parsed)
        return tuple(
            sorted(
                found,
                key=str,
            )
        )

    @staticmethod
    def _enum_text(value: Any) -> str:
        if value is None:
            return ""
        raw = getattr(value, "value", value)
        return str(raw or "").strip()

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _unit_float(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if not 0.0 <= numeric <= 1.0:
            return None
        return numeric

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output


__all__ = [
    "InvestigationEvidenceConfidenceAnalysisResult",
    "InvestigationEvidenceConfidenceService",
    "InvestigationEvidencePropositionConfidenceResult",
]

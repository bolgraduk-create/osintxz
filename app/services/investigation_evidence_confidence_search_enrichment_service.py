"""Propagate canonical M024 Evidence Confidence into unified search hits.

This service does not calculate confidence and does not alter search ranking.
It only attaches already-computed proposition confidence to matching
InvestigationSearchHit objects so RAG/AI can consume deterministic Evidence
analysis without confusing it with retrieval relevance.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from app.investigation.search_result import InvestigationSearchHit


CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY = (
    "canonical_evidence_confidence"
)


class InvestigationEvidenceConfidenceSearchEnrichmentService:
    """Attach canonical proposition-confidence payloads to matching hits."""

    metadata_key = CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY

    def annotate(
        self,
        hits: list[InvestigationSearchHit],
        proposition_results: Iterable[object],
    ) -> list[InvestigationSearchHit]:
        if not isinstance(hits, list):
            raise TypeError("hits must be a list.")

        proposition_list = list(proposition_results or ())
        if not proposition_list or not hits:
            return hits

        entity_map: dict[str, list[dict[str, Any]]] = {}
        evidence_map: dict[str, list[dict[str, Any]]] = {}
        origin_map: dict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = {}

        for proposition in proposition_list:
            payload = self._payload(proposition)
            if payload is None:
                continue

            entity_id = str(payload["entity_id"])
            entity_map.setdefault(
                entity_id,
                [],
            ).append(payload)

            for evidence_id in payload["evidence_ids"]:
                evidence_map.setdefault(
                    str(evidence_id),
                    [],
                ).append(payload)

            for origin in payload["origin_objects"]:
                if not isinstance(origin, dict):
                    continue
                object_type = str(
                    origin.get("object_type")
                    or ""
                ).strip().casefold()
                object_id = str(
                    origin.get("object_id")
                    or ""
                ).strip()
                if object_type and object_id:
                    origin_map.setdefault(
                        (object_type, object_id),
                        [],
                    ).append(payload)

        for hit in hits:
            if not isinstance(hit, InvestigationSearchHit):
                raise TypeError(
                    "hits must contain InvestigationSearchHit objects."
                )

            matches: list[dict[str, Any]] = []
            hit_id = str(hit.object_id)
            hit_type = str(hit.object_type or "").strip().casefold()

            if hit_type == "entity":
                matches.extend(
                    entity_map.get(
                        hit_id,
                        (),
                    )
                )

            if hit_type == "evidence":
                matches.extend(
                    evidence_map.get(
                        hit_id,
                        (),
                    )
                )

            matches.extend(
                origin_map.get(
                    (hit_type, hit_id),
                    (),
                )
            )

            unique_matches = self._deduplicate_payloads(
                matches
            )

            if not unique_matches:
                continue

            ordered = sorted(
                unique_matches,
                key=lambda item: (
                    -float(item["confidence_score"]),
                    -float(item["assessment_coverage"]),
                    str(item["proposition_key"]),
                ),
            )
            strongest = ordered[0]

            hit.metadata[self.metadata_key] = {
                "version": "m024b",
                "scope": "proposition_support",
                "proposition_count": len(ordered),
                "strongest_confidence": (
                    strongest["confidence_score"]
                ),
                "strongest_assessment_coverage": (
                    strongest["assessment_coverage"]
                ),
                "propositions": ordered,
                "ranking_unchanged": True,
            }

        return hits

    def _payload(
        self,
        proposition: object,
    ) -> dict[str, Any] | None:
        proposition_key = self._text(
            getattr(
                proposition,
                "proposition_key",
                None,
            )
        )
        entity_id = self._uuid_text(
            getattr(
                proposition,
                "entity_id",
                None,
            )
        )
        if not proposition_key or not entity_id:
            return None

        confidence = getattr(
            proposition,
            "confidence",
            None,
        )
        if confidence is None:
            return None

        confidence_score = self._unit_float(
            getattr(
                proposition,
                "confidence_score",
                getattr(
                    confidence,
                    "confidence_score",
                    None,
                ),
            )
        )
        assessment_coverage = self._unit_float(
            getattr(
                proposition,
                "assessment_coverage",
                getattr(
                    confidence,
                    "assessment_coverage",
                    None,
                ),
            )
        )
        if (
            confidence_score is None
            or assessment_coverage is None
        ):
            return None

        return {
            "proposition_key": proposition_key,
            "entity_id": entity_id,
            "entity_type": self._text(
                getattr(
                    proposition,
                    "entity_type",
                    None,
                )
            ),
            "entity_label": self._text(
                getattr(
                    proposition,
                    "entity_label",
                    None,
                )
            ),
            "confidence_score": confidence_score,
            "assessment_coverage": assessment_coverage,
            "intrinsic_strength": self._unit_float(
                getattr(
                    confidence,
                    "intrinsic_strength",
                    None,
                )
            ),
            "source_reliability_score": self._unit_float(
                getattr(
                    confidence,
                    "source_reliability_score",
                    None,
                )
            ),
            "source_reliability_coverage": self._unit_float(
                getattr(
                    confidence,
                    "source_reliability_coverage",
                    None,
                )
            ),
            "raw_corroboration_score": self._unit_float(
                getattr(
                    confidence,
                    "raw_corroboration_score",
                    None,
                )
            ),
            "effective_corroboration_score": self._unit_float(
                getattr(
                    confidence,
                    "effective_corroboration_score",
                    None,
                )
            ),
            "independence_score": self._unit_float(
                getattr(
                    confidence,
                    "independence_score",
                    None,
                )
            ),
            "independence_coverage": self._unit_float(
                getattr(
                    confidence,
                    "independence_coverage",
                    None,
                )
            ),
            "contradiction_strength": self._unit_float(
                getattr(
                    confidence,
                    "contradiction_strength",
                    None,
                )
            ),
            "conflict_score": self._unit_float(
                getattr(
                    confidence,
                    "conflict_score",
                    None,
                )
            ),
            "hard_conflict": bool(
                getattr(
                    confidence,
                    "hard_conflict",
                    False,
                )
            ),
            "net_support_margin": self._signed_float(
                getattr(
                    confidence,
                    "net_support_margin",
                    None,
                )
            ),
            "evidence_ids": [
                str(value)
                for value in (
                    getattr(
                        proposition,
                        "evidence_ids",
                        (),
                    )
                    or ()
                )
            ],
            "source_ids": [
                str(value)
                for value in (
                    getattr(
                        proposition,
                        "source_ids",
                        (),
                    )
                    or ()
                )
            ],
            "origin_objects": [
                {
                    "object_type": str(
                        origin[0]
                    ),
                    "object_id": str(
                        origin[1]
                    ),
                }
                for origin in (
                    getattr(
                        proposition,
                        "origin_objects",
                        (),
                    )
                    or ()
                )
                if (
                    isinstance(origin, tuple)
                    and len(origin) == 2
                    and str(origin[0]).strip()
                    and str(origin[1]).strip()
                )
            ],
        }

    @staticmethod
    def _deduplicate_payloads(
        values: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        unique: dict[str, dict[str, Any]] = {}
        for value in values:
            key = str(
                value.get("proposition_key")
                or ""
            )
            if not key:
                continue
            previous = unique.get(key)
            if previous is None:
                unique[key] = value
                continue
            current_key = (
                float(value.get("confidence_score") or 0.0),
                float(value.get("assessment_coverage") or 0.0),
            )
            previous_key = (
                float(previous.get("confidence_score") or 0.0),
                float(previous.get("assessment_coverage") or 0.0),
            )
            if current_key > previous_key:
                unique[key] = value
        return list(unique.values())

    @staticmethod
    def _uuid_text(value: Any) -> str:
        if isinstance(value, UUID):
            return str(value)
        try:
            return str(
                UUID(
                    str(value)
                )
            )
        except (
            TypeError,
            ValueError,
            AttributeError,
        ):
            return ""

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _unit_float(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not 0.0 <= number <= 1.0:
            return None
        return number

    @staticmethod
    def _signed_float(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not -1.0 <= number <= 1.0:
            return None
        return number


__all__ = [
    "CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY",
    "InvestigationEvidenceConfidenceSearchEnrichmentService",
]

"""Evidence/provenance confidence annotation for unified search results.

This service deliberately keeps confidence separate from search relevance.
Retrieval/fusion/rerank scores answer "how relevant is this hit to the query?".
Confidence answers "how well supported/provenanced is this result?".

It does not assert that a claim is true and does not replace claim verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.investigation.search_result import InvestigationSearchHit


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return _clamp(float(value))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class SearchConfidenceBreakdown:
    """Explainable confidence factors used for one hit."""

    confidence: float
    evidence_score: float
    provenance_completeness: float
    object_confidence: float | None
    source_integrity: float | None
    support_strength: float | None

    def as_dict(self) -> dict[str, float | None]:
        return {
            "confidence": self.confidence,
            "evidence_score": self.evidence_score,
            "provenance_completeness": self.provenance_completeness,
            "object_confidence": self.object_confidence,
            "source_integrity": self.source_integrity,
            "support_strength": self.support_strength,
        }


class SearchConfidenceService:
    """Calculate conservative provenance/evidence confidence for search hits."""

    METADATA_KEY = "evidence_confidence"

    def annotate(self, hits: list[InvestigationSearchHit]) -> list[InvestigationSearchHit]:
        for hit in hits:
            breakdown = self.calculate(hit)
            hit.scores.evidence = breakdown.evidence_score
            hit.scores.confidence = breakdown.confidence
            hit.metadata[self.METADATA_KEY] = breakdown.as_dict()
        return hits

    def calculate(self, hit: InvestigationSearchHit) -> SearchConfidenceBreakdown:
        provenance = self._provenance_completeness(hit)
        object_confidence = self._object_confidence(hit)
        source_integrity = self._source_integrity(hit)
        support_strength = self._support_strength(hit)

        evidence_factors: list[tuple[float, float]] = [(provenance, 0.45)]
        if source_integrity is not None:
            evidence_factors.append((source_integrity, 0.30))
        if support_strength is not None:
            evidence_factors.append((support_strength, 0.25))

        evidence_score = self._weighted_available(evidence_factors)

        confidence_factors: list[tuple[float, float]] = [(evidence_score, 0.70)]
        if object_confidence is not None:
            confidence_factors.append((object_confidence, 0.30))

        confidence = self._weighted_available(confidence_factors)

        return SearchConfidenceBreakdown(
            confidence=confidence,
            evidence_score=evidence_score,
            provenance_completeness=provenance,
            object_confidence=object_confidence,
            source_integrity=source_integrity,
            support_strength=support_strength,
        )

    @staticmethod
    def _weighted_available(values: list[tuple[float, float]]) -> float:
        total_weight = sum(weight for _, weight in values)
        if total_weight <= 0.0:
            return 0.0
        return _clamp(sum(value * weight for value, weight in values) / total_weight)

    @staticmethod
    def _provenance_completeness(hit: InvestigationSearchHit) -> float:
        checks = [
            hit.case_id is not None,
            hit.object_id is not None,
            bool(hit.object_type),
            hit.source is not None,
        ]
        return sum(1.0 for value in checks if value) / len(checks)

    @staticmethod
    def _object_confidence(hit: InvestigationSearchHit) -> float | None:
        value = hit.metadata.get("confidence")
        if value is None and hit.source is not None:
            value = getattr(hit.source, "confidence", None)
        return _numeric(value)

    @staticmethod
    def _source_integrity(hit: InvestigationSearchHit) -> float | None:
        """Score observable source-integrity signals, not source truthfulness."""
        metadata = hit.metadata
        source_id = metadata.get("source_id")
        sha256 = metadata.get("sha256")
        checksum = metadata.get("checksum")

        if hit.source is not None:
            source_id = source_id or getattr(hit.source, "source_id", None)
            sha256 = sha256 or getattr(hit.source, "sha256", None)
            checksum = checksum or getattr(hit.source, "checksum", None)

        if source_id is None and sha256 is None and checksum is None:
            return None

        score = 0.60 if source_id is not None else 0.35
        if sha256 or checksum:
            score += 0.40
        return _clamp(score)

    @staticmethod
    def _support_strength(hit: InvestigationSearchHit) -> float | None:
        """Use explicit support counts only when upstream actually supplies them."""
        raw_count = hit.metadata.get("evidence_support_count")
        if raw_count is None:
            return None
        try:
            count = max(0, int(raw_count))
        except (TypeError, ValueError):
            return None
        if count == 0:
            return 0.0
        if count == 1:
            return 0.60
        if count == 2:
            return 0.80
        return 1.0

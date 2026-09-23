"""Deterministic explainability for canonical Evidence Confidence.

This module explains scores that were already calculated by the Evidence
pipeline. It never changes confidence, thresholds, ranking, provenance, or
Evidence state. The output is suitable for UI, RAG and audit logs.

Important semantic boundary:
- confidence explains support for one proposition;
- assessment coverage explains how much of the configured assessment was
  observable;
- missing/unknown inputs are limitations, not negative evidence;
- retrieval relevance is outside this service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.evidence.contradiction_detection import (
    EvidenceContradictionBreakdown,
)
from app.evidence.corroboration import (
    EvidenceCorroborationBreakdown,
)
from app.evidence.evidence_confidence import (
    EvidenceConfidenceBreakdown,
)
from app.evidence.evidence_strength import (
    EvidenceStrengthBreakdown,
)
from app.evidence.source_independence import (
    EvidenceSourceIndependenceBreakdown,
)
from app.evidence.source_reliability import (
    SourceReliabilityBreakdown,
    SourceReliabilityFactorState,
)


@dataclass(frozen=True, slots=True)
class EvidenceConfidenceExplanationReason:
    """One deterministic explanation statement."""

    code: str
    category: str
    effect: str
    message: str
    value: float | None = None
    coverage: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "effect": self.effect,
            "message": self.message,
            "value": self.value,
            "coverage": self.coverage,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class EvidenceConfidenceExplanation:
    """Human/machine-readable explanation for one proposition score."""

    proposition_key: str
    summary: str
    reasons: tuple[EvidenceConfidenceExplanationReason, ...] = ()
    limitations: tuple[EvidenceConfidenceExplanationReason, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": "m025a",
            "propositionKey": self.proposition_key,
            "summary": self.summary,
            "reasons": [
                reason.to_payload()
                for reason in self.reasons
            ],
            "limitations": [
                reason.to_payload()
                for reason in self.limitations
            ],
        }


class EvidenceConfidenceExplanationService:
    """Explain already-calculated canonical Evidence Confidence."""

    def build(
        self,
        *,
        confidence: EvidenceConfidenceBreakdown,
        strength: EvidenceStrengthBreakdown,
        source_reliability: SourceReliabilityBreakdown,
        corroboration: EvidenceCorroborationBreakdown,
        contradiction: EvidenceContradictionBreakdown,
        independence: EvidenceSourceIndependenceBreakdown,
    ) -> EvidenceConfidenceExplanation:
        reasons: list[EvidenceConfidenceExplanationReason] = []
        limitations: list[EvidenceConfidenceExplanationReason] = []

        reasons.append(
            EvidenceConfidenceExplanationReason(
                code="intrinsic_strength",
                category="evidence",
                effect="support",
                message=(
                    "The strongest eligible intrinsic Evidence signal has "
                    f"strength {self._percent(confidence.intrinsic_strength)}."
                ),
                value=float(confidence.intrinsic_strength),
                details={
                    "consideredSignalCount": int(
                        strength.considered_signal_count
                    ),
                    "duplicateSignalCount": int(
                        strength.duplicate_signal_count
                    ),
                },
            )
        )

        reasons.append(
            EvidenceConfidenceExplanationReason(
                code="source_reliability",
                category="source",
                effect="context",
                message=(
                    "Observed source reliability is "
                    f"{self._percent(confidence.source_reliability_score)} "
                    "with "
                    f"{self._percent(confidence.source_reliability_coverage)} "
                    "reliability-model coverage."
                ),
                value=float(confidence.source_reliability_score),
                coverage=float(confidence.source_reliability_coverage),
                details={
                    "evaluatedFactorCount": int(
                        source_reliability.evaluated_factor_count
                    ),
                    "unknownFactorCount": int(
                        source_reliability.unknown_factor_count
                    ),
                    "negativeFactorCount": int(
                        source_reliability.negative_factor_count
                    ),
                },
            )
        )

        negative_factors = [
            factor
            for factor in source_reliability.factors
            if (
                factor.state
                == SourceReliabilityFactorState.NEGATIVE
            )
        ]
        for factor in negative_factors[:4]:
            limitations.append(
                EvidenceConfidenceExplanationReason(
                    code="source_factor_negative:" + factor.name,
                    category="source",
                    effect="limitation",
                    message=(
                        factor.reason
                        or (
                            "A source-reliability factor was evaluated "
                            "negatively."
                        )
                    ),
                    value=(
                        float(factor.quality)
                        if factor.quality is not None
                        else None
                    ),
                    details={
                        "factor": factor.name,
                        "weight": float(factor.weight),
                    },
                )
            )

        unknown_factors = [
            factor
            for factor in source_reliability.factors
            if (
                factor.state
                == SourceReliabilityFactorState.UNKNOWN
            )
        ]
        if confidence.source_reliability_coverage < 1.0:
            limitations.append(
                EvidenceConfidenceExplanationReason(
                    code="source_reliability_incomplete",
                    category="source",
                    effect="uncertainty",
                    message=(
                        "Source reliability is only partially observable; "
                        "missing factors were kept unknown instead of being "
                        "treated as negative evidence."
                    ),
                    coverage=float(
                        confidence.source_reliability_coverage
                    ),
                    details={
                        "unknownFactors": [
                            factor.name
                            for factor in unknown_factors[:8]
                        ],
                    },
                )
            )

        if (
            corroboration.is_corroborated
            and confidence.effective_corroboration_score > 0.0
        ):
            reasons.append(
                EvidenceConfidenceExplanationReason(
                    code="corroboration_applied",
                    category="corroboration",
                    effect="support",
                    message=(
                        f"{corroboration.supporting_evidence_count} distinct "
                        "Evidence item(s) support the proposition; after "
                        "source-independence adjustment, corroboration "
                        "contributes "
                        f"{self._percent(confidence.effective_corroboration_score)}."
                    ),
                    value=float(
                        confidence.effective_corroboration_score
                    ),
                    details={
                        "rawCorroboration": float(
                            confidence.raw_corroboration_score
                        ),
                        "supportingEvidenceCount": int(
                            corroboration.supporting_evidence_count
                        ),
                        "distinctSourceCount": int(
                            corroboration.distinct_source_count
                        ),
                    },
                )
            )
        elif (
            confidence.raw_corroboration_score > 0.0
            and confidence.effective_corroboration_score <= 0.0
        ):
            limitations.append(
                EvidenceConfidenceExplanationReason(
                    code="corroboration_not_independent",
                    category="corroboration",
                    effect="uncertainty",
                    message=(
                        "Multiple supporting observations exist, but they "
                        "did not increase confidence because independent "
                        "provenance was not established."
                    ),
                    value=float(confidence.raw_corroboration_score),
                    coverage=float(confidence.independence_coverage),
                )
            )
        elif corroboration.supporting_evidence_count <= 1:
            limitations.append(
                EvidenceConfidenceExplanationReason(
                    code="single_evidence_support",
                    category="corroboration",
                    effect="uncertainty",
                    message=(
                        "The proposition currently lacks corroboration from "
                        "a second distinct Evidence item."
                    ),
                    details={
                        "supportingEvidenceCount": int(
                            corroboration.supporting_evidence_count
                        ),
                    },
                )
            )

        if independence.total_pair_count > 0:
            if independence.independent_pair_count > 0:
                reasons.append(
                    EvidenceConfidenceExplanationReason(
                        code="verified_independence",
                        category="independence",
                        effect="support",
                        message=(
                            f"{independence.independent_pair_count} Evidence "
                            "pair(s) have provenance supporting independence."
                        ),
                        value=float(confidence.independence_score),
                        coverage=float(confidence.independence_coverage),
                    )
                )

            if independence.dependent_pair_count > 0:
                limitations.append(
                    EvidenceConfidenceExplanationReason(
                        code="dependent_sources",
                        category="independence",
                        effect="limitation",
                        message=(
                            f"{independence.dependent_pair_count} Evidence "
                            "pair(s) are provenance-dependent and therefore "
                            "cannot provide independent corroboration."
                        ),
                        details={
                            "sameSourcePairs": int(
                                independence.same_source_pair_count
                            ),
                            "sharedOriginPairs": int(
                                independence.shared_origin_pair_count
                            ),
                            "sharedLineagePairs": int(
                                independence.shared_lineage_pair_count
                            ),
                            "sharedFingerprintPairs": int(
                                independence.shared_fingerprint_pair_count
                            ),
                        },
                    )
                )

            if independence.unknown_pair_count > 0:
                limitations.append(
                    EvidenceConfidenceExplanationReason(
                        code="independence_unknown",
                        category="independence",
                        effect="uncertainty",
                        message=(
                            f"Independence could not be established for "
                            f"{independence.unknown_pair_count} Evidence "
                            "pair(s); different Source IDs alone are not "
                            "treated as proof of independence."
                        ),
                        coverage=float(confidence.independence_coverage),
                    )
                )
        else:
            limitations.append(
                EvidenceConfidenceExplanationReason(
                    code="independence_not_applicable",
                    category="independence",
                    effect="uncertainty",
                    message=(
                        "There are not enough distinct Evidence observations "
                        "to evaluate source independence."
                    ),
                )
            )

        if contradiction.hard_conflict:
            limitations.append(
                EvidenceConfidenceExplanationReason(
                    code="hard_conflict",
                    category="contradiction",
                    effect="contradiction",
                    message=(
                        "A hard Evidence conflict is present; canonical "
                        "Evidence Confidence is vetoed to zero."
                    ),
                    value=float(confidence.contradiction_strength),
                    details={
                        "hardConflictEvidenceIds": [
                            str(value)
                            for value in (
                                contradiction.hard_conflict_evidence_ids
                            )
                        ],
                    },
                )
            )
        elif confidence.contradiction_strength > 0.0:
            limitations.append(
                EvidenceConfidenceExplanationReason(
                    code="contradiction_present",
                    category="contradiction",
                    effect="contradiction",
                    message=(
                        "Contradicting Evidence reduces support with "
                        f"strength {self._percent(confidence.contradiction_strength)}."
                    ),
                    value=float(confidence.contradiction_strength),
                    details={
                        "contradictionEvidenceCount": int(
                            contradiction.contradiction_evidence_count
                        ),
                        "conflictScore": float(
                            confidence.conflict_score
                        ),
                        "penaltyFactor": float(
                            confidence.contradiction_penalty_factor
                        ),
                    },
                )
            )
        else:
            reasons.append(
                EvidenceConfidenceExplanationReason(
                    code="no_observed_contradiction",
                    category="contradiction",
                    effect="context",
                    message=(
                        "No contradicting Evidence was observed in the "
                        "evaluated proposition inputs."
                    ),
                    value=0.0,
                )
            )

        if confidence.assessment_coverage < 1.0:
            limitations.append(
                EvidenceConfidenceExplanationReason(
                    code="assessment_incomplete",
                    category="coverage",
                    effect="uncertainty",
                    message=(
                        "The confidence assessment is incomplete; overall "
                        "assessment coverage is "
                        f"{self._percent(confidence.assessment_coverage)}."
                    ),
                    coverage=float(confidence.assessment_coverage),
                )
            )

        summary = (
            "Canonical proposition confidence is "
            f"{self._percent(confidence.confidence_score)} "
            "with "
            f"{self._percent(confidence.assessment_coverage)} "
            "assessment coverage."
        )
        if confidence.hard_conflict:
            summary += " A hard conflict veto is active."
        elif confidence.contradiction_strength > 0.0:
            summary += " Contradicting Evidence reduces the final support."

        return EvidenceConfidenceExplanation(
            proposition_key=confidence.proposition_key,
            summary=summary,
            reasons=tuple(self._deduplicate(reasons)),
            limitations=tuple(self._deduplicate(limitations)),
        )

    @staticmethod
    def _percent(value: float) -> str:
        return f"{float(value) * 100.0:.0f}%"

    @staticmethod
    def _deduplicate(
        reasons: list[EvidenceConfidenceExplanationReason],
    ) -> list[EvidenceConfidenceExplanationReason]:
        seen: set[str] = set()
        result: list[EvidenceConfidenceExplanationReason] = []
        for reason in reasons:
            if reason.code in seen:
                continue
            seen.add(reason.code)
            result.append(reason)
        return result


__all__ = [
    "EvidenceConfidenceExplanation",
    "EvidenceConfidenceExplanationReason",
    "EvidenceConfidenceExplanationService",
]

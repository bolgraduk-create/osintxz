"""R14.3d calibrated machine confidence for identity candidates.

The calibrator combines already-existing machine signals without mutating
Entity.confidence and without converting analyst decisions into numeric model
evidence.

Inputs:
- persisted/base candidate confidence;
- explainable deterministic IdentityResolution;
- relationship corroboration from R14.3c;
- optional analyst decision state for presentation only.

Hard identity conflicts always dominate supportive graph evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Any

from app.application.identity_resolution import IdentityResolution
from app.application.identity_relationship_corroboration import (
    RelationshipCorroborationResult,
)


_HARD_CONFLICT_CATEGORIES = frozenset(
    {
        "birth_date",
        "orcid",
        "npi",
    }
)

_IDENTITY_SUPPORT_CAPS = {
    "strong": 0.45,
    "supported": 0.32,
    "possible": 0.15,
}

_VALID_ANALYST_DECISIONS = {
    "",
    "unreviewed",
    "review",
    "confirmed",
    "rejected",
}


@dataclass(frozen=True, slots=True)
class IdentityConfidenceCalibration:
    base_confidence: float
    calibrated_confidence: float
    identity_support: float
    relationship_support: float
    combined_support: float
    conflict_penalty: float
    identity_status: str
    analyst_decision: str
    hard_conflict: bool
    review_required: bool
    pivot_allowed: bool
    positive_signals: tuple[str, ...] = ()
    negative_signals: tuple[str, ...] = ()

    @property
    def analyst_authoritative(self) -> bool:
        return self.analyst_decision in {
            "confirmed",
            "rejected",
        }

    @property
    def machine_label(self) -> str:
        if self.hard_conflict:
            return "Conflicting"
        if self.calibrated_confidence >= 0.80:
            return "High machine confidence"
        if self.calibrated_confidence >= 0.60:
            return "Moderate machine confidence"
        return "Low machine confidence"

    @property
    def summary(self) -> str:
        parts: list[str] = []

        if self.positive_signals:
            parts.extend(self.positive_signals[:3])

        if self.negative_signals:
            parts.append(
                "Conflicts: "
                + "; ".join(
                    self.negative_signals[:2]
                )
            )

        if not parts:
            parts.append(
                "No additional calibrated identity support."
            )

        if self.analyst_authoritative:
            parts.append(
                "Analyst decision remains authoritative and separate from machine confidence."
            )

        return " · ".join(parts)

    def to_payload(self) -> dict[str, Any]:
        return {
            "baseConfidence": self.base_confidence,
            "calibratedConfidence": self.calibrated_confidence,
            "identitySupport": self.identity_support,
            "relationshipSupport": self.relationship_support,
            "combinedSupport": self.combined_support,
            "conflictPenalty": self.conflict_penalty,
            "identityStatus": self.identity_status,
            "analystDecision": self.analyst_decision,
            "analystAuthoritative": self.analyst_authoritative,
            "hardConflict": self.hard_conflict,
            "reviewRequired": self.review_required,
            "pivotAllowed": self.pivot_allowed,
            "machineLabel": self.machine_label,
            "positiveSignals": list(self.positive_signals),
            "negativeSignals": list(self.negative_signals),
            "summary": self.summary,
        }


class IdentityConfidenceCalibrationService:
    """Conservative correlation-aware identity confidence calibration."""

    MAX_RELATIONSHIP_SUPPORT = 0.45
    SOFT_CONFLICT_PENALTY = 0.08
    MAX_SOFT_CONFLICT_PENALTY = 0.24
    CONFLICTING_STATUS_CAP = 0.35
    HARD_CONFLICT_CAP = 0.25

    def calibrate(
        self,
        *,
        base_confidence: Any,
        identity_resolution: IdentityResolution | None = None,
        relationship_result: RelationshipCorroborationResult | None = None,
        analyst_decision: str = "",
    ) -> IdentityConfidenceCalibration:
        base = self._confidence(base_confidence)
        decision = self._analyst_decision(
            analyst_decision
        )

        identity_status = (
            str(identity_resolution.status or "")
            .strip()
            .lower()
            if identity_resolution is not None
            else "not_applicable"
        )

        identity_support = self._identity_support(
            identity_resolution
        )
        relationship_support = min(
            self.MAX_RELATIONSHIP_SUPPORT,
            max(
                0.0,
                float(
                    getattr(
                        relationship_result,
                        "support",
                        0.0,
                    )
                    or 0.0
                ),
            ),
        )

        combined_support = (
            1.0
            - prod(
                (
                    1.0 - identity_support,
                    1.0 - relationship_support,
                )
            )
        )
        combined_support = self._confidence(
            combined_support
        )

        calibrated = (
            base
            + (1.0 - base)
            * combined_support
        )

        conflict_categories = tuple(
            dict.fromkeys(
                str(item or "")
                .strip()
                .lower()
                for item in (
                    identity_resolution.conflict_categories
                    if identity_resolution is not None
                    else ()
                )
                if str(item or "").strip()
            )
        )
        hard_conflict = bool(
            set(conflict_categories)
            & _HARD_CONFLICT_CATEGORIES
        )

        conflict_penalty = min(
            self.MAX_SOFT_CONFLICT_PENALTY,
            len(conflict_categories)
            * self.SOFT_CONFLICT_PENALTY,
        )

        if conflict_penalty:
            calibrated *= (
                1.0 - conflict_penalty
            )

        if identity_status == "conflicting":
            calibrated = min(
                calibrated,
                self.CONFLICTING_STATUS_CAP,
            )

        if hard_conflict:
            calibrated = min(
                calibrated,
                self.HARD_CONFLICT_CAP,
            )

        calibrated = self._confidence(
            calibrated
        )

        positive_signals = self._positive_signals(
            identity_resolution=identity_resolution,
            relationship_result=relationship_result,
        )
        negative_signals = self._negative_signals(
            identity_resolution
        )

        pivot_allowed = bool(
            identity_resolution is not None
            and identity_resolution.pivot_allowed
            and not hard_conflict
            and identity_status
            in {
                "strong",
                "supported",
            }
            and calibrated >= 0.60
        )

        # Account ownership remains human-reviewed in R14.3.  This flag is
        # only safe for search/pivot relevance and never means auto-confirm.
        review_required = bool(
            decision
            in {
                "",
                "unreviewed",
                "review",
            }
        )

        return IdentityConfidenceCalibration(
            base_confidence=base,
            calibrated_confidence=calibrated,
            identity_support=round(
                identity_support,
                6,
            ),
            relationship_support=round(
                relationship_support,
                6,
            ),
            combined_support=round(
                combined_support,
                6,
            ),
            conflict_penalty=round(
                conflict_penalty,
                6,
            ),
            identity_status=identity_status,
            analyst_decision=decision,
            hard_conflict=hard_conflict,
            review_required=review_required,
            pivot_allowed=pivot_allowed,
            positive_signals=positive_signals,
            negative_signals=negative_signals,
        )

    @staticmethod
    def _identity_support(
        resolution: IdentityResolution | None,
    ) -> float:
        if resolution is None:
            return 0.0

        status = str(
            resolution.status
            or ""
        ).strip().lower()
        cap = _IDENTITY_SUPPORT_CAPS.get(
            status,
            0.0,
        )

        if cap <= 0.0:
            return 0.0

        score = max(
            0.0,
            min(
                100.0,
                float(
                    resolution.score
                    or 0.0
                ),
            ),
        )

        return min(
            cap,
            (score / 100.0) * cap,
        )

    @staticmethod
    def _positive_signals(
        *,
        identity_resolution: IdentityResolution | None,
        relationship_result: RelationshipCorroborationResult | None,
    ) -> tuple[str, ...]:
        signals: list[str] = []

        if identity_resolution is not None:
            signals.extend(
                str(item)
                for item in identity_resolution.matched
                if str(item).strip()
            )

        if relationship_result is not None:
            for signal in relationship_result.signals[:4]:
                text = str(
                    getattr(
                        signal,
                        "associate_label",
                        "",
                    )
                    or ""
                ).strip()
                if text:
                    signals.append(
                        f"Known associate overlap: {text}"
                    )

        return tuple(
            dict.fromkeys(
                signals
            )
        )

    @staticmethod
    def _negative_signals(
        resolution: IdentityResolution | None,
    ) -> tuple[str, ...]:
        if resolution is None:
            return ()

        return tuple(
            dict.fromkeys(
                str(item)
                for item in resolution.conflicts
                if str(item).strip()
            )
        )

    @staticmethod
    def _analyst_decision(
        value: Any,
    ) -> str:
        normalized = str(
            value
            or ""
        ).strip().lower()

        if normalized not in _VALID_ANALYST_DECISIONS:
            return ""

        return normalized

    @staticmethod
    def _confidence(
        value: Any,
    ) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0

        return round(
            max(
                0.0,
                min(
                    1.0,
                    number,
                ),
            ),
            6,
        )


__all__ = [
    "IdentityConfidenceCalibration",
    "IdentityConfidenceCalibrationService",
]

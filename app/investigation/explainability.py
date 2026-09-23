"""Unified Investigation Explainability contracts.

These contracts normalize already-produced explanations from Search, Evidence,
Entity Resolution, Graph analysis and persisted merge history.

They do not calculate scores, choose decisions, rank search hits, merge
entities, or infer causes that the source analytical layer did not provide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any
from uuid import UUID


class InvestigationExplanationDomain(str, Enum):
    SEARCH = "search"
    EVIDENCE = "evidence"
    ENTITY_RESOLUTION = "entity_resolution"
    GRAPH = "graph"
    ENTITY_MERGE = "entity_merge"


class InvestigationExplanationQuestion(str, Enum):
    FOUND = "why_found"
    RANKED = "why_ranked"
    CONFIDENT = "why_confident"
    LINKED = "why_linked"
    RESOLVED = "why_resolved"
    MERGED = "why_merged"
    CONTRADICTED = "why_contradicted"


class InvestigationExplanationEffect(str, Enum):
    SUPPORT = "support"
    CONTRADICT = "contradict"
    LIMITATION = "limitation"
    CONTEXT = "context"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class InvestigationExplanationSubject:
    """Canonical subject identity for an explanation."""

    object_type: str
    object_id: UUID
    related_object_type: str | None = None
    related_object_id: UUID | None = None

    def __post_init__(self) -> None:
        object_type = str(self.object_type or "").strip().casefold()
        if not object_type:
            raise ValueError("object_type cannot be empty.")
        if not isinstance(self.object_id, UUID):
            raise TypeError("object_id must be UUID.")

        related_type = (
            str(self.related_object_type or "").strip().casefold()
            or None
        )
        related_id = self.related_object_id

        if (related_type is None) != (related_id is None):
            raise ValueError(
                "related_object_type and related_object_id must be supplied together."
            )
        if related_id is not None and not isinstance(related_id, UUID):
            raise TypeError("related_object_id must be UUID or None.")

        object.__setattr__(self, "object_type", object_type)
        object.__setattr__(self, "related_object_type", related_type)

    def to_payload(self) -> dict[str, Any]:
        return {
            "objectType": self.object_type,
            "objectId": str(self.object_id),
            "relatedObjectType": self.related_object_type or "",
            "relatedObjectId": (
                str(self.related_object_id)
                if self.related_object_id is not None
                else ""
            ),
        }


@dataclass(frozen=True, slots=True)
class InvestigationExplanationReason:
    """One normalized deterministic explanation reason."""

    code: str
    message: str
    effect: InvestigationExplanationEffect
    score: float | None = None
    method: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        code = str(self.code or "").strip()
        message = str(self.message or "").strip()
        if not code:
            raise ValueError("Explanation reason code cannot be empty.")
        if not message:
            raise ValueError("Explanation reason message cannot be empty.")
        if not isinstance(self.effect, InvestigationExplanationEffect):
            raise TypeError("effect must be InvestigationExplanationEffect.")

        score = self.score
        if score is not None:
            score = float(score)
            if not isfinite(score):
                raise ValueError("Explanation reason score must be finite.")
            object.__setattr__(self, "score", score)

        method = str(self.method or "").strip() or None
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "details", dict(self.details or {}))

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "effect": self.effect.value,
            "score": self.score,
            "method": self.method or "",
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class InvestigationExplanation:
    """One answer to a canonical WHY question."""

    domain: InvestigationExplanationDomain
    question: InvestigationExplanationQuestion
    subject: InvestigationExplanationSubject
    summary: str
    reasons: tuple[InvestigationExplanationReason, ...] = ()
    limitations: tuple[InvestigationExplanationReason, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.domain, InvestigationExplanationDomain):
            raise TypeError("domain must be InvestigationExplanationDomain.")
        if not isinstance(self.question, InvestigationExplanationQuestion):
            raise TypeError("question must be InvestigationExplanationQuestion.")
        if not isinstance(self.subject, InvestigationExplanationSubject):
            raise TypeError("subject must be InvestigationExplanationSubject.")

        summary = str(self.summary or "").strip()
        if not summary:
            raise ValueError("summary cannot be empty.")
        object.__setattr__(self, "summary", summary)

        for collection_name in ("reasons", "limitations"):
            values = getattr(self, collection_name)
            if not isinstance(values, tuple):
                raise TypeError(f"{collection_name} must be tuple.")
            if not all(
                isinstance(value, InvestigationExplanationReason)
                for value in values
            ):
                raise TypeError(
                    f"{collection_name} must contain InvestigationExplanationReason."
                )

        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": "m025b",
            "domain": self.domain.value,
            "question": self.question.value,
            "subject": self.subject.to_payload(),
            "summary": self.summary,
            "reasons": [
                reason.to_payload()
                for reason in self.reasons
            ],
            "limitations": [
                reason.to_payload()
                for reason in self.limitations
            ],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class InvestigationExplainabilityBundle:
    """Deterministic collection of normalized WHY answers."""

    explanations: tuple[InvestigationExplanation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.explanations, tuple):
            raise TypeError("explanations must be tuple.")
        if not all(
            isinstance(value, InvestigationExplanation)
            for value in self.explanations
        ):
            raise TypeError(
                "explanations must contain InvestigationExplanation."
            )

    def for_question(
        self,
        question: InvestigationExplanationQuestion,
    ) -> tuple[InvestigationExplanation, ...]:
        if not isinstance(question, InvestigationExplanationQuestion):
            raise TypeError("question must be InvestigationExplanationQuestion.")
        return tuple(
            explanation
            for explanation in self.explanations
            if explanation.question == question
        )

    def for_subject(
        self,
        object_type: str,
        object_id: UUID,
    ) -> tuple[InvestigationExplanation, ...]:
        normalized_type = str(object_type or "").strip().casefold()
        if not normalized_type:
            raise ValueError("object_type cannot be empty.")
        if not isinstance(object_id, UUID):
            raise TypeError("object_id must be UUID.")
        return tuple(
            explanation
            for explanation in self.explanations
            if (
                explanation.subject.object_type == normalized_type
                and explanation.subject.object_id == object_id
            )
        )

    def to_payload(self) -> list[dict[str, Any]]:
        return [
            explanation.to_payload()
            for explanation in self.explanations
        ]


__all__ = [
    "InvestigationExplainabilityBundle",
    "InvestigationExplanation",
    "InvestigationExplanationDomain",
    "InvestigationExplanationEffect",
    "InvestigationExplanationQuestion",
    "InvestigationExplanationReason",
    "InvestigationExplanationSubject",
]

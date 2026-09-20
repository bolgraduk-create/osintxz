"""R13.26a — shadow Search Quality Engine.

This module is intentionally observational.  It annotates live-search rows with
an explainable quality assessment, but does not decide persistence, recursion,
or visibility in the existing UI result pipeline yet.

The purpose of the shadow phase is to make future relevance changes measurable:
we can see when the new assessment disagrees with the current contextual/
adaptive relevance stack before allowing it to affect search behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from app.application.adaptive_relevance import classify_suppressed_row
from app.application.contextual_relevance import (
    assess_result_row,
    context_boost,
    context_terms_from_profile,
)


_EXACT_KINDS = {
    "username",
    "email",
    "phone",
    "domain",
    "url",
    "ip",
    "hash",
    "lei",
    "orcid",
    "npi",
    "cve",
    "doi",
    "asn",
    "case_number",
    "registration_id",
    "vat_id",
    "repository",
    "crypto_address",
}

_ACCOUNT_TYPES = {
    "account",
    "username",
    "profile",
    "public_account",
    "public_user",
    "social_profile",
    "online_account",
}

_NEGATIVE_STATUS_WORDS = {
    "available",
    "free",
    "missing",
    "not found",
    "not_found",
    "unclaimed",
    "does not exist",
    "not registered",
}


@dataclass(frozen=True, slots=True)
class SearchQualityAssessment:
    tier: str
    score: float
    relevance_score: float
    identity_score: float
    pivot_score: float
    persistence_score: float
    positive_signals: tuple[str, ...]
    negative_signals: tuple[str, ...]
    hard_reject_reason: str
    would_show: bool
    would_explore: bool
    would_persist: bool
    legacy_visible: bool
    legacy_pivot_allowed: bool
    disagreement: bool

    @property
    def label(self) -> str:
        return {
            "strong": "Strong",
            "relevant": "Relevant",
            "possible": "Possible",
            "noise": "Noise",
        }.get(self.tier, self.tier.replace("_", " ").title())

    @property
    def summary(self) -> str:
        positive = list(self.positive_signals[:3])
        negative = list(self.negative_signals[:2])
        if self.hard_reject_reason:
            negative.insert(0, self.hard_reject_reason)
        parts = positive + negative
        return " · ".join(parts) or "No strong quality signals."

    def row_fields(self) -> dict[str, Any]:
        return {
            "qualityTier": self.tier,
            "qualityLabel": self.label,
            "qualityScore": round(float(self.score), 1),
            "qualityRelevanceScore": round(float(self.relevance_score), 1),
            "qualityIdentityScore": round(float(self.identity_score), 1),
            "qualityPivotScore": round(float(self.pivot_score), 1),
            "qualityPersistenceScore": round(float(self.persistence_score), 1),
            "qualityPositiveSignals": list(self.positive_signals),
            "qualityNegativeSignals": list(self.negative_signals),
            "qualityHardRejectReason": self.hard_reject_reason,
            "qualityWouldShow": bool(self.would_show),
            "qualityWouldExplore": bool(self.would_explore),
            "qualityWouldPersist": bool(self.would_persist),
            "qualityLegacyVisible": bool(self.legacy_visible),
            "qualityLegacyPivotAllowed": bool(self.legacy_pivot_allowed),
            "qualityDisagreement": bool(self.disagreement),
            "qualitySummary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class SearchQualitySummary:
    total: int
    strong: int
    relevant: int
    possible: int
    noise: int
    disagreements: int
    would_explore: int
    would_persist: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "strong": self.strong,
            "relevant": self.relevant,
            "possible": self.possible,
            "noise": self.noise,
            "disagreements": self.disagreements,
            "wouldExplore": self.would_explore,
            "wouldPersist": self.would_persist,
        }


def annotate_search_quality_rows(
    rows: Iterable[dict[str, Any]],
    *,
    search_profile: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], SearchQualitySummary]:
    """Return copies of rows annotated by the shadow quality engine."""

    context_terms = context_terms_from_profile(search_profile)
    annotated: list[dict[str, Any]] = []
    counts = {
        "strong": 0,
        "relevant": 0,
        "possible": 0,
        "noise": 0,
        "disagreements": 0,
        "would_explore": 0,
        "would_persist": 0,
    }

    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            continue

        row = dict(raw)
        assessment = assess_search_quality_row(
            row,
            context_terms=context_terms,
        )
        row.update(assessment.row_fields())
        row["qualityObservationId"] = f"obs-{index + 1:04d}"
        annotated.append(row)

        counts[assessment.tier] += 1
        if assessment.disagreement:
            counts["disagreements"] += 1
        if assessment.would_explore:
            counts["would_explore"] += 1
        if assessment.would_persist:
            counts["would_persist"] += 1

    return (
        annotated,
        SearchQualitySummary(
            total=len(annotated),
            strong=counts["strong"],
            relevant=counts["relevant"],
            possible=counts["possible"],
            noise=counts["noise"],
            disagreements=counts["disagreements"],
            would_explore=counts["would_explore"],
            would_persist=counts["would_persist"],
        ),
    )


def quality_trace_rows(
    rows: Iterable[dict[str, Any]],
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Build bounded analyst-facing trace rows from annotated observations."""

    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "observationId": str(row.get("qualityObservationId") or ""),
                "lane": str(row.get("lane") or ""),
                "source": str(row.get("source") or ""),
                "seed": str(row.get("seed") or ""),
                "seedType": str(row.get("seedType") or ""),
                "title": str(row.get("title") or "Observation"),
                "detail": str(row.get("detail") or ""),
                "type": str(row.get("type") or ""),
                "url": str(row.get("url") or ""),
                "depth": _safe_int(row.get("depth")),
                "qualityTier": str(row.get("qualityTier") or "noise"),
                "qualityLabel": str(row.get("qualityLabel") or "Noise"),
                "qualityScore": _safe_float(row.get("qualityScore")),
                "qualityRelevanceScore": _safe_float(
                    row.get("qualityRelevanceScore")
                ),
                "qualityIdentityScore": _safe_float(
                    row.get("qualityIdentityScore")
                ),
                "qualityPivotScore": _safe_float(row.get("qualityPivotScore")),
                "qualityPersistenceScore": _safe_float(
                    row.get("qualityPersistenceScore")
                ),
                "qualityPositiveSignals": list(
                    row.get("qualityPositiveSignals") or []
                ),
                "qualityNegativeSignals": list(
                    row.get("qualityNegativeSignals") or []
                ),
                "qualityHardRejectReason": str(
                    row.get("qualityHardRejectReason") or ""
                ),
                "qualityWouldShow": bool(row.get("qualityWouldShow")),
                "qualityWouldExplore": bool(row.get("qualityWouldExplore")),
                "qualityWouldPersist": bool(row.get("qualityWouldPersist")),
                "qualityLegacyVisible": bool(row.get("qualityLegacyVisible")),
                "qualityLegacyPivotAllowed": bool(
                    row.get("qualityLegacyPivotAllowed")
                ),
                "qualityDisagreement": bool(row.get("qualityDisagreement")),
                "qualitySummary": str(row.get("qualitySummary") or ""),
            }
        )

    out.sort(
        key=lambda item: (
            0 if item["qualityDisagreement"] else 1,
            -float(item["qualityScore"]),
            str(item["source"]).casefold(),
            str(item["title"]).casefold(),
        )
    )
    return out[:limit] if limit > 0 else out


def assess_search_quality_row(
    row: dict[str, Any],
    *,
    context_terms: Iterable[str] = (),
) -> SearchQualityAssessment:
    """Assess one raw observation without changing current search behaviour."""

    relevance = assess_result_row(row)
    probe = dict(row)
    probe.update(relevance.row_fields())

    boost, matched_context = context_boost(probe, context_terms)
    probe["contextBoost"] = boost
    probe["contextMatchedTerms"] = list(matched_context)

    adaptive = (
        classify_suppressed_row(probe)
        if not relevance.keep_clean
        else None
    )
    legacy_visible = bool(
        relevance.keep_clean
        or (adaptive is not None and adaptive.visible_as_possible)
    )

    positive: list[str] = []
    negative: list[str] = []

    for item in relevance.matched:
        _append_unique(positive, str(item))
    for item in relevance.reasons:
        if relevance.keep_clean:
            _append_unique(positive, str(item))
        else:
            _append_unique(negative, str(item))

    if matched_context:
        _append_unique(
            positive,
            "Context matches: " + ", ".join(str(x) for x in matched_context[:3]),
        )

    seed_kind = _kind(row.get("seedType"))
    family = _kind(row.get("type"))
    exact_kind = seed_kind in _EXACT_KINDS

    provider_score = _provider_score(row)
    if provider_score >= 85:
        _append_unique(positive, "High-confidence provider observation")
    elif provider_score and provider_score < 55:
        _append_unique(negative, "Low provider confidence")

    corroboration = max(1, _safe_int(row.get("corroborationCount")) or 1)
    if corroboration > 1:
        _append_unique(
            positive,
            f"{corroboration} independent sources corroborate this observation",
        )

    if row.get("url"):
        _append_unique(positive, "Concrete source/profile URL")

    identifiers = row.get("identifiers")
    if isinstance(identifiers, dict) and any(
        str(value or "").strip() for value in identifiers.values()
    ):
        _append_unique(positive, "Structured identifier present")

    identity_score, identity_applicable = _identity_component(row)
    identity_status = _kind(row.get("identityStatus"))
    if identity_status in {"strong", "supported"}:
        _append_unique(
            positive,
            f"Identity alignment is {identity_status}",
        )
    elif identity_status == "conflicting":
        _append_unique(negative, "Identity signals conflict")

    hard_reject = _hard_reject_reason(row, relevance_status=relevance.status)
    if hard_reject:
        _append_unique(negative, hard_reject)

    candidate_only = bool(row.get("candidateOnly"))
    if candidate_only:
        _append_unique(negative, "Review-only candidate")

    relevance_score = _clamp(
        float(relevance.score)
        + min(10.0, float(boost))
        + min(6.0, max(0, corroboration - 1) * 3.0)
    )

    context_component = min(100.0, float(boost) * 10.0)
    if identity_applicable:
        score = (
            relevance_score * 0.52
            + identity_score * 0.23
            + provider_score * 0.15
            + context_component * 0.10
        )
    else:
        score = (
            relevance_score * 0.72
            + provider_score * 0.18
            + context_component * 0.10
        )

    if candidate_only:
        score -= 8.0
    score -= min(15.0, max(0, _safe_int(row.get("depth"))) * 3.0)
    score += min(8.0, max(0, corroboration - 1) * 4.0)

    if hard_reject:
        score = min(score, 12.0)

    score = _clamp(score)

    if score >= 85.0:
        tier = "strong"
    elif score >= 65.0:
        tier = "relevant"
    elif score >= 35.0:
        tier = "possible"
    else:
        tier = "noise"

    pivot_score = _pivot_score(
        row=row,
        seed_kind=seed_kind,
        exact_kind=exact_kind,
        relevance_score=relevance_score,
        provider_score=provider_score,
        identity_score=identity_score,
        hard_reject=hard_reject,
        candidate_only=candidate_only,
        corroboration=corroboration,
    )
    persistence_score = _persistence_score(
        row=row,
        relevance_score=relevance_score,
        provider_score=provider_score,
        identity_score=identity_score,
        identity_applicable=identity_applicable,
        hard_reject=hard_reject,
        candidate_only=candidate_only,
        corroboration=corroboration,
    )

    would_show = bool(not hard_reject and tier != "noise")
    would_explore = bool(
        not hard_reject
        and pivot_score >= 68.0
        and (
            exact_kind
            or relevance.pivot_allowed
            or corroboration > 1
        )
    )
    would_persist = bool(
        not hard_reject
        and not candidate_only
        and persistence_score >= 82.0
    )

    disagreement = bool(
        would_show != legacy_visible
        or would_explore != bool(relevance.pivot_allowed)
    )

    return SearchQualityAssessment(
        tier=tier,
        score=score,
        relevance_score=relevance_score,
        identity_score=identity_score,
        pivot_score=pivot_score,
        persistence_score=persistence_score,
        positive_signals=tuple(positive[:10]),
        negative_signals=tuple(negative[:10]),
        hard_reject_reason=hard_reject,
        would_show=would_show,
        would_explore=would_explore,
        would_persist=would_persist,
        legacy_visible=legacy_visible,
        legacy_pivot_allowed=bool(relevance.pivot_allowed),
        disagreement=disagreement,
    )


def _pivot_score(
    *,
    row: dict[str, Any],
    seed_kind: str,
    exact_kind: bool,
    relevance_score: float,
    provider_score: float,
    identity_score: float,
    hard_reject: str,
    candidate_only: bool,
    corroboration: int,
) -> float:
    if hard_reject:
        return 0.0

    score = relevance_score * 0.62 + provider_score * 0.18

    if exact_kind:
        score += 12.0
    if identity_score >= 80.0:
        score += 8.0
    if corroboration > 1:
        score += min(10.0, (corroboration - 1) * 5.0)
    if candidate_only:
        score -= 18.0
    if seed_kind in {"person", "person_name", "organization", "address", "keyword"}:
        score -= 18.0
    if _kind(row.get("type")) in _ACCOUNT_TYPES and seed_kind == "username":
        score += 5.0

    return _clamp(score)


def _persistence_score(
    *,
    row: dict[str, Any],
    relevance_score: float,
    provider_score: float,
    identity_score: float,
    identity_applicable: bool,
    hard_reject: str,
    candidate_only: bool,
    corroboration: int,
) -> float:
    if hard_reject:
        return 0.0

    if identity_applicable:
        score = (
            relevance_score * 0.58
            + provider_score * 0.20
            + identity_score * 0.22
        )
    else:
        score = relevance_score * 0.74 + provider_score * 0.26

    if corroboration > 1:
        score += min(8.0, (corroboration - 1) * 4.0)
    if candidate_only:
        score -= 22.0
    if not row.get("url") and not row.get("identifiers"):
        score -= 8.0

    return _clamp(score)


def _identity_component(row: dict[str, Any]) -> tuple[float, bool]:
    status = _kind(row.get("identityStatus"))
    alignment = _safe_float(row.get("identityAlignmentScore"))
    match_score = _safe_float(row.get("identityMatchScore"))

    if status == "strong":
        return max(92.0, alignment, match_score), True
    if status == "supported":
        return max(78.0, alignment, match_score), True
    if status == "possible":
        return max(55.0, alignment, match_score), True
    if status == "insufficient":
        return max(30.0, min(54.0, alignment or match_score)), True
    if status == "conflicting":
        return 0.0, True
    if status and status != "not_applicable":
        return max(alignment, match_score), True

    if match_score > 0:
        return match_score, True

    return 0.0, False


def _provider_score(row: dict[str, Any]) -> float:
    values: list[float] = []
    for key in ("confidence", "reliability"):
        raw = row.get(key)
        if raw is None:
            continue
        value = _safe_float(raw)
        if value <= 1.0:
            value *= 100.0
        values.append(_clamp(value))

    if not values:
        # Unknown provider confidence should be neutral, not equivalent to bad.
        return 65.0
    return sum(values) / len(values)


def _hard_reject_reason(
    row: dict[str, Any],
    *,
    relevance_status: str,
) -> str:
    if str(row.get("accountVerificationStatus") or "").strip().casefold() == "invalid":
        return str(
            row.get("accountVerificationReason")
            or "Independent profile validation indicates the account is absent"
        )

    if bool(row.get("identityRejected")):
        return "Explicit identity mismatch"

    if _kind(row.get("identityStatus")) == "conflicting":
        return "Explicit identity conflict"

    metadata = row.get("findingMetadata")
    if isinstance(metadata, dict) and _metadata_negative(metadata):
        return "Provider explicitly reports account/identifier as absent"

    if str(relevance_status or "").casefold() == "contradictory":
        return "Contextual relevance is contradictory"

    return ""


def _metadata_negative(metadata: dict[str, Any]) -> bool:
    if metadata.get("available") is True:
        return True

    for key in ("exists", "claimed", "registered", "used"):
        if key in metadata and metadata.get(key) is False:
            return True

    status = str(
        metadata.get("status")
        or metadata.get("state")
        or metadata.get("exists")
        or ""
    ).strip().casefold()
    return status in _NEGATIVE_STATUS_WORDS


def _append_unique(items: list[str], value: str) -> None:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return
    if all(existing.casefold() != text.casefold() for existing in items):
        items.append(text)


def _kind(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value or "").strip().casefold(),
    ).strip("_")


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)

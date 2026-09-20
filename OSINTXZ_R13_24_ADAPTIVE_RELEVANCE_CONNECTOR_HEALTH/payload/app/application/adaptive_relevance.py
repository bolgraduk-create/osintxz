"""Adaptive visibility policy for unified investigation results.

R13.24 deliberately separates what an analyst may inspect from what the system
may persist or follow automatically.  The strict pre-persistence gate remains
unchanged.  This module only decides whether a row that failed the strict Clean
gate is still useful enough to surface as a Possible result.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


_EXACT_KINDS = {
    "username", "email", "phone", "domain", "url", "ip", "hash", "lei",
    "orcid", "npi", "cve", "doi", "asn", "case_number", "registration_id",
    "vat_id", "repository", "crypto_address",
}
_NEGATIVE_MARKERS = (
    "match: false", "match false", '"match": false', "matched: false",
    "does not match", "outside the searched", "conflicting",
)


@dataclass(frozen=True, slots=True)
class AdaptiveVisibility:
    tier: str
    score: float
    reason: str

    @property
    def visible_as_possible(self) -> bool:
        return self.tier == "possible"

    def row_fields(self) -> dict[str, Any]:
        return {
            "visibilityTier": self.tier,
            "visibilityScore": round(float(self.score), 1),
            "visibilityReason": self.reason,
        }


def classify_suppressed_row(row: dict[str, Any]) -> AdaptiveVisibility:
    """Return a conservative analyst-visibility tier for a suppressed row.

    Exact identifiers stay strict.  A weak username/domain/email/etc. result is
    *not* resurrected merely because its provider was queried.  Broader content
    and organization/name records may be surfaced as Possible when there is
    meaningful contextual support, but they remain non-persistable and
    non-pivotable.
    """
    kind = _kind(row.get("seedType"))
    relevance_status = str(row.get("contextRelevanceStatus") or "").casefold()
    relevance_score = _float(row.get("contextRelevanceScore"))
    matched_context = [
        str(x).strip()
        for x in list(row.get("contextMatchedTerms") or [])[:8]
        if str(x or "").strip()
    ]
    material = " ".join(
        str(row.get(key) or "")
        for key in ("title", "detail", "meta", "url")
    ).casefold()

    if bool(row.get("identityRejected")) or any(marker in material for marker in _NEGATIVE_MARKERS):
        return AdaptiveVisibility("suppressed", max(0.0, relevance_score), "Explicit mismatch or contradictory evidence")

    # Exact identifiers remain deliberately strict: visibility must not become
    # a back door around the username/URL relevance work from R13.21.x.
    if kind in _EXACT_KINDS:
        return AdaptiveVisibility("suppressed", relevance_score, "Exact identifier did not satisfy the strict target gate")

    if relevance_status == "candidate":
        return AdaptiveVisibility(
            "possible",
            max(45.0, relevance_score),
            "Provider returned a plausible but non-pivotable candidate",
        )

    if kind == "keyword" and relevance_score >= 35.0:
        return AdaptiveVisibility(
            "possible", max(42.0, relevance_score),
            "Context keyword is present; analyst review required",
        )

    # Two independent context terms are enough to show a broad content row for
    # analyst inspection, but never enough to save it or pivot from it.
    if len(matched_context) >= 2:
        return AdaptiveVisibility(
            "possible", min(69.0, 42.0 + len(matched_context) * 6.0),
            "Multiple known-profile context signals match",
        )

    # Person/organization records with one context signal and a moderate seed
    # score are useful to inspect, but not to trust.
    if kind in {"person_name", "organization", "address", "location"} and matched_context and relevance_score >= 18.0:
        return AdaptiveVisibility(
            "possible", min(64.0, max(38.0, relevance_score + 12.0)),
            "Partial seed match plus independent profile context",
        )

    return AdaptiveVisibility("suppressed", relevance_score, "Insufficient evidence for analyst-facing Possible results")


def annotate_relevant_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    status = str(out.get("contextRelevanceStatus") or "").casefold()
    tier = "relevant"
    if status == "corroborated" or int(out.get("corroborationCount") or 0) > 1:
        tier = "corroborated"
    elif status in {"candidate", "possible", "insufficient"}:
        tier = "possible"
    out.setdefault("visibilityTier", tier)
    out.setdefault("visibilityScore", _float(out.get("contextRelevanceScore")))
    out.setdefault("visibilityReason", str(out.get("contextRelevanceSummary") or "Passed strict Clean gate"))
    return out


def _kind(value: Any) -> str:
    raw = getattr(value, "value", value)
    return re.sub(r"[^a-z0-9]+", "_", str(raw or "").casefold()).strip("_")


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0

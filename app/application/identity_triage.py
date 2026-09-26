"""Identity triage and cross-platform correlation.

This layer is presentation-safe: it never mutates or deletes source rows, never
turns machine confidence into analyst confirmation, and never persists a
cross-platform identity assertion.  It only groups already-produced public
observations for review.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit


_REJECTED = {"invalid", "rejected", "conflicting"}
_REVIEW = {"reported", "unreachable", "uncertain", "blocked", "review", "possible"}
_CONFIRMED = {"verified", "confirmed"}
_LIKELY = {"likely", "supported", "strong"}


@dataclass(frozen=True, slots=True)
class IdentityTriageSummary:
    total: int
    confirmed: int
    needs_review: int
    rejected: int
    unreviewed: int
    clusters: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "confirmed": self.confirmed,
            "needsReview": self.needs_review,
            "rejected": self.rejected,
            "unreviewed": self.unreviewed,
            "clusters": self.clusters,
        }


def build_identity_triage(
    rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], IdentityTriageSummary]:
    """Return triage rows and non-authoritative cross-platform clusters."""

    triage: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        if not _is_identity_like(raw):
            continue
        item = dict(raw)
        status = _triage_status(item)
        signals = _signals(item)
        score = _score(item, status=status, signals=signals)
        item.update(
            {
                "triageStatus": status,
                "triageLabel": _label(status),
                "triageScore": score,
                "triageSignals": signals,
                "triageSummary": " · ".join(signals[:4])
                or "No independent identity support yet.",
                "triageAuthoritative": status in {"confirmed", "rejected"}
                and _analyst_status(item) in {"confirmed", "rejected"},
            }
        )
        triage.append(item)

    triage.sort(
        key=lambda row: (
            _status_rank(str(row.get("triageStatus") or "")),
            -float(row.get("triageScore") or 0.0),
            str(row.get("title") or row.get("value") or "").casefold(),
        )
    )

    clusters = _cross_platform_clusters(triage)
    counts = {
        "confirmed": 0,
        "needs_review": 0,
        "rejected": 0,
        "unreviewed": 0,
    }
    for row in triage:
        key = str(row.get("triageStatus") or "unreviewed")
        if key == "needs_review":
            counts["needs_review"] += 1
        elif key in counts:
            counts[key] += 1
        else:
            counts["unreviewed"] += 1

    return (
        triage,
        clusters,
        IdentityTriageSummary(
            total=len(triage),
            confirmed=counts["confirmed"],
            needs_review=counts["needs_review"],
            rejected=counts["rejected"],
            unreviewed=counts["unreviewed"],
            clusters=len(clusters),
        ),
    )


def _is_identity_like(row: dict[str, Any]) -> bool:
    kind = str(row.get("type") or row.get("entityType") or "").casefold()
    if kind in {"account", "username", "public_user", "profile", "person", "identity"}:
        return True
    identifiers = row.get("identifiers")
    if isinstance(identifiers, dict) and any(
        str(identifiers.get(key) or "").strip()
        for key in ("username", "handle", "email")
    ):
        return True
    return bool(row.get("accountVerificationStatus") or row.get("identityStatus"))


def _analyst_status(row: dict[str, Any]) -> str:
    for key in ("reviewStatus", "analystDecision", "identityReviewStatus"):
        value = str(row.get(key) or "").strip().casefold()
        if value:
            return value
    review = row.get("identityReview")
    if isinstance(review, dict):
        return str(review.get("decision") or "").strip().casefold()
    return ""


def _triage_status(row: dict[str, Any]) -> str:
    analyst = _analyst_status(row)
    if analyst == "confirmed":
        return "confirmed"
    if analyst == "rejected":
        return "rejected"
    if analyst in {"review", "needs_review"}:
        return "needs_review"

    values = {
        str(row.get("accountVerificationStatus") or "").strip().casefold(),
        str(row.get("identityStatus") or "").strip().casefold(),
        str(row.get("contextRelevanceStatus") or "").strip().casefold(),
    }
    if values & _REJECTED:
        return "rejected"
    if values & _CONFIRMED:
        return "confirmed"
    if values & (_REVIEW | _LIKELY):
        return "needs_review"
    return "unreviewed"


def _signals(row: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    analyst = _analyst_status(row)
    if analyst == "confirmed":
        signals.append("Analyst confirmed")
    elif analyst == "rejected":
        signals.append("Analyst rejected")
    elif analyst in {"review", "needs_review"}:
        signals.append("Analyst marked for review")

    verification = str(row.get("accountVerificationStatus") or "").strip().casefold()
    if verification:
        signals.append("Profile verification: " + verification.replace("_", " "))

    identity = str(row.get("identityStatus") or "").strip().casefold()
    if identity:
        signals.append("Identity alignment: " + identity.replace("_", " "))

    corroboration = int(row.get("corroborationCount") or row.get("accountProviderCorroboration") or 0)
    if corroboration > 1:
        signals.append(f"{corroboration} independent source observations")

    for key, label in (
        ("accountVerificationEvidenceSignals", ""),
        ("identityMatched", ""),
        ("identitySignals", ""),
    ):
        value = row.get(key)
        if isinstance(value, list):
            for item in value[:4]:
                text = str(item or "").strip()
                if text and text not in signals:
                    signals.append(text)

    if row.get("calibrationHardConflict"):
        signals.append("Hard identity conflict")
    negative = row.get("calibrationNegativeSignals")
    if isinstance(negative, list):
        for item in negative[:3]:
            text = str(item or "").strip()
            if text:
                signals.append("Conflict: " + text)

    return signals[:10]


def _score(row: dict[str, Any], *, status: str, signals: list[str]) -> float:
    candidates = [
        row.get("calibratedConfidence"),
        row.get("confidence"),
        row.get("identityAlignmentScore"),
        row.get("identityMatchScore"),
        row.get("accountVerificationEvidenceScore"),
        row.get("contextRelevanceScore"),
    ]
    numeric: list[float] = []
    for value in candidates:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if 0.0 <= number <= 1.0:
            number *= 100.0
        numeric.append(max(0.0, min(100.0, number)))
    base = max(numeric, default=0.0)
    if len(signals) >= 3:
        base = min(100.0, base + 5.0)
    if status == "rejected":
        base = min(base, 35.0)
    return round(base, 1)


def _cluster_key(row: dict[str, Any]) -> tuple[str, str] | None:
    identifiers = row.get("identifiers")
    identifiers = identifiers if isinstance(identifiers, dict) else {}
    username = ""
    for value in (
        identifiers.get("username"),
        identifiers.get("handle"),
        row.get("username"),
    ):
        username = str(value or "").strip().lstrip("@").casefold()
        if username:
            break
    if username:
        return ("username", username)

    email = str(identifiers.get("email") or row.get("email") or "").strip().casefold()
    if email:
        return ("email", email)

    url = str(row.get("url") or "").strip()
    if url:
        parsed = urlsplit(url)
        host = str(parsed.hostname or "").casefold()
        path = parsed.path.rstrip("/").casefold()
        if host and path:
            return ("url", host + path)
    return None


def _platform(row: dict[str, Any]) -> str:
    for key in ("service", "platform", "source"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    url = str(row.get("url") or "").strip()
    if url:
        return str(urlsplit(url).hostname or "")
    return "Unknown"


def _cross_platform_clusters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if str(row.get("triageStatus") or "") == "rejected":
            continue
        key = _cluster_key(row)
        if key is not None:
            groups.setdefault(key, []).append(row)

    output: list[dict[str, Any]] = []
    for (kind, value), members in groups.items():
        platforms = sorted({_platform(row) for row in members if _platform(row)})
        if len(platforms) < 2:
            continue
        score = max(float(row.get("triageScore") or 0.0) for row in members)
        support = min(18.0, 6.0 * (len(platforms) - 1))
        output.append(
            {
                "clusterKind": kind,
                "clusterValue": value,
                "platforms": platforms,
                "memberCount": len(members),
                "correlationScore": round(min(100.0, score + support), 1),
                "correlationLabel": "Cross-platform candidate",
                "correlationSummary": (
                    f"Same {kind.replace('_', ' ')} observed across "
                    f"{len(platforms)} platforms. This is supporting evidence, not proof of ownership."
                ),
                "memberUrls": [
                    str(row.get("url") or "")
                    for row in members
                    if str(row.get("url") or "").strip()
                ][:12],
            }
        )

    output.sort(
        key=lambda item: (
            -float(item.get("correlationScore") or 0.0),
            -int(item.get("memberCount") or 0),
            str(item.get("clusterValue") or ""),
        )
    )
    return output


def _label(status: str) -> str:
    return {
        "confirmed": "Confirmed",
        "needs_review": "Needs review",
        "rejected": "Rejected",
        "unreviewed": "Unreviewed",
    }.get(status, "Unreviewed")


def _status_rank(status: str) -> int:
    return {
        "needs_review": 0,
        "unreviewed": 1,
        "confirmed": 2,
        "rejected": 3,
    }.get(status, 4)


__all__ = ["IdentityTriageSummary", "build_identity_triage"]

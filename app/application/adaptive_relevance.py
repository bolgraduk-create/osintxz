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
from urllib.parse import parse_qsl, urlsplit


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

    if str(row.get("accountVerificationStatus") or "").strip().casefold() == "invalid":
        return AdaptiveVisibility(
            "suppressed",
            max(0.0, relevance_score),
            str(row.get("accountVerificationReason") or "Independent profile validation indicates the account is absent"),
        )

    if bool(row.get("identityRejected")) or any(marker in material for marker in _NEGATIVE_MARKERS):
        return AdaptiveVisibility("suppressed", max(0.0, relevance_score), "Explicit mismatch or contradictory evidence")

    # Exact identifiers stay strict for Clean/persistence/pivots, but R13.24.2
    # allows analyst-visible Possible rows when the returned record contains a
    # real, inspectable relation to the searched identifier.  This is deliberately
    # weaker than the strict gate and never promotes the row back to Clean.
    if kind in _EXACT_KINDS:
        related, relation_score, relation_reason = _weak_exact_relation(row, kind=kind)
        if related:
            return AdaptiveVisibility(
                "possible",
                max(relevance_score, relation_score),
                relation_reason,
            )
        return AdaptiveVisibility(
            "suppressed",
            relevance_score,
            "No meaningful relation to the searched exact identifier",
        )

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


_ACCOUNT_TYPES = {
    "account", "username", "public_account", "public_user", "profile",
    "social_profile", "online_account",
}
_POSITIVE_STATUS = {
    "found", "exists", "claimed", "registered", "used", "taken",
    "unavailable", "success", "true",
}
_NEGATIVE_STATUS = {
    "available", "free", "not found", "not_found", "missing", "unclaimed",
    "false",
}


def _weak_exact_relation(row: dict[str, Any], *, kind: str) -> tuple[bool, float, str]:
    """Return a weak-but-real analyst relation for an exact identifier.

    This is intentionally *not* the Clean gate.  It exists so OSINT tools can
    surface imperfect but clearly related observations in Possible while the
    persistence/autopivot layer remains exact.  A provider route by itself is
    never enough: the row must contain the searched value, share URL scope, or
    carry explicit positive account metadata.
    """
    seed = str(row.get("seed") or "").strip()
    if not seed:
        return False, 0.0, ""

    metadata = row.get("findingMetadata")
    if not isinstance(metadata, dict):
        metadata = {}
    if _metadata_negative(metadata):
        return False, 0.0, ""

    identifiers = row.get("identifiers")
    if not isinstance(identifiers, dict):
        identifiers = {}

    title = str(row.get("title") or "")
    detail = str(row.get("detail") or "")
    meta = str(row.get("meta") or "")
    url = str(row.get("url") or "")
    material = " ".join((title, detail, meta, url))

    normalized_seed = _normalize_identifier(kind, seed)
    if not normalized_seed:
        return False, 0.0, ""

    # Structured identifier values are a direct relation even if another
    # strict rule rejected the row for presentation/pivot reasons.
    for key, value in identifiers.items():
        key_kind = _kind(key)
        if key_kind == kind or (kind == "username" and key_kind in {"handle", "login", "user_name"}):
            if _normalize_identifier(kind, value) == normalized_seed:
                return True, 68.0, f"Returned {kind.replace('_', ' ')} identifier matches the search"

    if kind == "username":
        if _bounded_username_occurrence(seed, material):
            return True, 58.0, "Searched username appears directly in the returned record"
        if _username_any_url_relation(seed, url or material):
            return True, 56.0, "Returned URL contains the searched username"
        family = _kind(row.get("type"))
        if family in _ACCOUNT_TYPES and _metadata_positive(metadata):
            return True, 54.0, "Username-checking source reported a positive account observation"
        return False, 0.0, ""

    if kind == "url":
        if _same_url_scope(seed, url or material):
            return True, 52.0, "Returned URL stays inside the searched URL scope"
        return False, 0.0, ""

    if kind == "domain":
        if _domain_relation(seed, url or material):
            return True, 56.0, "Returned record references the searched domain or a subdomain"
        return False, 0.0, ""

    if kind == "email":
        if normalized_seed in str(material).casefold():
            return True, 58.0, "Searched email appears in the returned record"
        if _kind(row.get("type")) in _ACCOUNT_TYPES and _metadata_positive(metadata):
            # Email enumeration/account-discovery tools may emit a service hit
            # without echoing the address into every compact row.
            return True, 50.0, "Account-discovery source reported a positive observation for the searched email"
        return False, 0.0, ""

    if kind == "phone":
        compact = re.sub(r"[^0-9+]", "", material)
        if normalized_seed and normalized_seed in compact:
            return True, 58.0, "Searched phone number appears in the returned record"
        return False, 0.0, ""

    # CVEs, hashes, DOI, LEI, ORCID, NPI, case numbers and similar identifiers
    # are only useful as Possible when the identifier itself is visible.
    compact_kinds = {"hash", "lei", "orcid", "npi", "cve", "asn"}
    haystack = (
        re.sub(r"[^A-Za-z0-9+]", "", material).casefold()
        if kind in compact_kinds
        else " ".join(re.findall(r"[^\\W_]+|https?://\\S+", material, flags=re.UNICODE)).casefold()
    )
    needle = (
        re.sub(r"[^A-Za-z0-9+]", "", seed).casefold()
        if kind in compact_kinds
        else normalized_seed.casefold()
    )
    if needle and needle in haystack:
        return True, 55.0, f"Searched {kind.replace('_', ' ')} appears in the returned record"
    return False, 0.0, ""



def _normalize_identifier(kind: str, value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    kind = _kind(kind)
    if kind == "username":
        return raw.lstrip("@").casefold()
    if kind == "email":
        return raw.casefold()
    if kind == "phone":
        return ("+" if raw.startswith("+") else "") + "".join(ch for ch in raw if ch.isdigit())
    if kind == "domain":
        text = re.sub(r"^https?://", "", raw.casefold()).split("/", 1)[0].rstrip(".")
        return text[4:] if text.startswith("www.") else text
    if kind == "url":
        try:
            parsed = urlsplit(raw if "://" in raw else "https://" + raw)
        except ValueError:
            return raw.casefold()
        host = (parsed.hostname or "").casefold().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/") or "/"
        return host + path + (("?" + parsed.query) if parsed.query else "")
    if kind in {"hash", "lei", "orcid", "npi", "cve", "asn"}:
        return re.sub(r"[^A-Za-z0-9+]", "", raw).casefold()
    return " ".join(re.findall(r"[^\W_]+", raw, flags=re.UNICODE)).casefold()

def _metadata_positive(metadata: dict[str, Any]) -> bool:
    if not isinstance(metadata, dict):
        return False
    if metadata.get("registration_confirmed") is True:
        return True
    for key in ("exists", "claimed", "registered", "used"):
        if metadata.get(key) is True:
            return True
    if metadata.get("available") is False and metadata.get("success") is not False:
        # Common username/email enumeration convention: unavailable means taken.
        return True
    status = str(metadata.get("status") or metadata.get("state") or metadata.get("result") or "").strip().casefold()
    return status in _POSITIVE_STATUS


def _metadata_negative(metadata: dict[str, Any]) -> bool:
    if not isinstance(metadata, dict):
        return False
    if metadata.get("available") is True:
        return True
    for key in ("exists", "claimed", "registered", "used"):
        if metadata.get(key) is False:
            return True
    status = str(metadata.get("status") or metadata.get("state") or metadata.get("result") or "").strip().casefold()
    return status in _NEGATIVE_STATUS


def _bounded_username_occurrence(username: str, material: str) -> bool:
    wanted = str(username or "").strip().lstrip("@").casefold()
    if not wanted:
        return False
    # Usernames commonly contain dots, dashes and underscores.  Treat those as
    # username characters so `alex` does not match `alex_dev` accidentally.
    pattern = rf"(?<![A-Za-z0-9_.-])@?{re.escape(wanted)}(?![A-Za-z0-9_.-])"
    return re.search(pattern, str(material or "").casefold()) is not None


def _username_any_url_relation(username: str, value: str) -> bool:
    wanted = str(username or "").strip().lstrip("@").casefold()
    if not wanted:
        return False
    urls = re.findall(r"https?://[^\\s<>\"]+", str(value or ""))
    direct = str(value or "").strip()
    if direct.startswith(("http://", "https://")) and direct not in urls:
        urls.insert(0, direct)
    for found in urls:
        try:
            parsed = urlsplit(found)
        except ValueError:
            continue
        segments = [segment.casefold() for segment in parsed.path.split("/") if segment]
        if wanted in segments:
            return True
        for key, val in parse_qsl(parsed.query, keep_blank_values=True):
            if wanted in {str(key).casefold(), str(val).casefold().lstrip("@")}:
                return True
    return False


def _same_url_scope(seed: str, value: str) -> bool:
    """Return True only when a returned URL stays in the searched URL scope.

    Same-host alone is intentionally insufficient. For a seed such as
    ``https://gitlab.com/torvalds`` we accept descendants like
    ``/torvalds/linux`` but reject unrelated accounts such as
    ``/adamstoolkit``. A host-root seed (``https://example.com/``) may still
    surface same-host pages as Possible because the seed itself defines only
    host scope.
    """
    try:
        seed_raw = str(seed or "").strip()
        if not seed_raw:
            return False
        seed_parsed = urlsplit(seed_raw if "://" in seed_raw else "https://" + seed_raw)
    except ValueError:
        return False

    seed_host = (seed_parsed.hostname or "").casefold().rstrip(".")
    if seed_host.startswith("www."):
        seed_host = seed_host[4:]
    if not seed_host:
        return False

    seed_path = re.sub(r"/{2,}", "/", seed_parsed.path or "/").rstrip("/") or "/"

    urls = re.findall(r"https?://[^\\s<>\"]+", str(value or ""))
    direct = str(value or "").strip()
    if direct.startswith(("http://", "https://")) and direct not in urls:
        urls.insert(0, direct)

    for item in urls:
        try:
            parsed = urlsplit(item)
        except ValueError:
            continue
        host = (parsed.hostname or "").casefold().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        if host != seed_host:
            continue

        candidate_path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/") or "/"
        if seed_path == "/":
            return True
        if candidate_path == seed_path:
            return True
        if candidate_path.startswith(seed_path + "/"):
            return True
        if seed_path.startswith(candidate_path + "/"):
            return True

    return False


def _domain_relation(seed: str, value: str) -> bool:
    domain = str(seed or "").strip().casefold()
    domain = re.sub(r"^https?://", "", domain).split("/", 1)[0].rstrip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain:
        return False
    for item in re.findall(r"https?://[^\\s<>\"]+", str(value or "")):
        host = _host(item)
        if host and (host == domain or host.endswith("." + domain)):
            return True
    token_pattern = rf"(?<![A-Za-z0-9.-]){re.escape(domain)}(?![A-Za-z0-9.-])"
    return re.search(token_pattern, str(value or "").casefold()) is not None


def _host(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        host = (urlsplit(raw).hostname or "").casefold().rstrip(".")
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host

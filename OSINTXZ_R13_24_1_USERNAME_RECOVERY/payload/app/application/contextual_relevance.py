"""R13.21.1 — contextual relevance for unified investigation results.

The module scores whether one provider record is actually relevant to the
specific seed that produced it.  It is intentionally conservative: weak name
or organization token overlap is not enough to enter the Clean view or to
produce automatic pivots.  Raw provider output remains available separately.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from typing import Any, Iterable
from urllib.parse import urlsplit

from app.application.person_name_relevance import match_person_name_record


_GENERIC_ORG_TOKENS = {
    "foundation", "fund", "company", "co", "corporation", "corp", "inc",
    "incorporated", "limited", "ltd", "llc", "plc", "group", "holding",
    "holdings", "association", "society", "organization", "organisation",
    "institute", "institution", "center", "centre", "international",
    "global", "services", "service", "systems", "system", "solutions",
}

_USERNAME_KEYS = {
    "username", "user_name", "handle", "login", "github_username",
    "gitlab_username", "twitter_username", "screen_name",
}

_EXACT_TYPES = {
    "username", "email", "phone", "registration_id", "vat_id", "lei",
    "domain", "url", "ip", "asn", "hash", "orcid", "npi", "cve", "doi",
    "case_number", "crypto_address", "repository",
}


@dataclass(frozen=True, slots=True)
class RelevanceAssessment:
    status: str
    score: float
    matched: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    keep_clean: bool = True
    pivot_allowed: bool = True

    @property
    def label(self) -> str:
        return {
            "corroborated": "Corroborated",
            "relevant": "Relevant",
            "candidate": "Candidate",
            "low_relevance": "Low relevance",
            "contradictory": "Contradictory",
            "not_applicable": "Not scored",
        }.get(self.status, self.status.replace("_", " ").title())

    @property
    def summary(self) -> str:
        return " · ".join((*self.matched[:3], *self.reasons[:2])) or "No contextual match evidence."

    def row_fields(self) -> dict[str, Any]:
        return {
            "contextRelevanceStatus": self.status,
            "contextRelevanceLabel": self.label,
            "contextRelevanceScore": round(float(self.score), 1),
            "contextRelevanceMatched": list(self.matched),
            "contextRelevanceReasons": list(self.reasons),
            "contextRelevanceSummary": self.summary,
            "contextKeepClean": bool(self.keep_clean),
            "contextPivotAllowed": bool(self.pivot_allowed),
        }


def assess_record_against_seed(seed: Any, record: Any) -> RelevanceAssessment:
    kind = _kind(getattr(seed, "kind", ""))
    value = str(getattr(seed, "value", "") or "").strip()
    if not value:
        return RelevanceAssessment("not_applicable", 0.0)

    if kind == "person_name":
        match = match_person_name_record(value, record)
        if match.accepted:
            return RelevanceAssessment(
                "relevant", max(70.0, match.score),
                ("Full name matches",), (), True, False,
            )
        return RelevanceAssessment(
            "low_relevance", match.score,
            (), ("Full person name does not match",), False, False,
        )

    text, exact_values = _record_search_material(record)
    return _assess(kind, value, text=text, exact_values=exact_values, candidate_only=_candidate_only(record))


def assess_result_row(row: dict[str, Any]) -> RelevanceAssessment:
    kind = _kind(row.get("seedType"))
    value = str(row.get("seed") or "").strip()
    if not kind or not value:
        return RelevanceAssessment("not_applicable", 0.0)

    if kind == "person_name":
        rejected = bool(row.get("identityRejected"))
        score = float(row.get("identityMatchScore") or 0.0)
        if rejected:
            return RelevanceAssessment("low_relevance", score, (), ("Full person name does not match",), False, False)
        if score:
            return RelevanceAssessment("relevant", max(70.0, score), ("Full name matches",), (), True, False)

    identifiers = row.get("identifiers")
    exact_values: list[str] = []
    if isinstance(identifiers, dict):
        exact_values.extend(str(v) for v in identifiers.values() if v is not None)

    if kind == "username":
        wanted = _normalize_exact("username", value)
        identifier_match = any(
            _normalize_exact("username", item) == wanted
            for item in exact_values
            if str(item).strip()
        )
        title_match = _normalize_exact("username", row.get("title")) == wanted
        url_match = _username_url_match(wanted, row.get("url")) or _username_url_match(
            wanted, row.get("title")
        )
        metadata = row.get("findingMetadata") if isinstance(row.get("findingMetadata"), dict) else {}
        family = _kind(row.get("type"))
        direct_account = bool(
            wanted
            and title_match
            and family in {"account", "username", "public_account", "public_user", "profile", "social_profile"}
            and not _metadata_negative(metadata)
        )
        if wanted and (identifier_match or direct_account or url_match):
            if identifier_match:
                reason = "Username identifier matches"
                score = 98.0
            elif direct_account:
                reason = "Exact account finding matches searched username"
                score = 96.0
            else:
                reason = "Username account URL matches"
                score = 92.0
            return RelevanceAssessment("relevant", score, (reason,), (), True, True)
        return RelevanceAssessment(
            "low_relevance", 8.0, (),
            ("Returned record does not prove the searched username",), False, False,
        )

    text = " ".join(
        str(row.get(key) or "")
        for key in ("title", "detail", "url")
    )
    return _assess(
        kind,
        value,
        text=text,
        exact_values=exact_values,
        candidate_only=bool(row.get("candidateOnly")),
        provider_hint=str(row.get("lane") or ""),
    )



def _metadata_negative(metadata: dict[str, Any]) -> bool:
    if not isinstance(metadata, dict):
        return False
    for key in ("available", "exists", "claimed", "registered", "used"):
        value = metadata.get(key)
        if key == "available" and value is True:
            return True
        if key != "available" and value is False:
            return True
    status = str(metadata.get("status") or metadata.get("state") or "").strip().casefold()
    return status in {"available", "free", "not found", "not_found", "missing", "unclaimed"}

def context_terms_from_profile(profile: dict[str, Any] | None) -> tuple[str, ...]:
    """Return analyst context terms that may boost ranking but never route search."""
    data = dict(profile or {})
    values: list[str] = []
    for key in ("keywords", "city", "region", "country", "organizations"):
        raw = data.get(key)
        if isinstance(raw, (list, tuple, set, frozenset)):
            parts = [str(x) for x in raw]
        else:
            parts = re.split(r"[\r\n;,]+", str(raw or ""))
        values.extend(part.strip() for part in parts if part and part.strip())
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        norm = _norm_text(value)
        if len(norm) < 2 or norm in seen:
            continue
        seen.add(norm)
        out.append(value.strip())
    return tuple(out[:40])


def context_boost(row: dict[str, Any], terms: Iterable[str]) -> tuple[float, tuple[str, ...]]:
    haystack = _norm_text(" ".join(str(row.get(k) or "") for k in ("title", "detail", "meta")))
    if not haystack:
        return 0.0, ()
    matched: list[str] = []
    for term in terms:
        normalized = _norm_text(term)
        if normalized and normalized in haystack:
            matched.append(str(term))
    # Context is supporting evidence only, never the main relevance proof.
    return min(10.0, len(matched) * 2.5), tuple(matched[:4])


def _assess(
    kind: str,
    seed_value: str,
    *,
    text: str,
    exact_values: Iterable[str],
    candidate_only: bool,
    provider_hint: str = "",
) -> RelevanceAssessment:
    normalized_text = _norm_text(text)
    normalized_seed = _normalize_exact(kind, seed_value)
    exact_normalized = {_normalize_exact(kind, item) for item in exact_values if str(item).strip()}
    exact_normalized.discard("")

    # Upstream reconciliation APIs often explicitly tell us a row did not
    # match.  Keep it in Raw, but do not let it pollute Clean or pivots.
    lower_text = str(text or "").casefold()
    if any(marker in lower_text for marker in ("match: false", "match false", '"match": false', "matched: false")):
        return RelevanceAssessment("low_relevance", 5.0, (), ("Upstream source marked this as non-matching",), False, False)

    if kind == "username":
        exact = normalized_seed and normalized_seed in exact_normalized
        url_match = _username_url_match(normalized_seed, text)
        direct = _normalize_exact("username", text) == normalized_seed
        if normalized_seed and (exact or direct or url_match):
            return RelevanceAssessment(
                "relevant", 96.0 if exact else 90.0,
                ("Username matches",), (), True, True,
            )
        return RelevanceAssessment(
            "low_relevance", 8.0, (),
            ("Returned record does not prove the searched username",), False, False,
        )

    if kind == "organization":
        wanted = _organization_tokens(seed_value)
        candidate_tokens = set(_tokens(text))
        if not wanted:
            phrase = _norm_text(seed_value)
            ok = bool(phrase and phrase in normalized_text)
            return RelevanceAssessment(
                "relevant" if ok else "low_relevance",
                82.0 if ok else 8.0,
                ("Organization phrase matches",) if ok else (),
                () if ok else ("Organization name does not match",),
                ok,
                ok,
            )
        overlap = wanted & candidate_tokens
        ratio = len(overlap) / len(wanted)
        if ratio >= 1.0:
            return RelevanceAssessment("relevant", 88.0, ("Organization name matches",), (), True, True)
        if ratio >= 0.67 and len(wanted) >= 3:
            return RelevanceAssessment("candidate", 58.0, ("Organization name partially matches",), (), True, False)
        return RelevanceAssessment("low_relevance", round(ratio * 45.0, 1), (), ("Organization name token overlap is too weak",), False, False)

    if kind == "keyword":
        # Keywords are context-only in R13.21.1. Rows from older/current runs
        # remain visible in Raw, but a keyword alone is not a Clean-view proof.
        phrase = _norm_text(seed_value)
        if phrase and phrase in normalized_text:
            return RelevanceAssessment("candidate", 45.0, ("Context keyword appears",), (), False, False)
        return RelevanceAssessment("low_relevance", 0.0, (), ("Keyword-only result",), False, False)

    # R13.21.4 — URL targets need proof from the returned URL itself.
    # A historical/archive provider being invoked for a URL is not enough:
    # some tools return unrelated URLs from the same platform/domain.
    if kind == "url":
        relation = _url_seed_relation(seed_value, text)
        if relation == "exact":
            return RelevanceAssessment(
                "relevant", 96.0, ("Exact URL matches",), (), True, True,
            )
        if relation == "descendant":
            return RelevanceAssessment(
                "relevant", 88.0, ("URL is inside searched profile/path scope",), (), True, True,
            )
        return RelevanceAssessment(
            "low_relevance", 6.0, (),
            ("Returned URL is outside the searched URL/profile scope",),
            False, False,
        )

    if kind in _EXACT_TYPES:
        exact = normalized_seed and normalized_seed in exact_normalized
        text_match = _exact_text_match(kind, seed_value, text)
        if exact or text_match:
            score = 96.0 if exact else 84.0
            return RelevanceAssessment("relevant", score, (f"{kind.replace('_', ' ').title()} matches",), (), True, True)

        # For non-URL exact targets a bounded provider route may still omit the
        # exact value from the compact UI row. URL is deliberately excluded
        # above because it is the source of cross-account historical noise.
        if provider_hint.casefold() in {"classic osint", "open-web"} and not candidate_only:
            return RelevanceAssessment("candidate", 60.0, ("Exact-target provider route",), (), True, False)
        return RelevanceAssessment("low_relevance", 12.0, (), ("Exact identifier was not present in the returned record",), False, False)

    if kind == "address":
        seed_tokens = set(_tokens(seed_value))
        candidate_tokens = set(_tokens(text))
        overlap = len(seed_tokens & candidate_tokens)
        required = min(2, len(seed_tokens))
        ok = overlap >= max(1, required)
        return RelevanceAssessment(
            "candidate" if ok else "low_relevance",
            55.0 if ok else 10.0,
            ("Address context overlaps",) if ok else (),
            () if ok else ("Address context does not match",),
            ok,
            False,
        )

    return RelevanceAssessment("not_applicable", 0.0)


def _candidate_only(record: Any) -> bool:
    for obj in (
        getattr(record, "attributes", None),
        getattr(record, "metadata", None),
    ):
        if isinstance(obj, dict) and bool(obj.get("candidate_only") or obj.get("lead_only")):
            return True
    return False


def _record_search_material(record: Any) -> tuple[str, list[str]]:
    parts: list[str] = []
    exact: list[str] = []
    for attr in ("display_name", "record_id", "record_type", "country"):
        value = getattr(record, attr, None)
        if value:
            parts.append(str(value))
    for attr in ("identifiers", "attributes", "metadata"):
        value = getattr(record, attr, None)
        _collect(value, parts, exact, key=attr, depth=0)
    return " ".join(parts)[:30000], exact[:250]


def _collect(value: Any, parts: list[str], exact: list[str], *, key: str, depth: int) -> None:
    if value is None or depth > 3:
        return
    if isinstance(value, dict):
        for index, (child_key, child) in enumerate(value.items()):
            if index >= 80:
                break
            _collect(child, parts, exact, key=str(child_key), depth=depth + 1)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for child in list(value)[:60]:
            _collect(child, parts, exact, key=key, depth=depth + 1)
        return
    text = str(value).strip()
    if not text:
        return
    parts.append(text)
    key_norm = _kind(key)
    if (
        key_norm in _EXACT_TYPES
        or key_norm in _USERNAME_KEYS
        or any(marker in key_norm for marker in _EXACT_TYPES)
    ):
        exact.append(text)


def _organization_tokens(value: str) -> set[str]:
    tokens = {token for token in _tokens(value) if token not in _GENERIC_ORG_TOKENS and len(token) > 1}
    return tokens


def _tokens(value: Any) -> list[str]:
    return [token.casefold() for token in re.findall(r"[^\W_]+", str(value or ""), flags=re.UNICODE)]


def _exact_text_match(kind: str, seed: str, text: str) -> bool:
    normalized_seed = _normalize_exact(kind, seed)
    if not normalized_seed:
        return False
    if kind == "url":
        return normalized_seed in {_normalize_exact("url", item) for item in re.findall(r"https?://[^\s<>\"]+", str(text or ""))}
    if kind == "username":
        return _normalize_exact("username", text) == normalized_seed or _username_url_match(normalized_seed, text)
    if kind in {"email", "domain", "cve", "doi", "orcid", "lei", "npi", "case_number", "registration_id", "vat_id", "repository", "crypto_address", "hash", "asn", "ip", "phone"}:
        haystack = _norm_compact(text) if kind in {"phone", "hash", "lei", "orcid", "npi", "asn"} else _norm_text(text)
        needle = _norm_compact(seed) if kind in {"phone", "hash", "lei", "orcid", "npi", "asn"} else _norm_text(seed)
        return bool(needle and needle in haystack)
    return normalized_seed in _norm_text(text)


def _username_url_match(wanted: str, value: Any) -> bool:
    wanted = _normalize_exact("username", wanted)
    if not wanted:
        return False
    for found in re.findall(r"https?://[^\s<>\"]+", str(value or "")):
        try:
            parsed = urlsplit(found)
        except ValueError:
            continue
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not segments:
            continue
        # Account ownership must be expressed in the owner/profile position.
        # `/torvalds/...` is accepted. `/users/torvalds/...` is accepted.
        # Arbitrary deep mentions such as `/project/issues/torvalds` are not.
        if _normalize_exact("username", segments[0]) == wanted:
            return True
        namespaces = {"user", "users", "u", "profile", "profiles", "people", "member", "members"}
        if (
            len(segments) >= 2
            and segments[0].casefold() in namespaces
            and _normalize_exact("username", segments[1]) == wanted
        ):
            return True
    return False


def _url_seed_relation(seed: str, value: Any) -> str | None:
    """Return exact/descendant only when a returned URL is in seed scope.

    For a profile-like seed such as `https://gitlab.com/torvalds`, a child URL
    under `/torvalds/...` is relevant, while another account on gitlab.com is
    not.  A site-root seed may legitimately discover any path on that host.
    """
    seed_parts = _url_parts(seed)
    if seed_parts is None:
        return None
    seed_host, seed_path = seed_parts
    found_urls = re.findall(r"https?://[^\s<>\"]+", str(value or ""))
    direct = str(value or "").strip()
    if direct.startswith(("http://", "https://")) and direct not in found_urls:
        found_urls.insert(0, direct)
    for found in found_urls:
        parts = _url_parts(found)
        if parts is None:
            continue
        host, path = parts
        if host != seed_host:
            continue
        if path == seed_path:
            return "exact"
        if seed_path == "/":
            return "descendant"
        prefix = seed_path.rstrip("/") + "/"
        if path.startswith(prefix):
            return "descendant"
    return None


def _url_parts(value: Any) -> tuple[str, str] | None:
    raw = str(value or "").strip()
    if not raw.startswith(("http://", "https://")):
        return None
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return None
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    path = path.rstrip("/") or "/"
    return host, path


def _normalize_exact(kind: str, value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if kind == "email":
        return raw.casefold()
    if kind == "username":
        return raw.lstrip("@").casefold()
    if kind == "phone":
        return ("+" if raw.startswith("+") else "") + "".join(ch for ch in raw if ch.isdigit())
    if kind == "domain":
        return raw.casefold().removeprefix("http://").removeprefix("https://").split("/", 1)[0].rstrip(".")
    if kind == "url":
        try:
            parsed = urlsplit(raw if "://" in raw else "https://" + raw)
            host = (parsed.hostname or "").casefold().rstrip(".")
            path = parsed.path.rstrip("/") or "/"
            return f"{host}{path}" + (f"?{parsed.query}" if parsed.query else "")
        except ValueError:
            return raw.casefold()
    if kind == "ip":
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            return raw.casefold()
    if kind in {"hash", "lei", "orcid", "npi", "cve", "asn"}:
        return _norm_compact(raw)
    return _norm_text(raw)


def _kind(value: Any) -> str:
    raw = getattr(value, "value", value)
    return re.sub(r"[^a-z0-9]+", "_", str(raw or "").casefold()).strip("_")


def _norm_text(value: Any) -> str:
    return " ".join(_tokens(value))


def _norm_compact(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9+]", "", str(value or "")).casefold()

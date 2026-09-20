"""R13.20.1 result normalization, consolidation and ranking for live investigation search.

This module is presentation-layer aggregation only. It does not alter persisted
Evidence, Entity, Source or provider results. Raw rows remain available in the
UI; the clean view groups semantically identical observations across sources.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.application.person_name_relevance import match_person_name_row


_TRACKING_QUERY_KEYS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid",
    "igshid", "yclid", "_hsenc", "_hsmi",
}
_GENERIC_TITLES = {
    "", "result", "remote record", "registry record", "public document",
    "osint finding", "extracted finding", "finding", "unknown",
}
_GENERIC_DETAILS = {
    "", "finding", "email", "username", "phone", "domain", "url", "ip",
    "document", "public web", "remote", "registry", "organization", "person",
}
_TYPE_ALIASES = {
    "email_address": "email", "e_mail": "email",
    "user": "username", "account": "username", "profile": "username",
    "telephone": "phone", "phone_number": "phone",
    "hostname": "domain", "fqdn": "domain",
    "ip_address": "ip", "ipv4": "ip", "ipv6": "ip",
    "website": "url", "link": "url",
    "sha256": "hash", "sha1": "hash", "md5": "hash",
    "legal_entity": "organization", "company": "organization",
    "sole_trader": "organization",
    "person_name": "person", "individual": "person",
    "court_case": "case_number", "court_decision": "case_number",
    "publication": "document", "research_output": "document",
}
_IDENTIFIER_KIND_HINTS = {
    "email": "email", "email_address": "email",
    "username": "username", "handle": "username",
    "phone": "phone", "telephone": "phone",
    "domain": "domain", "hostname": "domain",
    "url": "url", "uri": "url", "website": "url",
    "ip": "ip", "ip_address": "ip",
    "lei": "lei", "orcid": "orcid", "npi": "npi", "cve": "cve",
    "doi": "doi", "asn": "asn", "case_number": "case_number",
    "edrpou": "registration_id", "krs": "registration_id",
    "company_number": "registration_id", "registration_id": "registration_id",
    "vat": "vat_id", "vat_id": "vat_id",
    "sha256": "hash", "sha1": "hash", "md5": "hash", "hash": "hash",
}
_EXACT_FAMILIES = {
    "email", "username", "phone", "domain", "url", "ip", "hash", "lei",
    "orcid", "npi", "cve", "doi", "asn", "case_number", "registration_id",
    "vat_id", "repository", "crypto_address",
}


@dataclass(slots=True)
class ConsolidationResult:
    rows: list[dict[str, Any]]
    raw_count: int
    duplicates_collapsed: int
    low_value_suppressed: int
    corroborated_count: int


def consolidate_result_rows(
    rows: Iterable[dict[str, Any]],
    *,
    seeds: Iterable[dict[str, Any]] = (),
    limit: int = 300,
) -> ConsolidationResult:
    """Group cross-source duplicates, suppress obvious echo/noise and rank results.

    No fuzzy person-name matching is performed. Person/organization values only
    collapse on exact normalized text or a shared exact identifier/URL.
    """
    raw = [dict(row) for row in rows if isinstance(row, dict)]
    seed_keys = _seed_identity_keys(seeds)

    groups: list[dict[str, Any]] = []
    strong_index: dict[tuple[str, str], int] = {}
    fallback_index: dict[tuple[str, str, str], int] = {}
    suppressed = 0

    for order, row in enumerate(raw):
        prepared = _prepare_row(row, order=order)
        if _is_low_value(prepared, seed_keys=seed_keys):
            suppressed += 1
            continue

        strong_keys = prepared.pop("_strong_keys")
        fallback_key = prepared.pop("_fallback_key")
        group_index = next((strong_index[key] for key in strong_keys if key in strong_index), None)
        if group_index is None:
            group_index = fallback_index.get(fallback_key)

        if group_index is None:
            group_index = len(groups)
            groups.append(_new_group(prepared))
        else:
            _merge_group(groups[group_index], prepared)

        for key in strong_keys:
            strong_index.setdefault(key, group_index)
        fallback_index.setdefault(fallback_key, group_index)

    clean: list[dict[str, Any]] = []
    for group in groups:
        clean.append(_finalize_group(group))

    clean.sort(
        key=lambda row: (
            -float(row.get("score") or 0.0),
            -int(row.get("corroborationCount") or 0),
            int(row.get("depth") or 0),
            str(row.get("title") or "").casefold(),
        )
    )
    if limit > 0:
        clean = clean[:limit]

    duplicates = max(0, len(raw) - suppressed - len(groups))
    corroborated = sum(1 for row in clean if int(row.get("corroborationCount") or 0) > 1)
    return ConsolidationResult(
        rows=clean,
        raw_count=len(raw),
        duplicates_collapsed=duplicates,
        low_value_suppressed=suppressed,
        corroborated_count=corroborated,
    )


def _prepare_row(row: dict[str, Any], *, order: int) -> dict[str, Any]:
    out = dict(row)
    family = _family(out.get("type"))
    title = _clean_text(out.get("title"))
    detail = _clean_text(out.get("detail"))
    url = _canonical_url(out.get("url"))
    identifiers = _identifier_map(out.get("identifiers"))

    strong: set[tuple[str, str]] = set()
    for raw_key, raw_value in identifiers.items():
        hint = _identifier_kind(raw_key)
        normalized = _normalize_value(hint, raw_value)
        if normalized:
            strong.add((hint, normalized))

    title_norm = _normalize_value(family, title)
    if family in _EXACT_FAMILIES and title_norm:
        strong.add((family, title_norm))
    if url:
        strong.add(("url", url))

    fallback_title = _normalize_text(title)
    fallback_detail = _normalize_text(detail)
    # Keep exact names conservative: no fuzzy or token-based person/org merging.
    fallback_key = (family, fallback_title, url or fallback_detail[:180])

    out.update({
        "title": title or str(out.get("title") or "Result"),
        "detail": detail,
        "url": url or _clean_text(out.get("url")),
        "type": family,
        "identifiers": identifiers,
        "depth": _safe_int(out.get("depth")),
        "candidateOnly": bool(out.get("candidateOnly")),
        "sensitive": bool(out.get("sensitive")),
        "_order": order,
        "_strong_keys": strong,
        "_fallback_key": fallback_key,
    })
    return out


def _new_group(row: dict[str, Any]) -> dict[str, Any]:
    source = _clean_text(row.get("source")) or "Unknown source"
    lane = _clean_text(row.get("lane")) or "Unknown"
    return {
        "best": row,
        "rows": [row],
        "sources": {source},
        "lanes": {lane},
        "urls": {row.get("url")} if row.get("url") else set(),
        "candidate_all": bool(row.get("candidateOnly")),
        "sensitive_any": bool(row.get("sensitive")),
        "identifiers": dict(row.get("identifiers") or {}),
    }


def _merge_group(group: dict[str, Any], row: dict[str, Any]) -> None:
    group["rows"].append(row)
    source = _clean_text(row.get("source"))
    lane = _clean_text(row.get("lane"))
    if source:
        group["sources"].add(source)
    if lane:
        group["lanes"].add(lane)
    if row.get("url"):
        group["urls"].add(row.get("url"))
    group["candidate_all"] = bool(group["candidate_all"] and row.get("candidateOnly"))
    group["sensitive_any"] = bool(group["sensitive_any"] or row.get("sensitive"))
    for key, value in dict(row.get("identifiers") or {}).items():
        group["identifiers"].setdefault(key, value)
    if _representative_quality(row) > _representative_quality(group["best"]):
        group["best"] = row


def _finalize_group(group: dict[str, Any]) -> dict[str, Any]:
    best = dict(group["best"])
    sources = sorted(group["sources"], key=str.casefold)
    lanes = sorted(group["lanes"], key=str.casefold)
    duplicate_count = len(group["rows"])
    corroboration = len(sources)
    candidate = bool(group["candidate_all"])
    best["candidateOnly"] = candidate
    best["sensitive"] = bool(group["sensitive_any"])
    best["sources"] = sources
    best["lanes"] = lanes
    best["identifiers"] = dict(group["identifiers"])
    best["duplicateCount"] = duplicate_count
    best["duplicatesMerged"] = max(0, duplicate_count - 1)
    best["corroborationCount"] = corroboration
    best["source"] = sources[0] if corroboration == 1 else f"{corroboration} sources"
    best["lane"] = lanes[0] if len(lanes) == 1 else "Cross-source"
    best["status"] = (
        "Candidate" if candidate
        else "Corroborated" if corroboration > 1
        else str(best.get("status") or "Result")
    )
    score = _score(best, corroboration=corroboration, duplicate_count=duplicate_count)
    best["score"] = score
    best["quality"] = "high" if score >= 72 else "medium" if score >= 48 else "low"

    meta_parts: list[str] = []
    identity_score = float(best.get("identityMatchScore") or 0.0)
    identity_reason = _clean_text(best.get("identityMatchReason"))
    if identity_score > 0:
        label = "Full-name match" if identity_reason == "full_name_match" else "Strong name match"
        meta_parts.append(f"{label} {identity_score:.0f}%")
    old_meta = _clean_text(best.get("meta"))
    if corroboration > 1:
        meta_parts.append(f"{corroboration} independent sources")
    if duplicate_count > corroboration:
        meta_parts.append(f"{duplicate_count} observations")
    if old_meta:
        meta_parts.append(old_meta)
    best["meta"] = " · ".join(dict.fromkeys(meta_parts))

    best.pop("_order", None)
    return best


def _score(row: dict[str, Any], *, corroboration: int, duplicate_count: int) -> float:
    family = _family(row.get("type"))
    if family in _EXACT_FAMILIES:
        score = 67.0
    elif family in {"person", "organization"}:
        score = 50.0
    elif family == "document":
        score = 45.0
    else:
        score = 48.0

    if row.get("identifiers"):
        score += 8.0
    if row.get("url"):
        score += 4.0
    if row.get("candidateOnly"):
        score -= 18.0
    identity_score = float(row.get("identityMatchScore") or 0.0)
    if identity_score >= 99.0:
        score += 12.0
    elif identity_score >= 80.0:
        score += 7.0
    if _normalize_text(row.get("title")) in _GENERIC_TITLES:
        score -= 18.0
    score -= min(16.0, float(_safe_int(row.get("depth"))) * 4.0)
    score += min(22.0, max(0, corroboration - 1) * 8.0)
    score += min(5.0, max(0, duplicate_count - corroboration) * 1.0)
    return round(max(0.0, min(100.0, score)), 1)


def _representative_quality(row: dict[str, Any]) -> tuple[int, int, int, int, int]:
    return (
        1 if not row.get("candidateOnly") else 0,
        1 if row.get("identifiers") else 0,
        1 if row.get("url") else 0,
        len(_clean_text(row.get("detail"))),
        -_safe_int(row.get("depth")),
    )


def _is_low_value(row: dict[str, Any], *, seed_keys: set[tuple[str, str]]) -> bool:
    title_norm = _normalize_text(row.get("title"))
    detail_norm = _normalize_text(row.get("detail"))
    family = _family(row.get("type"))

    # R13.20.2 — strict full-name relevance.  Raw rows are preserved by the
    # worker, but the Clean view must not show a person-name route merely
    # because one token (first name or surname) happened to match upstream.
    if bool(row.get("identityRejected")):
        return True
    seed_type_raw = re.sub(
        r"[^a-z0-9]+", "_", str(row.get("seedType") or "").strip().casefold()
    ).strip("_")
    if seed_type_raw == "person_name":
        if row.get("identityMatchScore") is None:
            match = match_person_name_row(row)
            if not match.accepted:
                return True
            row["identityMatchScore"] = match.score
            row["identityMatchReason"] = match.reason
            row["identityMatchedName"] = match.matched_text

    if title_norm in _GENERIC_TITLES and not row.get("url") and not row.get("identifiers"):
        return True

    value_norm = _normalize_value(family, row.get("title"))
    seed_type = _family(row.get("seedType"))
    if (
        value_norm
        and (family, value_norm) in seed_keys
        and family == seed_type
        and not row.get("url")
        and not row.get("identifiers")
        and detail_norm in _GENERIC_DETAILS
    ):
        return True
    return False


def _seed_identity_keys(seeds: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for seed in seeds:
        if not isinstance(seed, dict):
            continue
        family = _family(seed.get("kind"))
        value = _normalize_value(family, seed.get("value"))
        if value:
            out.add((family, value))
    return out


def _identifier_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for key, item in value.items():
        text = _clean_text(item)
        if text:
            out[str(key)] = text
    return out


def _identifier_kind(key: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(key).strip().casefold()).strip("_")
    return _IDENTIFIER_KIND_HINTS.get(normalized, "identifier")


def _family(value: Any) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", str(value or "finding").strip().casefold()).strip("_") or "finding"
    return _TYPE_ALIASES.get(raw, raw)


def _normalize_value(family: str, value: Any) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""
    family = _family(family)
    if family == "email":
        return raw.casefold()
    if family == "username":
        return raw.lstrip("@").casefold()
    if family == "phone":
        prefix = "+" if raw.startswith("+") else ""
        digits = "".join(ch for ch in raw if ch.isdigit())
        return prefix + digits
    if family == "domain":
        value = raw.casefold().removeprefix("http://").removeprefix("https://").split("/", 1)[0].rstrip(".")
        return value[4:] if value.startswith("www.") else value
    if family == "url":
        return _canonical_url(raw)
    if family == "ip":
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            return raw.casefold()
    if family in {"hash", "doi", "repository", "crypto_address"}:
        return raw.casefold()
    if family in {"lei", "orcid", "cve", "asn", "registration_id", "vat_id", "case_number", "npi"}:
        return re.sub(r"\s+", "", raw).upper()
    return _normalize_text(raw)


def _canonical_url(value: Any) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return raw
    scheme = parsed.scheme.casefold()
    host = parsed.hostname.casefold().rstrip(".")
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query_items = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        low = key.casefold()
        if low.startswith("utm_") or low in _TRACKING_QUERY_KEYS:
            continue
        query_items.append((key, val))
    query_items.sort(key=lambda item: (item[0].casefold(), item[1]))
    return urlunsplit((scheme, netloc, path, urlencode(query_items, doseq=True), ""))


def _normalize_text(value: Any) -> str:
    text = _clean_text(value).casefold()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n.,;:|-_")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

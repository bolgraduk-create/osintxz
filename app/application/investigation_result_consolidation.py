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
from app.application.identity_resolution import (
    IdentitySignals,
    KnownIdentityProfile,
    resolve_identity_row,
    is_identity_candidate_type,
    is_account_candidate_type,
)
from app.application.contextual_relevance import (
    assess_result_row,
    context_boost,
    context_terms_from_profile,
)
from app.application.adaptive_relevance import (
    annotate_relevant_row,
    classify_suppressed_row,
)


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
    "public_account": "username", "public_user": "username",
    "social_profile": "username", "online_account": "username",
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
    identity_rows: list[dict[str, Any]] = None
    identity_strong: int = 0
    identity_supported: int = 0
    identity_possible: int = 0
    identity_conflicting: int = 0
    identity_insufficient: int = 0
    candidate_rows: list[dict[str, Any]] = None
    related_accounts: list[dict[str, Any]] = None
    mention_rows: list[dict[str, Any]] = None
    possible_rows: list[dict[str, Any]] = None


def consolidate_result_rows(
    rows: Iterable[dict[str, Any]],
    *,
    seeds: Iterable[dict[str, Any]] = (),
    identity_profile: KnownIdentityProfile | None = None,
    search_profile: dict[str, Any] | None = None,
    limit: int = 300,
) -> ConsolidationResult:
    """Group cross-source duplicates, suppress obvious echo/noise and rank results.

    No fuzzy person-name matching is performed. Person/organization values only
    collapse on exact normalized text or a shared exact identifier/URL.
    """
    raw = [dict(row) for row in rows if isinstance(row, dict)]
    seed_keys = _seed_identity_keys(seeds)
    context_terms = context_terms_from_profile(search_profile)

    groups: list[dict[str, Any]] = []
    strong_index: dict[tuple[str, str], int] = {}
    fallback_index: dict[tuple[str, str, str], int] = {}
    suppressed = 0

    for order, row in enumerate(raw):
        prepared = _prepare_row(row, order=order)

        relevance = assess_result_row(prepared)
        prepared.update(relevance.row_fields())
        boost, matched_context = context_boost(prepared, context_terms)
        prepared["contextBoost"] = boost
        prepared["contextMatchedTerms"] = list(matched_context)

        if not relevance.keep_clean or _is_low_value(prepared, seed_keys=seed_keys):
            visibility = classify_suppressed_row(prepared)
            prepared.update(visibility.row_fields())
            if visibility.visible_as_possible and not _is_low_value(prepared, seed_keys=seed_keys):
                prepared["_adaptive_possible"] = True
                prepared.pop("_strong_keys", None)
                prepared.pop("_fallback_key", None)
                groups.append(_new_group(prepared))
            else:
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
    candidate_rows: list[dict[str, Any]] = []
    identity_rows: list[dict[str, Any]] = []
    related_accounts: list[dict[str, Any]] = []
    mention_rows: list[dict[str, Any]] = []
    possible_rows: list[dict[str, Any]] = []
    identity_counts = {
        "strong": 0, "supported": 0, "possible": 0,
        "conflicting": 0, "insufficient": 0,
    }
    for group in groups:
        item = _finalize_group(group, identity_profile=identity_profile)
        if bool(group.get("_adaptive_possible")) or bool(item.pop("_adaptive_possible", False)):
            item.update(classify_suppressed_row(item).row_fields())
            possible_rows.append(item)
            continue
        item = annotate_relevant_row(item)
        if bool(item.get("accountRelation")):
            related_accounts.append(dict(item))
        identity_status = str(item.get("identityStatus") or "")
        if identity_status and identity_status != "not_applicable":
            identity_rows.append(dict(item))
            if identity_status in identity_counts:
                identity_counts[identity_status] += 1
        # Corroborating Mentions are content/document/page records that match
        # multiple independent known-person signals. They live in their own
        # analyst-facing tab instead of polluting generic Results/Candidates.
        if _is_corroborating_mention(item):
            mention_rows.append(_mention_row(item))
            continue

        # Hard identity conflicts are still visible in the Identity view and Raw
        # stream, but do not pollute the normal Clean result list.
        if identity_status == "conflicting":
            suppressed += 1
            continue
        if bool(item.get("candidateOnly")) and identity_status not in {"strong", "supported"}:
            # Identity-review rows live in Identity only; duplicating them in
            # generic Candidates made the UI look noisier than the data was.
            if identity_status and identity_status != "not_applicable":
                continue
            if _candidate_review_worthy(item):
                candidate_rows.append(item)
            else:
                suppressed += 1
            continue
        clean.append(item)

    clean.sort(
        key=lambda row: (
            -float(row.get("score") or 0.0),
            -int(row.get("corroborationCount") or 0),
            int(row.get("depth") or 0),
            str(row.get("title") or "").casefold(),
        )
    )
    candidate_rows.sort(
        key=lambda row: (
            -float(row.get("score") or 0.0),
            -int(row.get("corroborationCount") or 0),
            int(row.get("depth") or 0),
            str(row.get("title") or "").casefold(),
        )
    )
    related_accounts.sort(
        key=lambda row: (
            -float(row.get("score") or 0.0),
            -int(row.get("corroborationCount") or 0),
            str(row.get("title") or "").casefold(),
        )
    )
    mention_rows.sort(
        key=lambda row: (
            -float(row.get("mentionScore") or 0.0),
            -int(row.get("corroborationCount") or 0),
            -float(row.get("score") or 0.0),
            str(row.get("title") or "").casefold(),
        )
    )
    possible_rows.sort(
        key=lambda row: (
            -float(row.get("visibilityScore") or row.get("contextRelevanceScore") or 0.0),
            -float(row.get("score") or 0.0),
            str(row.get("title") or "").casefold(),
        )
    )
    identity_rows.sort(
        key=lambda row: (
            {"strong": 0, "supported": 1, "possible": 2, "insufficient": 3, "conflicting": 4}.get(
                str(row.get("identityStatus") or ""), 9
            ),
            -float(row.get("identityAlignmentScore") or 0.0),
            -int(row.get("corroborationCount") or 0),
            str(row.get("title") or "").casefold(),
        )
    )
    if limit > 0:
        clean = clean[:limit]
        candidate_rows = candidate_rows[:limit]
        identity_rows = identity_rows[:limit]
        related_accounts = related_accounts[:limit]
        mention_rows = mention_rows[:limit]
        possible_rows = possible_rows[:limit]

    duplicates = max(0, len(raw) - suppressed - len(groups))
    corroborated = sum(1 for row in clean if int(row.get("corroborationCount") or 0) > 1)
    return ConsolidationResult(
        rows=clean,
        raw_count=len(raw),
        duplicates_collapsed=duplicates,
        low_value_suppressed=suppressed,
        corroborated_count=corroborated,
        identity_rows=identity_rows,
        identity_strong=identity_counts["strong"],
        identity_supported=identity_counts["supported"],
        identity_possible=identity_counts["possible"],
        identity_conflicting=identity_counts["conflicting"],
        identity_insufficient=identity_counts["insufficient"],
        candidate_rows=candidate_rows,
        related_accounts=related_accounts,
        mention_rows=mention_rows,
        possible_rows=possible_rows,
    )


def _prepare_row(row: dict[str, Any], *, order: int) -> dict[str, Any]:
    out = dict(row)
    original_type = out.get("type")
    family = _family(original_type)
    title = _clean_text(out.get("title"))
    detail = _clean_text(out.get("detail"))
    url = _canonical_url(out.get("url"))
    identifiers = _identifier_map(out.get("identifiers"))

    account_observation = bool(
        _family(out.get("seedType")) == "username"
        and (
            is_account_candidate_type(original_type)
            or _family(original_type) == "username"
        )
    )

    strong: set[tuple[str, str]] = set()
    for raw_key, raw_value in identifiers.items():
        hint = _identifier_kind(raw_key)
        normalized = _normalize_value(hint, raw_value)
        if normalized and not (account_observation and hint == "username"):
            strong.add((hint, normalized))

    title_norm = _normalize_value(family, title)
    # One username may legitimately exist on many unrelated platforms.  For
    # account observations, the bare handle is therefore not a dedupe key;
    # canonical profile URL (or the fallback platform/source context) is.
    if family in _EXACT_FAMILIES and title_norm and not account_observation:
        strong.add((family, title_norm))
    if url:
        strong.add(("url", url))

    fallback_title = _normalize_text(title)
    fallback_detail = _normalize_text(detail)
    if account_observation:
        finding_metadata = (
            out.get("findingMetadata")
            if isinstance(out.get("findingMetadata"), dict)
            else {}
        )
        platform = _normalize_text(
            out.get("service") or finding_metadata.get("service")
        )
        platform = platform or _normalize_text(out.get("source"))
        fallback_key = (family, fallback_title, url or platform or fallback_detail[:180])
    else:
        # Keep exact names conservative: no fuzzy or token-based person/org merging.
        fallback_key = (family, fallback_title, url or fallback_detail[:180])

    structured_person_match = bool(
        _clean_text(out.get("identityMatchedName"))
        and _clean_text(out.get("identityMatchReason")) in {"full_name_match", "first_last_match"}
    )

    out.update({
        "title": title or str(out.get("title") or "Result"),
        "detail": detail,
        "url": url or _clean_text(out.get("url")),
        "type": family,
        "identifiers": identifiers,
        "depth": _safe_int(out.get("depth")),
        "candidateOnly": bool(out.get("candidateOnly")),
        "sensitive": bool(out.get("sensitive")),
        "identityCandidateEligible": bool(
            out.get("identityCandidateEligible")
            or is_identity_candidate_type(original_type)
        ),
        "accountCandidateEligible": bool(
            out.get("accountCandidateEligible")
            or is_account_candidate_type(original_type)
            or (family == "username" and _family(out.get("seedType")) == "username")
        ),
        "recordType": str(original_type or ""),
        "structuredPersonMatch": structured_person_match,
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
        "identity_signals": IdentitySignals.from_payload(row.get("_identitySignals")),
        "identity_eligible_any": bool(row.get("identityCandidateEligible")),
        "account_eligible_any": bool(row.get("accountCandidateEligible")),
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
    group["identity_eligible_any"] = bool(
        group.get("identity_eligible_any") or row.get("identityCandidateEligible")
    )
    group["account_eligible_any"] = bool(
        group.get("account_eligible_any") or row.get("accountCandidateEligible")
    )
    for key, value in dict(row.get("identifiers") or {}).items():
        group["identifiers"].setdefault(key, value)
    group["identity_signals"].merge(
        IdentitySignals.from_payload(row.get("_identitySignals"))
    )
    if _representative_quality(row) > _representative_quality(group["best"]):
        group["best"] = row


def _finalize_group(
    group: dict[str, Any],
    *,
    identity_profile: KnownIdentityProfile | None = None,
) -> dict[str, Any]:
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

    if bool(group.get("account_eligible_any")):
        best["accountRelation"] = True
        best["accountRelationLabel"] = "Related account"
        best["identityCandidateEligible"] = False
        best["identityStatus"] = "not_applicable"
        best["identityLabel"] = "Account signal"
        best["identityAlignmentScore"] = 0.0
        best["identityMatchedSignals"] = []
        best["identityConflictSignals"] = []
        best["identityMatchedCategories"] = []
        best["identityConflictCategories"] = []
        best["identityPivotAllowed"] = False
        best["identitySummary"] = "Online account/username signal; not a separate person identity."

    if identity_profile is not None and bool(group.get("identity_eligible_any")) and not bool(group.get("account_eligible_any")):
        resolution, merged_signals = resolve_identity_row(
            identity_profile,
            best,
            merged_signals=group.get("identity_signals"),
        )
        best.update(resolution.row_fields())
        best["_identitySignals"] = merged_signals.to_payload()
        if resolution.status in {"strong", "supported"}:
            best["candidateOnly"] = False
        elif resolution.status in {"possible", "insufficient"}:
            best["candidateOnly"] = True
        if resolution.status == "conflicting":
            best["status"] = "Identity conflict"
        elif resolution.status == "strong":
            best["status"] = "Strong identity lead"
        elif resolution.status == "supported":
            best["status"] = "Supported identity lead"
    elif identity_profile is not None and not bool(group.get("account_eligible_any")):
        best.update({
            "identityStatus": "not_applicable",
            "identityLabel": "Not identity-scored",
            "identityAlignmentScore": 0.0,
            "identityMatchedSignals": [],
            "identityConflictSignals": [],
            "identityMatchedCategories": [],
            "identityConflictCategories": [],
            "identityPivotAllowed": False,
            "identitySummary": "This record is content/data, not a person-like identity record.",
        })
        best.pop("identityMatchScore", None)
        best.pop("identityMatchReason", None)
        best.pop("identityMatchedName", None)

    score = _score(best, corroboration=corroboration, duplicate_count=duplicate_count)
    best["score"] = score
    best["quality"] = "high" if score >= 72 else "medium" if score >= 48 else "low"

    meta_parts: list[str] = []
    identity_score = float(best.get("identityMatchScore") or 0.0)
    identity_reason = _clean_text(best.get("identityMatchReason"))
    if identity_score > 0:
        label = "Full-name match" if identity_reason == "full_name_match" else "Strong name match"
        meta_parts.append(f"{label} {identity_score:.0f}%")
    alignment = float(best.get("identityAlignmentScore") or 0.0)
    identity_label = _clean_text(best.get("identityLabel"))
    if identity_label and str(best.get("identityStatus") or "") != "not_applicable":
        meta_parts.append(f"{identity_label} · alignment {alignment:.0f}")
    relevance_label = _clean_text(best.get("contextRelevanceLabel"))
    relevance_score = float(best.get("contextRelevanceScore") or 0.0)
    if relevance_label and str(best.get("contextRelevanceStatus") or "") != "not_applicable":
        meta_parts.append(f"{relevance_label} · seed {relevance_score:.0f}")
    matched_context = list(best.get("contextMatchedTerms") or [])
    if matched_context:
        meta_parts.append("Context: " + ", ".join(str(x) for x in matched_context[:3]))
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




def _mention_signal_labels(row: dict[str, Any]) -> list[str]:
    """Return distinct human-readable signals supporting a contextual mention.

    Mentions are deliberately stricter than generic candidates. A document/page
    must match more than one independent known-person signal so broad keywords
    or surname-only references do not become corroboration.
    """
    labels: list[str] = []

    def add(value: Any) -> None:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            return
        lowered = text.casefold()
        if lowered in {"full name matches", "full-name match", "full name"}:
            text = "Full name"
        key = text.casefold()
        if all(item.casefold() != key for item in labels):
            labels.append(text)

    matched = row.get("contextRelevanceMatched")
    if isinstance(matched, (list, tuple, set, frozenset)):
        for value in matched:
            add(value)

    if bool(row.get("structuredPersonMatch")) or float(row.get("identityMatchScore") or 0.0) >= 95.0:
        add("Full name")

    context = row.get("contextMatchedTerms")
    if isinstance(context, (list, tuple, set, frozenset)):
        for value in context:
            add(value)

    identifiers = row.get("identifiers")
    if isinstance(identifiers, dict):
        for key, value in identifiers.items():
            normalized_key = re.sub(r"[^a-z0-9]+", "_", str(key).casefold()).strip("_")
            if normalized_key in {"username", "handle", "email", "phone", "orcid", "npi"} and str(value or "").strip():
                add(f"{normalized_key}: {value}")

    return labels[:8]


def _is_corroborating_mention(row: dict[str, Any]) -> bool:
    """Classify non-identity content as a multi-signal corroborating mention."""
    if bool(row.get("accountRelation")):
        return False

    identity_status = str(row.get("identityStatus") or "")
    if identity_status and identity_status != "not_applicable":
        return False

    family = _family(row.get("type"))
    # Mentions are content/pages/documents, not person/account/entity records.
    if family in {"person", "username", "organization", "email", "phone", "domain", "ip", "hash"}:
        return False

    relevance_status = str(row.get("contextRelevanceStatus") or "")
    relevance_score = float(row.get("contextRelevanceScore") or 0.0)
    if relevance_status not in {"relevant", "corroborated"} or relevance_score < 70.0:
        return False

    signals = _mention_signal_labels(row)
    if len(signals) < 2:
        return False

    # Require either a structured/full-name signal or three independent
    # contextual signals. This prevents keyword pairs like "Linux" + "FI"
    # from becoming corroboration on their own.
    has_name = any("full name" == signal.casefold() for signal in signals)
    if not has_name and len(signals) < 3:
        return False

    # Candidate-only metadata/search rows need a direct person-name anchor.
    if bool(row.get("candidateOnly")) and not has_name:
        return False

    return True


def _mention_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    signals = _mention_signal_labels(out)
    corroboration = int(out.get("corroborationCount") or 0)
    base = 62.0 + min(18.0, max(0, len(signals) - 2) * 8.0)
    if corroboration > 1:
        base += min(12.0, (corroboration - 1) * 6.0)
    if bool(out.get("structuredPersonMatch")):
        base += 8.0
    mention_score = round(min(100.0, base), 1)

    out["mentionSignals"] = signals
    out["mentionScore"] = mention_score
    out["mentionLabel"] = "Strong mention" if mention_score >= 84.0 else "Corroborating mention"
    out["mentionSummary"] = " · ".join(signals[:4])
    out["status"] = out["mentionLabel"]
    return out



def _candidate_review_worthy(row: dict[str, Any]) -> bool:
    """Keep only candidates with an explicit reason for analyst review.

    R13.21.4 tightens *content* candidates without breaking legacy candidate
    semantics. Person-like rows remain reviewable by exact full-name matching;
    document/archive rows additionally require the structured matched-name
    marker captured before snapshotting the remote record.
    """
    seed_type = _family(row.get("seedType"))
    family = _family(row.get("type"))
    relevance_status = str(row.get("contextRelevanceStatus") or "")
    relevance_score = float(row.get("contextRelevanceScore") or 0.0)

    # Preserve generic/legacy candidate behaviour when no live-search seed is
    # attached (older result-cleanup callers/tests rely on this contract).
    if not str(row.get("seedType") or "").strip():
        return True

    if seed_type == "person":
        if family == "person" or bool(row.get("identityCandidateEligible")):
            # Fallback person rows may have their full-name score attached by
            # _is_low_value after contextual scoring. Keep exact person-name
            # candidates reviewable even when no multi-signal profile is built.
            return (
                float(row.get("identityMatchScore") or 0.0) >= 80.0
                or (relevance_status in {"relevant", "corroborated"} and relevance_score >= 70.0)
            )
        if not bool(row.get("structuredPersonMatch")):
            return False
        return relevance_status in {"relevant", "corroborated"} and relevance_score >= 70.0

    if seed_type == "organization":
        return relevance_status in {"candidate", "relevant", "corroborated"} and relevance_score >= 55.0

    # Exact-identifier candidates are useful only when the contextual matcher
    # still found strong evidence in the returned row.
    return relevance_status in {"relevant", "corroborated"} and relevance_score >= 70.0

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
    identity_status = str(row.get("identityStatus") or "")
    alignment_score = float(row.get("identityAlignmentScore") or 0.0)
    if identity_status == "strong":
        score += 24.0 + min(8.0, alignment_score / 20.0)
    elif identity_status == "supported":
        score += 15.0
    elif identity_status == "possible":
        score += 5.0
    elif identity_status == "insufficient":
        score -= 7.0
    elif identity_status == "conflicting":
        score -= 35.0
    identity_score = float(row.get("identityMatchScore") or 0.0)
    if identity_score >= 99.0:
        score += 12.0
    elif identity_score >= 80.0:
        score += 7.0

    relevance_status = str(row.get("contextRelevanceStatus") or "")
    relevance_score = float(row.get("contextRelevanceScore") or 0.0)
    if relevance_status in {"relevant", "corroborated"}:
        score += 8.0 + min(8.0, relevance_score / 16.0)
    elif relevance_status == "candidate":
        score -= 3.0
    elif relevance_status in {"low_relevance", "contradictory"}:
        score -= 30.0
    score += min(10.0, float(row.get("contextBoost") or 0.0))

    if _normalize_text(row.get("title")) in _GENERIC_TITLES:
        score -= 18.0
    score -= min(16.0, float(_safe_int(row.get("depth"))) * 4.0)
    score += min(22.0, max(0, corroboration - 1) * 8.0)
    score += min(5.0, max(0, duplicate_count - corroboration) * 1.0)
    return round(max(0.0, min(100.0, score)), 1)


def _representative_quality(row: dict[str, Any]) -> tuple[int, int, int, int, int]:
    return (
        1 if str(row.get("identityStatus") or "") in {"strong", "supported"} else 0,
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
        and not (
            family in {"person", "organization"}
            and str(row.get("contextRelevanceStatus") or "") in {"relevant", "corroborated"}
        )
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

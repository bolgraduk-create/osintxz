"""R13.27a — unified person/target profile projection.

This module builds a read-only, presentation-friendly profile from the existing
PERSON snapshot. It does not create entities, evidence, relationships or new
identity claims. Every associated item keeps its provenance/basis so the UI can
show whether it came from shared evidence, analyst selection, a manual
attachment or an explicit source URL.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any
from urllib.parse import urlsplit


_GROUP_ORDER = (
    "identity",
    "accounts",
    "contacts",
    "organizations",
    "locations",
    "webTechnical",
    "documents",
)

_GROUP_TITLES = {
    "identity": "IDENTITY",
    "accounts": "ACCOUNTS",
    "contacts": "CONTACTS",
    "organizations": "ORGANIZATIONS",
    "locations": "LOCATIONS",
    "webTechnical": "WEB & TECHNICAL",
    "documents": "DOCUMENTS",
}

_TYPE_TO_GROUP = {
    "username": "accounts",
    "account": "accounts",
    "email": "contacts",
    "phone": "contacts",
    "organization": "organizations",
    "location": "locations",
    "address": "locations",
    "domain": "webTechnical",
    "url": "webTechnical",
    "ip": "webTechnical",
    "asn": "webTechnical",
    "hash": "webTechnical",
    "document": "documents",
}

_BASIS_LABELS = {
    "person_entity": "Person entity",
    "evidence": "Evidence linked",
    "analyst_selected": "Analyst selected",
    "manual": "Manual",
    "source_url": "Source URL",
    "managed_attachment": "Managed attachment",
}


def build_unified_target_profile(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build a deduplicated target profile from one PERSON snapshot."""

    data = dict(snapshot or {})
    groups: dict[str, list[dict[str, Any]]] = {
        key: [] for key in _GROUP_ORDER
    }
    seen: dict[str, set[str]] = {
        key: set() for key in _GROUP_ORDER
    }
    provenance: Counter[str] = Counter()

    def add(
        group: str,
        *,
        value: Any,
        kind: str,
        basis: str,
        url: Any = "",
        source: Any = "",
        evidence_title: Any = "",
        confidence: Any = "",
        detail: Any = "",
        entity_id: Any = "",
    ) -> None:
        if group not in groups:
            return
        text = str(value or "").strip()
        safe_url = _safe_http_url(url)
        if not text and not safe_url:
            return
        if not text:
            text = safe_url

        key = _dedupe_key(
            group=group,
            kind=kind,
            value=text,
            url=safe_url,
        )
        if not key or key in seen[group]:
            return
        seen[group].add(key)

        normalized_basis = _basis(basis)
        provenance[normalized_basis] += 1
        groups[group].append(
            {
                "id": str(entity_id or ""),
                "kind": _kind(kind) or "other",
                "label": _kind(kind).replace("_", " ").title() or "Data",
                "value": text,
                "url": safe_url,
                "source": str(source or ""),
                "evidenceTitle": str(evidence_title or ""),
                "confidence": str(confidence or ""),
                "basis": normalized_basis,
                "basisLabel": _BASIS_LABELS.get(
                    normalized_basis,
                    normalized_basis.replace("_", " ").title(),
                ),
                "detail": str(detail or ""),
            }
        )

    title = str(data.get("title") or "").strip()
    normalized_name = str(data.get("normalizedValue") or "").strip()
    add(
        "identity",
        value=title,
        kind="primary_name",
        basis="person_entity",
        confidence=data.get("confidenceText"),
        detail="Primary PERSON entity value",
        entity_id=data.get("id"),
    )
    if normalized_name and normalized_name.casefold() != title.casefold():
        add(
            "identity",
            value=normalized_name,
            kind="normalized_name",
            basis="person_entity",
            confidence=data.get("confidenceText"),
            detail="Normalized PERSON identity value",
            entity_id=data.get("id"),
        )

    related = data.get("relatedEntities")
    if not isinstance(related, list):
        related = []
    for item in related:
        if not isinstance(item, dict):
            continue
        raw_type = _kind(item.get("rawType") or item.get("type"))
        group = _TYPE_TO_GROUP.get(raw_type)
        if not group:
            continue
        add(
            group,
            value=item.get("value"),
            kind=raw_type,
            basis=item.get("basis") or "evidence",
            url=item.get("url"),
            source=item.get("source"),
            evidence_title=item.get("evidenceTitle"),
            confidence=item.get("confidence"),
            detail=item.get("detail"),
            entity_id=item.get("id"),
        )

    # Explicit pages remain useful even when no URL Entity was persisted. Keep
    # account/profile-looking links with accounts and general pages under web.
    links = data.get("links")
    if not isinstance(links, list):
        links = []
    for item in links:
        if not isinstance(item, dict):
            continue
        url = _safe_http_url(item.get("url"))
        value = str(item.get("value") or url).strip()
        label = str(item.get("label") or "").casefold()
        account_like = any(
            token in label
            for token in ("profile", "account", "username")
        )
        add(
            "accounts" if account_like else "webTechnical",
            value=value,
            kind="profile_page" if account_like else "url",
            basis=item.get("basis") or "source_url",
            url=url,
            source=item.get("source"),
            evidence_title=item.get("evidenceTitle"),
            detail=item.get("label"),
        )

    # Managed files/photos are profile documents, but evidence itself remains a
    # separate concept and is counted rather than duplicated into every group.
    attachments = []
    for key in ("photos", "files"):
        rows = data.get(key)
        if isinstance(rows, list):
            attachments.extend(rows)
    for item in attachments:
        if not isinstance(item, dict):
            continue
        add(
            "documents",
            value=item.get("title") or item.get("managedPath"),
            kind=(
                "photo"
                if str(item.get("type") or "").casefold() == "image"
                else "file"
            ),
            basis="managed_attachment",
            source=item.get("mimeType"),
            evidence_title=item.get("title"),
            detail=item.get("date"),
            entity_id=item.get("id"),
        )

    for key in _GROUP_ORDER:
        groups[key].sort(
            key=lambda row: (
                _basis_priority(row.get("basis")),
                str(row.get("kind") or ""),
                str(row.get("value") or "").casefold(),
            )
        )

    evidence = data.get("evidence")
    evidence_count = len(evidence) if isinstance(evidence, list) else 0
    mentions = data.get("mentions")
    mention_count = len(mentions) if isinstance(mentions, list) else 0

    populated = sum(bool(groups[key]) for key in _GROUP_ORDER)
    total_groups = len(_GROUP_ORDER)
    coverage_percent = (
        round((populated / total_groups) * 100)
        if total_groups
        else 0
    )

    metrics = [
        {"label": "Accounts", "value": len(groups["accounts"])},
        {"label": "Contacts", "value": len(groups["contacts"])},
        {"label": "Organizations", "value": len(groups["organizations"])},
        {"label": "Locations", "value": len(groups["locations"])},
        {"label": "Web / Tech", "value": len(groups["webTechnical"])},
        {"label": "Evidence", "value": evidence_count},
        {"label": "Coverage", "value": f"{coverage_percent}%"},
    ]

    provenance_rows = [
        {
            "basis": basis,
            "label": _BASIS_LABELS.get(
                basis,
                basis.replace("_", " ").title(),
            ),
            "count": count,
        }
        for basis, count in sorted(
            provenance.items(),
            key=lambda item: (
                _basis_priority(item[0]),
                item[0],
            ),
        )
    ]

    group_rows = [
        {
            "key": key,
            "title": _GROUP_TITLES[key],
            "count": len(groups[key]),
            "rows": groups[key],
        }
        for key in _GROUP_ORDER
    ]

    return {
        "version": "R13.27a",
        "personId": str(data.get("id") or ""),
        "primary": {
            "name": title,
            "normalizedName": normalized_name,
            "avatarUrl": str(data.get("avatarUrl") or ""),
            "caseTitle": str(data.get("caseTitle") or ""),
            "confidenceText": str(data.get("confidenceText") or ""),
        },
        "groups": group_rows,
        "groupMap": groups,
        "metrics": metrics,
        "provenance": provenance_rows,
        "coverage": {
            "populatedGroups": populated,
            "totalGroups": total_groups,
            "percent": coverage_percent,
            "label": (
                f"{populated}/{total_groups} profile categories populated"
            ),
        },
        "counts": {
            "identity": len(groups["identity"]),
            "accounts": len(groups["accounts"]),
            "contacts": len(groups["contacts"]),
            "organizations": len(groups["organizations"]),
            "locations": len(groups["locations"]),
            "webTechnical": len(groups["webTechnical"]),
            "documents": len(groups["documents"]),
            "evidence": evidence_count,
            "mentions": mention_count,
        },
        "notice": (
            "Unified Profile groups already-linked investigation data. "
            "A grouped item is not automatically an independently verified "
            "identity claim; its provenance remains authoritative."
        ),
    }


def _dedupe_key(
    *,
    group: str,
    kind: str,
    value: str,
    url: str,
) -> str:
    normalized_url = _normalized_url_key(url)
    if normalized_url:
        return f"{group}|url|{normalized_url}"
    normalized_value = re.sub(
        r"\s+",
        " ",
        str(value or "").strip().casefold(),
    )
    if not normalized_value:
        return ""
    return f"{group}|{_kind(kind)}|{normalized_value}"


def _normalized_url_key(value: Any) -> str:
    safe = _safe_http_url(value)
    if not safe:
        return ""
    parsed = urlsplit(safe)
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/") or "/"
    return f"{host}{path}".casefold()


def _safe_http_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        return ""
    return raw


def _basis(value: Any) -> str:
    normalized = _kind(value)
    if normalized in _BASIS_LABELS:
        return normalized
    return normalized or "evidence"


def _basis_priority(value: Any) -> int:
    return {
        "person_entity": 0,
        "evidence": 1,
        "analyst_selected": 2,
        "manual": 3,
        "source_url": 4,
        "managed_attachment": 5,
    }.get(_basis(value), 9)


def _kind(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value or "").strip().casefold(),
    ).strip("_")

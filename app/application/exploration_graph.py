"""R13.26c — in-memory Exploration Graph for pivot-before-persistence.

The graph converts quality-approved result observations into bounded ephemeral
search seeds.  It is deliberately separate from database persistence:

- a row may be useful enough to explore without being persistence-grade;
- exploration seeds live only for one unified-search run;
- only exact, OSINT-compatible target kinds are executable in this first phase;
- initial/user seeds and already-known exact pivots are deduplicated;
- no Entity/Evidence is created merely because a node is explored.

This module is pure. It performs no network, database, Qt, or connector work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable
from urllib.parse import urlsplit

from app.application.unified_investigation_search import (
    UnifiedSeed,
    UnifiedSeedKind,
    dedupe_seeds,
    osint_target_for_seed,
)


_EXECUTABLE_KINDS = frozenset(
    {
        UnifiedSeedKind.USERNAME,
        UnifiedSeedKind.EMAIL,
        UnifiedSeedKind.PHONE,
        UnifiedSeedKind.DOMAIN,
        UnifiedSeedKind.URL,
        UnifiedSeedKind.IP,
        UnifiedSeedKind.HASH,
    }
)

_IDENTIFIER_KIND_MAP: dict[str, UnifiedSeedKind] = {
    "username": UnifiedSeedKind.USERNAME,
    "handle": UnifiedSeedKind.USERNAME,
    "login": UnifiedSeedKind.USERNAME,
    "user_name": UnifiedSeedKind.USERNAME,
    "email": UnifiedSeedKind.EMAIL,
    "phone": UnifiedSeedKind.PHONE,
    "domain": UnifiedSeedKind.DOMAIN,
    "url": UnifiedSeedKind.URL,
    "ip": UnifiedSeedKind.IP,
    "ip_address": UnifiedSeedKind.IP,
    "hash": UnifiedSeedKind.HASH,
    "md5": UnifiedSeedKind.HASH,
    "sha1": UnifiedSeedKind.HASH,
    "sha256": UnifiedSeedKind.HASH,
}

_ROW_TYPE_MAP: dict[str, UnifiedSeedKind] = {
    "username": UnifiedSeedKind.USERNAME,
    "account": UnifiedSeedKind.USERNAME,
    "profile": UnifiedSeedKind.USERNAME,
    "social_profile": UnifiedSeedKind.USERNAME,
    "public_account": UnifiedSeedKind.USERNAME,
    "email": UnifiedSeedKind.EMAIL,
    "phone": UnifiedSeedKind.PHONE,
    "domain": UnifiedSeedKind.DOMAIN,
    "url": UnifiedSeedKind.URL,
    "ip": UnifiedSeedKind.IP,
    "ip_address": UnifiedSeedKind.IP,
    "hash": UnifiedSeedKind.HASH,
}


@dataclass(frozen=True, slots=True)
class ExplorationNode:
    seed: UnifiedSeed
    observation_id: str
    quality_score: float
    pivot_score: float
    persistence_score: float
    reason: str
    source: str = ""
    parent_seed_kind: str = ""
    parent_seed_value: str = ""

    @property
    def identity_key(self) -> tuple[str, str, str]:
        return self.seed.identity_key

    def to_dict(self, *, executed: bool = False) -> dict[str, Any]:
        return {
            "kind": self.seed.kind.value,
            "value": self.seed.value,
            "depth": self.seed.depth,
            "country": self.seed.country or "",
            "origin": self.seed.origin,
            "parentRef": self.seed.parent_ref or "",
            "observationId": self.observation_id,
            "qualityScore": round(self.quality_score, 1),
            "pivotScore": round(self.pivot_score, 1),
            "persistenceScore": round(self.persistence_score, 1),
            "reason": self.reason,
            "source": self.source,
            "parentSeedKind": self.parent_seed_kind,
            "parentSeedValue": self.parent_seed_value,
            "ephemeral": True,
            "executed": bool(executed),
        }


@dataclass(frozen=True, slots=True)
class ExplorationEdge:
    parent_ref: str
    child_key: tuple[str, str, str]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "parentRef": self.parent_ref,
            "childKind": self.child_key[0],
            "childValue": self.child_key[1],
            "childCountry": self.child_key[2],
            "reason": self.reason,
        }


@dataclass(slots=True)
class ExplorationGraph:
    nodes: list[ExplorationNode] = field(default_factory=list)
    edges: list[ExplorationEdge] = field(default_factory=list)
    skipped_initial: int = 0
    skipped_duplicate: int = 0
    skipped_unsupported: int = 0
    skipped_not_approved: int = 0
    skipped_depth: int = 0

    @property
    def seeds(self) -> list[UnifiedSeed]:
        return [node.seed for node in self.nodes]

    def to_dict(
        self,
        *,
        executed_keys: set[tuple[str, str, str]] | None = None,
    ) -> dict[str, Any]:
        executed_keys = executed_keys or set()
        return {
            "nodes": [
                node.to_dict(executed=node.identity_key in executed_keys)
                for node in self.nodes
            ],
            "edges": [edge.to_dict() for edge in self.edges],
            "summary": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "executed": sum(
                    node.identity_key in executed_keys
                    for node in self.nodes
                ),
                "skippedInitial": self.skipped_initial,
                "skippedDuplicate": self.skipped_duplicate,
                "skippedUnsupported": self.skipped_unsupported,
                "skippedNotApproved": self.skipped_not_approved,
                "skippedDepth": self.skipped_depth,
            },
        }


def build_exploration_graph(
    rows: Iterable[dict[str, Any]],
    *,
    initial_seeds: Iterable[UnifiedSeed] = (),
    existing_seeds: Iterable[UnifiedSeed] = (),
    max_nodes: int = 8,
    max_depth: int = 2,
) -> ExplorationGraph:
    """Build a bounded graph from quality-approved raw observations."""

    graph = ExplorationGraph()
    blocked_keys = {
        seed.identity_key
        for seed in dedupe_seeds([*initial_seeds, *existing_seeds])
    }
    seen: set[tuple[str, str, str]] = set()

    ranked_rows = sorted(
        (dict(row) for row in rows if isinstance(row, dict)),
        key=lambda row: (
            0 if bool(row.get("qualityWouldExplore")) else 1,
            -_safe_float(row.get("qualityPivotScore")),
            -_safe_float(row.get("qualityScore")),
            str(row.get("qualityObservationId") or ""),
        ),
    )

    for row in ranked_rows:
        if len(graph.nodes) >= max(0, int(max_nodes)):
            break

        if not bool(row.get("qualityWouldExplore")):
            graph.skipped_not_approved += 1
            continue

        row_depth = _safe_int(row.get("depth"))
        child_depth = max(1, row_depth + 1)
        if child_depth > max_depth:
            graph.skipped_depth += 1
            continue

        candidates = _candidate_seeds_from_row(
            row,
            depth=child_depth,
        )
        if not candidates:
            graph.skipped_unsupported += 1
            continue

        for seed, reason in candidates:
            if len(graph.nodes) >= max(0, int(max_nodes)):
                break

            if seed.kind not in _EXECUTABLE_KINDS:
                graph.skipped_unsupported += 1
                continue
            if osint_target_for_seed(seed) is None:
                graph.skipped_unsupported += 1
                continue
            if seed.identity_key in blocked_keys:
                graph.skipped_initial += 1
                continue
            if seed.identity_key in seen:
                graph.skipped_duplicate += 1
                continue

            seen.add(seed.identity_key)
            node = ExplorationNode(
                seed=seed,
                observation_id=str(
                    row.get("qualityObservationId")
                    or row.get("id")
                    or ""
                ),
                quality_score=_safe_float(row.get("qualityScore")),
                pivot_score=_safe_float(row.get("qualityPivotScore")),
                persistence_score=_safe_float(
                    row.get("qualityPersistenceScore")
                ),
                reason=reason,
                source=str(row.get("source") or ""),
                parent_seed_kind=str(row.get("seedType") or ""),
                parent_seed_value=str(row.get("seed") or ""),
            )
            graph.nodes.append(node)
            graph.edges.append(
                ExplorationEdge(
                    parent_ref=seed.parent_ref or "",
                    child_key=seed.identity_key,
                    reason=reason,
                )
            )

    return graph


def _candidate_seeds_from_row(
    row: dict[str, Any],
    *,
    depth: int,
) -> list[tuple[UnifiedSeed, str]]:
    out: list[tuple[UnifiedSeed, str]] = []
    country = _country(row.get("country") or row.get("meta"))
    parent_ref = str(
        row.get("qualityObservationId")
        or row.get("url")
        or row.get("title")
        or ""
    )[:500]
    metadata = {
        "ephemeral": True,
        "quality_score": _safe_float(row.get("qualityScore")),
        "pivot_score": _safe_float(row.get("qualityPivotScore")),
        "persistence_score": _safe_float(
            row.get("qualityPersistenceScore")
        ),
        "source": str(row.get("source") or ""),
    }

    identifiers = row.get("identifiers")
    if isinstance(identifiers, dict):
        for raw_key, raw_value in list(identifiers.items())[:80]:
            key = _kind(raw_key)
            seed_kind = _identifier_kind(key)
            if seed_kind is None:
                continue
            for value in _identifier_values(raw_value):
                seed = _make_seed(
                    kind=seed_kind,
                    value=value,
                    depth=depth,
                    country=country,
                    parent_ref=parent_ref,
                    metadata=metadata,
                )
                if seed is not None:
                    out.append(
                        (
                            seed,
                            f"Quality-approved {seed_kind.value} identifier",
                        )
                    )

    row_url = str(row.get("url") or "").strip()
    if row_url:
        url_seed = _make_seed(
            kind=UnifiedSeedKind.URL,
            value=row_url,
            depth=depth,
            country=country,
            parent_ref=parent_ref,
            metadata=metadata,
        )
        if url_seed is not None:
            out.append(
                (
                    url_seed,
                    "Quality-approved source/profile URL",
                )
            )

    family = _kind(row.get("type"))
    row_kind = _ROW_TYPE_MAP.get(family)
    if row_kind is UnifiedSeedKind.URL:
        value = str(row.get("url") or row.get("title") or "").strip()
        seed = _make_seed(
            kind=UnifiedSeedKind.URL,
            value=value,
            depth=depth,
            country=country,
            parent_ref=parent_ref,
            metadata=metadata,
        )
        if seed is not None:
            out.append(
                (
                    seed,
                    "Quality-approved discovered URL",
                )
            )
    elif row_kind is UnifiedSeedKind.DOMAIN:
        value = str(row.get("title") or row.get("url") or "").strip()
        seed = _make_seed(
            kind=UnifiedSeedKind.DOMAIN,
            value=value,
            depth=depth,
            country=country,
            parent_ref=parent_ref,
            metadata=metadata,
        )
        if seed is not None:
            out.append(
                (
                    seed,
                    "Quality-approved discovered domain",
                )
            )
    elif row_kind in {
        UnifiedSeedKind.EMAIL,
        UnifiedSeedKind.PHONE,
        UnifiedSeedKind.IP,
        UnifiedSeedKind.HASH,
    }:
        value = str(row.get("title") or "").strip()
        seed = _make_seed(
            kind=row_kind,
            value=value,
            depth=depth,
            country=country,
            parent_ref=parent_ref,
            metadata=metadata,
        )
        if seed is not None:
            out.append(
                (
                    seed,
                    f"Quality-approved discovered {row_kind.value}",
                )
            )
    elif row_kind is UnifiedSeedKind.USERNAME:
        value = _username_from_row(row)
        seed = _make_seed(
            kind=UnifiedSeedKind.USERNAME,
            value=value,
            depth=depth,
            country=country,
            parent_ref=parent_ref,
            metadata=metadata,
        )
        if seed is not None:
            out.append(
                (
                    seed,
                    "Quality-approved verified account username",
                )
            )

    # Preserve first evidence path while removing duplicates produced by both
    # identifiers and the row's own type/value.
    deduped: list[tuple[UnifiedSeed, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for seed, reason in out:
        if seed.identity_key in seen:
            continue
        seen.add(seed.identity_key)
        deduped.append((seed, reason))
    return deduped


def _identifier_kind(key: str) -> UnifiedSeedKind | None:
    if key in _IDENTIFIER_KIND_MAP:
        return _IDENTIFIER_KIND_MAP[key]
    for marker, seed_kind in _IDENTIFIER_KIND_MAP.items():
        if key.endswith("_" + marker) or key.startswith(marker + "_"):
            return seed_kind
    return None


def _identifier_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        out: list[str] = []
        for child in list(value.values())[:30]:
            out.extend(_identifier_values(child))
        return out[:60]
    if isinstance(value, (list, tuple, set, frozenset)):
        out: list[str] = []
        for child in list(value)[:30]:
            out.extend(_identifier_values(child))
        return out[:60]
    text = str(value).strip()
    return [text] if text else []


def _make_seed(
    *,
    kind: UnifiedSeedKind,
    value: str,
    depth: int,
    country: str | None,
    parent_ref: str,
    metadata: dict[str, Any],
) -> UnifiedSeed | None:
    normalized = _normalize_candidate(kind, value)
    if not normalized:
        return None
    try:
        return UnifiedSeed(
            kind=kind,
            value=normalized,
            origin="quality_exploration",
            depth=depth,
            country=country,
            parent_ref=parent_ref or None,
            candidate_only=False,
            metadata=dict(metadata),
        )
    except ValueError:
        return None


def _normalize_candidate(kind: UnifiedSeedKind, value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    if kind is UnifiedSeedKind.USERNAME:
        value = raw.lstrip("@").strip()
        return value if re.fullmatch(r"[A-Za-z0-9_.-]{2,100}", value) else ""

    if kind is UnifiedSeedKind.EMAIL:
        return raw.casefold() if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", raw) else ""

    if kind is UnifiedSeedKind.PHONE:
        prefix = "+" if raw.startswith("+") else ""
        digits = "".join(ch for ch in raw if ch.isdigit())
        return prefix + digits if 6 <= len(digits) <= 20 else ""

    if kind is UnifiedSeedKind.DOMAIN:
        candidate = raw
        if raw.startswith(("http://", "https://")):
            try:
                candidate = urlsplit(raw).hostname or ""
            except ValueError:
                return ""
        candidate = candidate.casefold().strip().rstrip(".")
        return candidate if re.fullmatch(
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
            candidate,
        ) else ""

    if kind is UnifiedSeedKind.URL:
        try:
            parsed = urlsplit(raw)
        except ValueError:
            return ""
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            return ""
        return raw

    if kind is UnifiedSeedKind.IP:
        # Keep validation dependency-free; the target router/connector performs
        # its own strict IP validation. Obvious non-IP values are rejected here.
        return raw if re.fullmatch(r"[0-9A-Fa-f:.]{3,64}", raw) else ""

    if kind is UnifiedSeedKind.HASH:
        compact = re.sub(r"\s+", "", raw)
        return compact.casefold() if re.fullmatch(
            r"[A-Fa-f0-9]{32,128}",
            compact,
        ) else ""

    return ""


def _username_from_row(row: dict[str, Any]) -> str:
    identifiers = row.get("identifiers")
    if isinstance(identifiers, dict):
        for key in ("username", "handle", "login", "user_name"):
            value = str(identifiers.get(key) or "").strip().lstrip("@")
            if value:
                return value
    seed = str(row.get("seed") or "").strip().lstrip("@")
    return seed


def _country(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text if len(text) == 2 and text.isalpha() else None


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

"""R13.26d — fair, explainable retrieval scheduling.

The scheduler is deliberately pure: no network, database, Qt, connector, or
persistence work. It replaces first-N slicing with bounded round-robin
selection so one seed/kind cannot consume a whole lane budget before other
known inputs get a chance.

Two scheduling modes are exposed:
- seeds: round-robin by UnifiedSeedKind;
- seed-routes: round-robin by seed identity, preferring configured routes.

Every scheduling decision is captured for the result snapshot so analysts can
see which work was skipped because of a budget rather than because no source
existed.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.application.unified_investigation_search import (
    UnifiedSeed,
    dedupe_seeds,
)


@dataclass(frozen=True, slots=True)
class RetrievalScheduleDecision:
    lane: str
    selected: bool
    wave: int
    reason: str
    seed_kind: str
    seed_value: str
    source: str = ""
    capability: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "selected": self.selected,
            "wave": self.wave,
            "reason": self.reason,
            "seedKind": self.seed_kind,
            "seedValue": self.seed_value,
            "source": self.source,
            "capability": self.capability,
        }


@dataclass(frozen=True, slots=True)
class RetrievalScheduleSummary:
    lane: str
    limit: int
    candidates: int
    selected: int
    skipped_due_to_budget: int
    groups: int
    waves: int
    decisions: tuple[RetrievalScheduleDecision, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "limit": self.limit,
            "candidates": self.candidates,
            "selected": self.selected,
            "skippedDueToBudget": self.skipped_due_to_budget,
            "groups": self.groups,
            "waves": self.waves,
            "decisions": [item.to_dict() for item in self.decisions],
        }


@dataclass(slots=True)
class RetrievalScheduleBook:
    entries: list[RetrievalScheduleSummary] = field(default_factory=list)

    def add(self, summary: RetrievalScheduleSummary) -> None:
        self.entries.append(summary)

    @property
    def missed_due_to_budget(self) -> int:
        return sum(item.skipped_due_to_budget for item in self.entries)

    @property
    def selected(self) -> int:
        return sum(item.selected for item in self.entries)

    @property
    def candidates(self) -> int:
        return sum(item.candidates for item in self.entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "lanes": len(self.entries),
                "candidates": self.candidates,
                "selected": self.selected,
                "missedDueToBudget": self.missed_due_to_budget,
            },
            "lanes": [item.to_dict() for item in self.entries],
        }


def schedule_seeds(
    seeds: Iterable[UnifiedSeed],
    *,
    limit: int,
    lane: str,
) -> tuple[list[UnifiedSeed], RetrievalScheduleSummary]:
    """Select seeds fairly across seed kinds rather than input position."""

    candidates = dedupe_seeds(seeds)
    bounded_limit = max(0, int(limit))
    if not candidates or bounded_limit == 0:
        decisions = tuple(
            RetrievalScheduleDecision(
                lane=lane,
                selected=False,
                wave=0,
                reason="lane budget exhausted before execution",
                seed_kind=seed.kind.value,
                seed_value=seed.value,
            )
            for seed in candidates
        )
        return [], RetrievalScheduleSummary(
            lane=lane,
            limit=bounded_limit,
            candidates=len(candidates),
            selected=0,
            skipped_due_to_budget=len(candidates),
            groups=len({seed.kind.value for seed in candidates}),
            waves=0,
            decisions=decisions,
        )

    grouped: OrderedDict[str, list[UnifiedSeed]] = OrderedDict()
    for seed in sorted(candidates, key=_seed_priority_key):
        grouped.setdefault(seed.kind.value, []).append(seed)

    selected, selected_wave = _round_robin_grouped(
        grouped,
        limit=bounded_limit,
    )
    selected_keys = {seed.identity_key for seed in selected}

    decisions: list[RetrievalScheduleDecision] = []
    for seed in candidates:
        is_selected = seed.identity_key in selected_keys
        decisions.append(
            RetrievalScheduleDecision(
                lane=lane,
                selected=is_selected,
                wave=selected_wave.get(seed.identity_key, 0),
                reason=(
                    "selected by fair kind round-robin"
                    if is_selected
                    else "skipped because lane budget was exhausted"
                ),
                seed_kind=seed.kind.value,
                seed_value=seed.value,
            )
        )

    return selected, RetrievalScheduleSummary(
        lane=lane,
        limit=bounded_limit,
        candidates=len(candidates),
        selected=len(selected),
        skipped_due_to_budget=max(0, len(candidates) - len(selected)),
        groups=len(grouped),
        waves=max(selected_wave.values(), default=0),
        decisions=tuple(decisions),
    )


def schedule_seed_routes(
    items: Iterable[tuple[UnifiedSeed, Any]],
    *,
    limit: int,
    lane: str,
) -> tuple[list[tuple[UnifiedSeed, Any]], RetrievalScheduleSummary]:
    """Select route/query work fairly across seed identities."""

    candidates = list(items)
    bounded_limit = max(0, int(limit))
    grouped: OrderedDict[
        tuple[str, str, str],
        list[tuple[UnifiedSeed, Any]],
    ] = OrderedDict()

    for seed, route in sorted(candidates, key=_route_priority_key):
        grouped.setdefault(seed.identity_key, []).append((seed, route))

    if bounded_limit == 0 or not candidates:
        decisions = tuple(
            _route_decision(
                lane=lane,
                seed=seed,
                route=route,
                selected=False,
                wave=0,
                reason="lane budget exhausted before execution",
            )
            for seed, route in candidates
        )
        return [], RetrievalScheduleSummary(
            lane=lane,
            limit=bounded_limit,
            candidates=len(candidates),
            selected=0,
            skipped_due_to_budget=len(candidates),
            groups=len(grouped),
            waves=0,
            decisions=decisions,
        )

    selected: list[tuple[UnifiedSeed, Any]] = []
    wave_by_key: dict[tuple[tuple[str, str, str], int], int] = {}
    wave = 0
    offsets = {key: 0 for key in grouped}

    while len(selected) < bounded_limit:
        wave += 1
        added = False
        for group_key, group_items in grouped.items():
            offset = offsets[group_key]
            if offset >= len(group_items):
                continue
            item = group_items[offset]
            offsets[group_key] = offset + 1
            selected.append(item)
            wave_by_key[(group_key, id(item[1]))] = wave
            added = True
            if len(selected) >= bounded_limit:
                break
        if not added:
            break

    selected_ids = {
        (seed.identity_key, id(route))
        for seed, route in selected
    }
    decisions: list[RetrievalScheduleDecision] = []
    for seed, route in candidates:
        key = (seed.identity_key, id(route))
        is_selected = key in selected_ids
        decisions.append(
            _route_decision(
                lane=lane,
                seed=seed,
                route=route,
                selected=is_selected,
                wave=wave_by_key.get(key, 0),
                reason=(
                    "selected by fair seed round-robin"
                    if is_selected
                    else "skipped because lane budget was exhausted"
                ),
            )
        )

    return selected, RetrievalScheduleSummary(
        lane=lane,
        limit=bounded_limit,
        candidates=len(candidates),
        selected=len(selected),
        skipped_due_to_budget=max(0, len(candidates) - len(selected)),
        groups=len(grouped),
        waves=max(
            (item.wave for item in decisions if item.selected),
            default=0,
        ),
        decisions=tuple(decisions),
    )


def _round_robin_grouped(
    grouped: OrderedDict[str, list[UnifiedSeed]],
    *,
    limit: int,
) -> tuple[list[UnifiedSeed], dict[tuple[str, str, str], int]]:
    selected: list[UnifiedSeed] = []
    waves: dict[tuple[str, str, str], int] = {}
    offsets = {key: 0 for key in grouped}
    wave = 0

    while len(selected) < limit:
        wave += 1
        added = False
        for group_key, group_items in grouped.items():
            offset = offsets[group_key]
            if offset >= len(group_items):
                continue
            seed = group_items[offset]
            offsets[group_key] = offset + 1
            selected.append(seed)
            waves[seed.identity_key] = wave
            added = True
            if len(selected) >= limit:
                break
        if not added:
            break

    return selected, waves


def _seed_priority_key(seed: UnifiedSeed) -> tuple[int, int, str, str]:
    origin = str(seed.origin or "").strip().casefold()
    origin_priority = {
        "user": 0,
        "discovered": 1,
        "remote": 1,
        "quality_exploration": 2,
    }.get(origin, 1)
    return (
        origin_priority,
        max(0, int(seed.depth)),
        seed.kind.value,
        seed.value.casefold(),
    )


def _route_priority_key(
    item: tuple[UnifiedSeed, Any],
) -> tuple[int, int, str, str, str]:
    seed, route = item
    configured = getattr(route, "configured", None)
    configured_priority = 0 if configured is True else 1
    return (
        _seed_priority_key(seed)[0],
        configured_priority,
        seed.kind.value,
        seed.value.casefold(),
        _route_source(route).casefold(),
    )


def _route_decision(
    *,
    lane: str,
    seed: UnifiedSeed,
    route: Any,
    selected: bool,
    wave: int,
    reason: str,
) -> RetrievalScheduleDecision:
    return RetrievalScheduleDecision(
        lane=lane,
        selected=selected,
        wave=wave,
        reason=reason,
        seed_kind=seed.kind.value,
        seed_value=seed.value,
        source=_route_source(route),
        capability=_route_capability(route),
    )


def _route_source(route: Any) -> str:
    for name in ("source_code", "provider", "source"):
        value = getattr(route, name, None)
        if value:
            return str(value)

    domain = getattr(route, "domain", None)
    if domain is not None:
        return str(getattr(domain, "value", None) or domain)

    return type(route).__name__


def _route_capability(route: Any) -> str:
    for name in ("capability", "kind"):
        value = getattr(route, name, None)
        if value is None:
            continue
        return str(getattr(value, "value", None) or value)
    return ""

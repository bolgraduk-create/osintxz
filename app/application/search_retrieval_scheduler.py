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

from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.application.connector_health import classify_provider_health
from app.application.unified_investigation_search import (
    UnifiedSeed,
    dedupe_seeds,
)


_HEALTH_PENALTIES: dict[str, float] = {
    "ready": 0.0,
    "partial": 1.5,
    "timeout": 5.0,
    "rate_limited": 4.0,
    "auth_or_policy": 6.0,
    "endpoint_error": 5.0,
    "temporarily_unavailable": 4.5,
    "not_configured": 8.0,
    "not_installed": 8.0,
    "guarded": 7.0,
    "broken": 7.0,
}

_LANE_BASE_SECONDS: dict[str, float] = {
    "federation_roots": 4.0,
    "federation_pivots": 4.0,
    "registry_roots": 5.0,
    "registry_pivots": 5.0,
}


@dataclass(slots=True)
class SourceRuntimeObservation:
    source: str
    attempts: int = 0
    total_seconds: float = 0.0
    max_seconds: float = 0.0
    records: int = 0
    states: Counter[str] = field(default_factory=Counter)

    def observe(
        self,
        *,
        state: str,
        duration_seconds: float,
        records: int,
    ) -> None:
        self.attempts += 1
        self.total_seconds += max(0.0, float(duration_seconds or 0.0))
        self.max_seconds = max(
            self.max_seconds,
            max(0.0, float(duration_seconds or 0.0)),
        )
        self.records += max(0, int(records or 0))
        self.states[str(state or "partial")] += 1

    @property
    def average_seconds(self) -> float:
        return (
            self.total_seconds / self.attempts
            if self.attempts
            else 0.0
        )

    @property
    def timeout_risk(self) -> float:
        if not self.attempts:
            return 0.0
        return min(
            1.0,
            float(self.states.get("timeout", 0)) / float(self.attempts),
        )

    @property
    def health_penalty(self) -> float:
        if not self.attempts:
            return 0.0
        weighted = sum(
            _HEALTH_PENALTIES.get(state, 2.0) * count
            for state, count in self.states.items()
        )
        return weighted / float(self.attempts)

    @property
    def dominant_state(self) -> str:
        if not self.states:
            return "unknown"
        return self.states.most_common(1)[0][0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "attempts": self.attempts,
            "averageSeconds": round(self.average_seconds, 3),
            "maxSeconds": round(self.max_seconds, 3),
            "records": self.records,
            "healthState": self.dominant_state,
            "healthPenalty": round(self.health_penalty, 2),
            "timeoutRisk": round(self.timeout_risk, 3),
            "states": dict(self.states),
        }


@dataclass(slots=True)
class AdaptiveRetrievalFeedback:
    """Ephemeral source-health/latency profile for one search run."""

    sources: dict[str, SourceRuntimeObservation] = field(default_factory=dict)

    def observe_provider_row(self, row: dict[str, Any]) -> None:
        source = str(row.get("source") or "").strip().casefold()
        if not source:
            return
        state, _label, _action, _retryable = classify_provider_health(row)
        duration = _safe_float(
            row.get("durationSeconds")
            or row.get("executionTime")
            or row.get("elapsedSeconds")
        )
        records = _safe_int(row.get("records"))
        observation = self.sources.setdefault(
            source,
            SourceRuntimeObservation(source=source),
        )
        observation.observe(
            state=state,
            duration_seconds=duration,
            records=records,
        )

    def observation(self, source: str) -> SourceRuntimeObservation | None:
        return self.sources.get(str(source or "").strip().casefold())

    def health_penalty(self, source: str) -> float:
        observation = self.observation(source)
        return observation.health_penalty if observation else 0.0

    def timeout_risk(self, source: str) -> float:
        observation = self.observation(source)
        return observation.timeout_risk if observation else 0.0

    def health_state(self, source: str) -> str:
        observation = self.observation(source)
        return observation.dominant_state if observation else "unknown"

    def estimate_seconds(
        self,
        *,
        source: str,
        route: Any,
        lane: str,
    ) -> float:
        observation = self.observation(source)
        if observation and observation.average_seconds > 0:
            estimate = observation.average_seconds * 1.15
        else:
            timeout = _safe_float(getattr(route, "timeout", 0.0))
            if timeout > 0:
                estimate = max(1.0, min(12.0, timeout * 0.25))
            else:
                estimate = _LANE_BASE_SECONDS.get(lane, 4.0)

        penalty = self.health_penalty(source)
        estimate *= 1.0 + min(1.0, penalty * 0.08)
        return max(0.5, min(30.0, estimate))

    def adaptive_score(
        self,
        *,
        source: str,
        route: Any,
        lane: str,
    ) -> float:
        return (
            self.health_penalty(source) * 10.0
            + self.timeout_risk(source) * 20.0
            + self.estimate_seconds(
                source=source,
                route=route,
                lane=lane,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": [
                observation.to_dict()
                for _source, observation in sorted(self.sources.items())
            ]
        }


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
    estimated_seconds: float = 0.0
    health_state: str = "unknown"
    health_penalty: float = 0.0
    timeout_risk: float = 0.0
    adaptive_score: float = 0.0
    deprioritized: bool = False
    time_budget_skip: bool = False

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
            "estimatedSeconds": round(self.estimated_seconds, 2),
            "healthState": self.health_state,
            "healthPenalty": round(self.health_penalty, 2),
            "timeoutRisk": round(self.timeout_risk, 3),
            "adaptiveScore": round(self.adaptive_score, 2),
            "deprioritized": self.deprioritized,
            "timeBudgetSkip": self.time_budget_skip,
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
    time_budget_seconds: float | None = None
    estimated_selected_seconds: float = 0.0
    skipped_due_to_time_budget: int = 0
    deprioritized: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "limit": self.limit,
            "candidates": self.candidates,
            "selected": self.selected,
            "skippedDueToBudget": self.skipped_due_to_budget,
            "groups": self.groups,
            "waves": self.waves,
            "timeBudgetSeconds": (
                round(self.time_budget_seconds, 2)
                if self.time_budget_seconds is not None
                else None
            ),
            "estimatedSelectedSeconds": round(
                self.estimated_selected_seconds, 2
            ),
            "skippedDueToTimeBudget": self.skipped_due_to_time_budget,
            "deprioritized": self.deprioritized,
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
    def skipped_due_to_time_budget(self) -> int:
        return sum(item.skipped_due_to_time_budget for item in self.entries)

    @property
    def deprioritized(self) -> int:
        return sum(item.deprioritized for item in self.entries)

    @property
    def estimated_selected_seconds(self) -> float:
        return sum(item.estimated_selected_seconds for item in self.entries)

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
                "skippedDueToTimeBudget": self.skipped_due_to_time_budget,
                "deprioritized": self.deprioritized,
                "estimatedSelectedSeconds": round(
                    self.estimated_selected_seconds, 2
                ),
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
    feedback: AdaptiveRetrievalFeedback | None = None,
    time_budget_seconds: float | None = None,
) -> tuple[list[tuple[UnifiedSeed, Any]], RetrievalScheduleSummary]:
    """Select route/query work fairly while accounting for cost/health."""

    candidates = list(items)
    bounded_limit = max(0, int(limit))
    profile = feedback or AdaptiveRetrievalFeedback()
    bounded_time_budget = (
        None
        if time_budget_seconds is None
        else max(0.0, float(time_budget_seconds))
    )

    grouped: OrderedDict[
        tuple[str, str, str],
        list[tuple[UnifiedSeed, Any]],
    ] = OrderedDict()

    for seed, route in sorted(
        candidates,
        key=lambda item: _route_priority_key(
            item,
            feedback=profile,
            lane=lane,
        ),
    ):
        grouped.setdefault(seed.identity_key, []).append((seed, route))

    if bounded_limit == 0 or not candidates or bounded_time_budget == 0.0:
        time_skip = bool(candidates and bounded_time_budget == 0.0)
        decisions = tuple(
            _route_decision(
                lane=lane,
                seed=seed,
                route=route,
                selected=False,
                wave=0,
                reason=(
                    "skipped because estimated time budget was exhausted"
                    if time_skip
                    else "lane budget exhausted before execution"
                ),
                feedback=profile,
                time_budget_skip=time_skip,
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
            time_budget_seconds=bounded_time_budget,
            estimated_selected_seconds=0.0,
            skipped_due_to_time_budget=(len(candidates) if time_skip else 0),
            deprioritized=sum(item.deprioritized for item in decisions),
        )

    selected: list[tuple[UnifiedSeed, Any]] = []
    wave_by_key: dict[tuple[tuple[str, str, str], int], int] = {}
    time_skipped: set[tuple[tuple[str, str, str], int]] = set()
    estimated_selected_seconds = 0.0
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
            seed, route = item
            route_key = (group_key, id(route))
            source = _route_source(route)
            estimate = profile.estimate_seconds(
                source=source,
                route=route,
                lane=lane,
            )

            if (
                bounded_time_budget is not None
                and selected
                and estimated_selected_seconds + estimate
                    > bounded_time_budget
            ):
                time_skipped.add(route_key)
                continue

            selected.append(item)
            estimated_selected_seconds += estimate
            wave_by_key[route_key] = wave
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
        is_time_skip = key in time_skipped
        decisions.append(
            _route_decision(
                lane=lane,
                seed=seed,
                route=route,
                selected=is_selected,
                wave=wave_by_key.get(key, 0),
                reason=(
                    "selected by adaptive fair round-robin"
                    if is_selected
                    else (
                        "skipped because estimated time budget was exhausted"
                        if is_time_skip
                        else "skipped because lane budget was exhausted"
                    )
                ),
                feedback=profile,
                time_budget_skip=is_time_skip,
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
        time_budget_seconds=bounded_time_budget,
        estimated_selected_seconds=estimated_selected_seconds,
        skipped_due_to_time_budget=len(time_skipped),
        deprioritized=sum(item.deprioritized for item in decisions),
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
    *,
    feedback: AdaptiveRetrievalFeedback,
    lane: str,
) -> tuple[int, int, float, float, str, str, str]:
    seed, route = item
    source = _route_source(route)
    configured = getattr(route, "configured", None)
    configured_priority = 0 if configured is True else 1
    health_penalty = feedback.health_penalty(source)
    estimate = feedback.estimate_seconds(
        source=source,
        route=route,
        lane=lane,
    )
    return (
        _seed_priority_key(seed)[0],
        configured_priority,
        health_penalty,
        estimate,
        seed.kind.value,
        seed.value.casefold(),
        source.casefold(),
    )


def _route_decision(
    *,
    lane: str,
    seed: UnifiedSeed,
    route: Any,
    selected: bool,
    wave: int,
    reason: str,
    feedback: AdaptiveRetrievalFeedback | None = None,
    time_budget_skip: bool = False,
) -> RetrievalScheduleDecision:
    profile = feedback or AdaptiveRetrievalFeedback()
    source = _route_source(route)
    health_penalty = profile.health_penalty(source)
    timeout_risk = profile.timeout_risk(source)
    estimated_seconds = profile.estimate_seconds(
        source=source,
        route=route,
        lane=lane,
    )
    adaptive_score = profile.adaptive_score(
        source=source,
        route=route,
        lane=lane,
    )
    configured = getattr(route, "configured", None)
    deprioritized = bool(
        configured is False
        or health_penalty >= 4.0
        or timeout_risk >= 0.5
        or estimated_seconds >= 10.0
    )
    return RetrievalScheduleDecision(
        lane=lane,
        selected=selected,
        wave=wave,
        reason=reason,
        seed_kind=seed.kind.value,
        seed_value=seed.value,
        source=source,
        capability=_route_capability(route),
        estimated_seconds=estimated_seconds,
        health_state=profile.health_state(source),
        health_penalty=health_penalty,
        timeout_risk=timeout_risk,
        adaptive_score=adaptive_score,
        deprioritized=deprioritized,
        time_budget_skip=time_budget_skip,
    )


def _route_source(route: Any) -> str:
    for name in ("source_code", "provider", "source"):
        value = getattr(route, name, None)
        if value:
            return str(value)

    sources = getattr(route, "sources", None)
    if sources:
        values = [str(item).strip() for item in list(sources) if str(item).strip()]
        if len(values) == 1:
            return values[0]

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

"""R14.7 explainable smart query planner.

The planner decides which already-approved ephemeral pivots are safe to execute
automatically and which should remain analyst-review suggestions. It does not
persist findings, bypass guarded routes, or turn weak identity evidence into an
automatic ownership assertion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.application.exploration_graph import ExplorationGraph, ExplorationNode
from app.application.unified_investigation_search import UnifiedSeedKind


_AUTO_KINDS = frozenset(
    {
        UnifiedSeedKind.USERNAME,
        UnifiedSeedKind.EMAIL,
        UnifiedSeedKind.PHONE,
        UnifiedSeedKind.DOMAIN,
        UnifiedSeedKind.URL,
        UnifiedSeedKind.IP,
        UnifiedSeedKind.HASH,
        UnifiedSeedKind.REGISTRATION_ID,
        UnifiedSeedKind.VAT_ID,
        UnifiedSeedKind.LEI,
        UnifiedSeedKind.CASE_NUMBER,
    }
)

_HIGH_RISK_SOURCE_MARKERS = (
    "darkweb",
    "onion",
    "breach",
    "leak",
    "stealer",
    "secret",
    "wanted",
    "sanction",
)


@dataclass(frozen=True, slots=True)
class SmartQueryDecision:
    action: str
    score: float
    reason: str
    node: ExplorationNode
    route_hint: str
    risk: str
    signals: tuple[str, ...] = ()
    auto_lanes: tuple[str, ...] = ()
    review_lanes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        seed = self.node.seed
        return {
            "action": self.action,
            "score": round(self.score, 1),
            "reason": self.reason,
            "kind": seed.kind.value,
            "value": seed.value,
            "depth": seed.depth,
            "origin": seed.origin,
            "source": self.node.source,
            "qualityScore": round(self.node.quality_score, 1),
            "pivotScore": round(self.node.pivot_score, 1),
            "persistenceScore": round(self.node.persistence_score, 1),
            "routeHint": self.route_hint,
            "risk": self.risk,
            "signals": list(self.signals),
            "autoLanes": list(self.auto_lanes),
            "reviewLanes": list(self.review_lanes),
            "observationId": self.node.observation_id,
            "parentSeedKind": self.node.parent_seed_kind,
            "parentSeedValue": self.node.parent_seed_value,
        }


@dataclass(frozen=True, slots=True)
class SmartQueryPlan:
    decisions: tuple[SmartQueryDecision, ...]

    @property
    def auto_nodes(self) -> list[ExplorationNode]:
        return [
            item.node
            for item in self.decisions
            if item.action == "auto_execute"
        ]

    @property
    def review_nodes(self) -> list[ExplorationNode]:
        return [
            item.node
            for item in self.decisions
            if item.action == "review"
        ]

    def to_dict(self) -> dict[str, Any]:
        counts = {
            "autoExecute": 0,
            "review": 0,
            "blocked": 0,
        }
        for item in self.decisions:
            if item.action == "auto_execute":
                counts["autoExecute"] += 1
            elif item.action == "review":
                counts["review"] += 1
            else:
                counts["blocked"] += 1
        return {
            "summary": {
                "candidates": len(self.decisions),
                **counts,
            },
            "decisions": [item.to_dict() for item in self.decisions],
        }


def build_smart_query_plan(
    graph: ExplorationGraph,
    *,
    max_auto: int = 6,
) -> SmartQueryPlan:
    decisions = [
        _decision(node)
        for node in list(graph.nodes)
    ]

    decisions.sort(
        key=lambda item: (
            0 if item.action == "auto_execute" else (
                1 if item.action == "review" else 2
            ),
            -item.score,
            item.node.seed.depth,
            item.node.seed.kind.value,
            item.node.seed.value.casefold(),
        )
    )

    auto_seen = 0
    bounded: list[SmartQueryDecision] = []
    for item in decisions:
        if item.action == "auto_execute":
            auto_seen += 1
            if auto_seen > max(0, int(max_auto)):
                item = SmartQueryDecision(
                    action="review",
                    score=item.score,
                    reason="Safe automatic pivot budget exhausted; retained for analyst review.",
                    node=item.node,
                    route_hint=item.route_hint,
                    risk=item.risk,
                    signals=item.signals,
                    auto_lanes=item.auto_lanes,
                    review_lanes=item.review_lanes,
                )
        bounded.append(item)

    return SmartQueryPlan(tuple(bounded))




def nodes_for_lane(
    plan: SmartQueryPlan,
    lane: str,
) -> list[ExplorationNode]:
    wanted = str(lane or "").strip().casefold()
    if not wanted:
        return []
    return [
        item.node
        for item in plan.decisions
        if item.action == "auto_execute"
        and wanted in item.auto_lanes
    ]


def graph_for_lane_execution(
    graph: ExplorationGraph,
    plan: SmartQueryPlan,
    lane: str,
) -> ExplorationGraph:
    wanted = {
        node.identity_key
        for node in nodes_for_lane(plan, lane)
    }
    return ExplorationGraph(
        nodes=[
            node
            for node in graph.nodes
            if node.identity_key in wanted
        ],
        edges=[
            edge
            for edge in graph.edges
            if edge.child_key in wanted
        ],
        skipped_initial=graph.skipped_initial,
        skipped_duplicate=graph.skipped_duplicate,
        skipped_unsupported=graph.skipped_unsupported,
        skipped_not_approved=graph.skipped_not_approved,
        skipped_depth=graph.skipped_depth,
    )

def graph_for_auto_execution(
    graph: ExplorationGraph,
    plan: SmartQueryPlan,
) -> ExplorationGraph:
    wanted = {
        item.node.identity_key
        for item in plan.decisions
        if item.action == "auto_execute"
    }
    return ExplorationGraph(
        nodes=[
            node
            for node in graph.nodes
            if node.identity_key in wanted
        ],
        edges=[
            edge
            for edge in graph.edges
            if edge.child_key in wanted
        ],
        skipped_initial=graph.skipped_initial,
        skipped_duplicate=graph.skipped_duplicate,
        skipped_unsupported=graph.skipped_unsupported,
        skipped_not_approved=graph.skipped_not_approved,
        skipped_depth=graph.skipped_depth,
    )


def _decision(node: ExplorationNode) -> SmartQueryDecision:
    seed = node.seed
    signals: list[str] = []
    risk = _risk(node)
    auto_lanes, review_lanes = _lanes(seed.kind)

    if seed.kind not in _AUTO_KINDS:
        return SmartQueryDecision(
            action="review",
            score=_score(node),
            reason="Seed kind is not approved for autonomous execution.",
            node=node,
            route_hint=_route_hint(seed.kind),
            risk=risk,
            signals=("non_auto_seed_kind",),
            auto_lanes=(),
            review_lanes=review_lanes or ("review",),
        )

    if seed.depth > 2:
        return SmartQueryDecision(
            action="blocked",
            score=_score(node),
            reason="Pivot depth exceeds the autonomous exploration boundary.",
            node=node,
            route_hint=_route_hint(seed.kind),
            risk=risk,
            signals=("depth_limit",),
            auto_lanes=(),
            review_lanes=review_lanes or auto_lanes,
        )

    source = str(node.source or "").casefold()
    if any(marker in source for marker in _HIGH_RISK_SOURCE_MARKERS):
        return SmartQueryDecision(
            action="review",
            score=_score(node),
            reason="Sensitive-source pivot requires analyst review.",
            node=node,
            route_hint=_route_hint(seed.kind),
            risk="guarded",
            signals=("sensitive_source",),
            auto_lanes=(),
            review_lanes=tuple(dict.fromkeys((*auto_lanes, *review_lanes))),
        )

    score = _score(node)

    if node.pivot_score >= 72.0 and node.quality_score >= 65.0:
        signals.extend(("quality_approved", "strong_pivot_score"))
        if node.persistence_score >= 55.0:
            signals.append("persistence_supported")
        return SmartQueryDecision(
            action="auto_execute",
            score=score,
            reason="High-quality exact pivot is safe for bounded ephemeral execution.",
            node=node,
            route_hint=_route_hint(seed.kind),
            risk=risk,
            signals=tuple(signals),
            auto_lanes=auto_lanes,
            review_lanes=review_lanes,
        )

    if node.pivot_score >= 55.0 and node.quality_score >= 50.0:
        return SmartQueryDecision(
            action="review",
            score=score,
            reason="Useful pivot signal, but confidence is below the autonomous threshold.",
            node=node,
            route_hint=_route_hint(seed.kind),
            risk=risk,
            signals=("moderate_pivot_signal",),
            auto_lanes=(),
            review_lanes=tuple(dict.fromkeys((*auto_lanes, *review_lanes))),
        )

    return SmartQueryDecision(
        action="blocked",
        score=score,
        reason="Pivot quality is too weak for automatic or suggested execution.",
        node=node,
        route_hint=_route_hint(seed.kind),
        risk=risk,
        signals=("weak_pivot_signal",),
        auto_lanes=(),
        review_lanes=tuple(dict.fromkeys((*auto_lanes, *review_lanes))),
    )


def _score(node: ExplorationNode) -> float:
    value = (
        node.pivot_score * 0.50
        + node.quality_score * 0.35
        + node.persistence_score * 0.15
    )
    return max(0.0, min(100.0, value))


def _risk(node: ExplorationNode) -> str:
    if node.seed.depth >= 2:
        return "medium"
    if node.quality_score >= 80 and node.pivot_score >= 80:
        return "low"
    return "normal"


def _lanes(kind: UnifiedSeedKind) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return automatic and analyst-review lanes for one safe exact seed.

    Open Web is review-only here because the current Open-Web enrichment path
    persists findings. Autonomous R14.8 execution is limited to lanes with a
    read-only/ephemeral boundary.
    """
    if kind in {
        UnifiedSeedKind.USERNAME,
        UnifiedSeedKind.EMAIL,
        UnifiedSeedKind.PHONE,
        UnifiedSeedKind.HASH,
    }:
        return ("classic", "federation"), ()
    if kind in {
        UnifiedSeedKind.DOMAIN,
        UnifiedSeedKind.URL,
        UnifiedSeedKind.IP,
    }:
        return ("classic", "federation"), ("open_web",)
    if kind in {
        UnifiedSeedKind.REGISTRATION_ID,
        UnifiedSeedKind.VAT_ID,
        UnifiedSeedKind.LEI,
        UnifiedSeedKind.CASE_NUMBER,
    }:
        return ("registry",), ()
    return (), ("review",)


def _route_hint(kind: UnifiedSeedKind) -> str:
    if kind in {UnifiedSeedKind.USERNAME, UnifiedSeedKind.EMAIL, UnifiedSeedKind.PHONE}:
        return "classic + federation"
    if kind in {UnifiedSeedKind.DOMAIN, UnifiedSeedKind.URL, UnifiedSeedKind.IP}:
        return "classic + federation · open web review"
    if kind is UnifiedSeedKind.HASH:
        return "classic + federation"
    return "review"


__all__ = [
    "SmartQueryDecision",
    "SmartQueryPlan",
    "build_smart_query_plan",
    "graph_for_auto_execution",
    "nodes_for_lane",
    "graph_for_lane_execution",
]

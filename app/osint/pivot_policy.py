"""
M021.1 — OSINT Pivot Policy.

Pure policy layer. It decides whether a prospective OSINT pivot is allowed.
It never executes connectors and never performs network requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType


class PivotDecisionCode(str, Enum):
    ALLOWED = "allowed"
    UNSUPPORTED_TARGET = "unsupported_target"
    UNSUPPORTED_GOAL = "unsupported_goal"
    MAX_DEPTH_REACHED = "max_depth_reached"
    ENTITY_BUDGET_EXHAUSTED = "entity_budget_exhausted"
    PIVOT_BUDGET_EXHAUSTED = "pivot_budget_exhausted"
    ALREADY_VISITED = "already_visited"


@dataclass(frozen=True, slots=True)
class PivotPolicyLimits:
    """
    Conservative defaults for future recursive discovery.

    These are application policy limits, not connector/network timeouts.
    """

    max_depth: int = 3
    max_pivots_per_entity: int = 8
    max_new_entities: int = 50

    def __post_init__(self) -> None:
        if self.max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        if self.max_pivots_per_entity < 1:
            raise ValueError("max_pivots_per_entity must be >= 1")
        if self.max_new_entities < 1:
            raise ValueError("max_new_entities must be >= 1")


@dataclass(frozen=True, slots=True)
class PivotKey:
    target_type: OsintTargetType
    normalized_value: str
    goal: DiscoveryGoal

    @classmethod
    def build(
        cls,
        target_type: OsintTargetType,
        value: str,
        goal: DiscoveryGoal,
    ) -> "PivotKey":
        return cls(
            target_type=target_type,
            normalized_value=_normalize_target_value(target_type, value),
            goal=goal,
        )


@dataclass(slots=True)
class PivotTraversalState:
    """
    In-memory traversal guard used by a single enrichment run.

    Persistence/history belongs to later M021 blocks.
    """

    visited: set[PivotKey] = field(default_factory=set)
    pivots_by_entity: dict[str, int] = field(default_factory=dict)
    new_entities_count: int = 0
    credentialed_calls_by_module: dict[str, int] = field(
        default_factory=dict
    )

    def entity_count(self, entity_identity: str) -> int:
        return self.pivots_by_entity.get(entity_identity, 0)

    def mark_visited(
        self,
        *,
        key: PivotKey,
        entity_identity: str,
    ) -> None:
        self.visited.add(key)
        self.pivots_by_entity[entity_identity] = (
            self.pivots_by_entity.get(entity_identity, 0) + 1
        )

    def add_new_entities(self, count: int) -> None:
        if count < 0:
            raise ValueError("count must be >= 0")
        self.new_entities_count += count

    def credentialed_call_count(self, module: str) -> int:
        return self.credentialed_calls_by_module.get(
            str(module or "").strip(),
            0,
        )

    def mark_credentialed_call(self, module: str) -> None:
        key = str(module or "").strip()
        if not key:
            return
        self.credentialed_calls_by_module[key] = (
            self.credentialed_calls_by_module.get(key, 0) + 1
        )

    def remaining_new_entities(
        self,
        limits: PivotPolicyLimits,
    ) -> int:
        """
        Return the remaining global new-entity budget.

        This is a read-only projection of traversal state. Persistence is
        responsible for consuming the budget only when a genuinely new Entity
        is created.
        """
        return max(
            0,
            limits.max_new_entities
            - self.new_entities_count,
        )

    def remaining_pivots(
        self,
        *,
        entity_identity: str,
        limits: PivotPolicyLimits,
    ) -> int:
        """
        Return how many automatic pivot operations remain for one entity.

        Pivot count and finding count are deliberately separate budgets.
        """
        return max(
            0,
            limits.max_pivots_per_entity
            - self.entity_count(entity_identity),
        )


@dataclass(frozen=True, slots=True)
class PivotDecision:
    allowed: bool
    code: PivotDecisionCode
    reason: str


# Only goals that already have a meaningful safe/default route are enabled here.
_DEFAULT_GOALS: dict[OsintTargetType, tuple[DiscoveryGoal, ...]] = {
    OsintTargetType.USERNAME: (
        DiscoveryGoal.ACCOUNT_DISCOVERY,
    ),
    OsintTargetType.EMAIL: (
        DiscoveryGoal.EMAIL_REGISTRATION,
        DiscoveryGoal.EMAIL_PROFILE_ENRICHMENT,
    ),
    OsintTargetType.PHONE: (
        DiscoveryGoal.PHONE_ENRICHMENT,
    ),
    OsintTargetType.DOMAIN: (
        DiscoveryGoal.DOMAIN_DISCOVERY,
        DiscoveryGoal.HISTORICAL_WEB,
        DiscoveryGoal.THREAT_INTELLIGENCE,
    ),
    OsintTargetType.URL: (
        DiscoveryGoal.HISTORICAL_WEB,
        DiscoveryGoal.THREAT_INTELLIGENCE,
    ),
    OsintTargetType.IP: (
        DiscoveryGoal.NETWORK_ENRICHMENT,
        DiscoveryGoal.THREAT_INTELLIGENCE,
    ),
    OsintTargetType.HASH: (
        DiscoveryGoal.THREAT_INTELLIGENCE,
    ),
}


class OsintPivotPolicy:
    """Deterministic allow/deny policy for OSINT enrichment pivots."""

    def __init__(
        self,
        limits: PivotPolicyLimits | None = None,
    ) -> None:
        self.limits = limits or PivotPolicyLimits()

    def default_goals(
        self,
        target_type: OsintTargetType,
    ) -> tuple[DiscoveryGoal, ...]:
        return _DEFAULT_GOALS.get(target_type, ())

    def evaluate(
        self,
        *,
        target_type: OsintTargetType,
        value: str,
        goal: DiscoveryGoal,
        depth: int,
        entity_identity: str,
        state: PivotTraversalState,
    ) -> PivotDecision:
        goals = self.default_goals(target_type)

        if not goals:
            return PivotDecision(
                allowed=False,
                code=PivotDecisionCode.UNSUPPORTED_TARGET,
                reason=(
                    f"No automatic OSINT enrichment goals are defined for "
                    f"{target_type.value}."
                ),
            )

        if goal not in goals:
            return PivotDecision(
                allowed=False,
                code=PivotDecisionCode.UNSUPPORTED_GOAL,
                reason=(
                    f"{goal.value} is not an automatic goal for "
                    f"{target_type.value}."
                ),
            )

        if depth > self.limits.max_depth:
            return PivotDecision(
                allowed=False,
                code=PivotDecisionCode.MAX_DEPTH_REACHED,
                reason=(
                    f"Pivot depth {depth} exceeds max_depth "
                    f"{self.limits.max_depth}."
                ),
            )

        if state.new_entities_count >= self.limits.max_new_entities:
            return PivotDecision(
                allowed=False,
                code=PivotDecisionCode.ENTITY_BUDGET_EXHAUSTED,
                reason="Maximum new-entity budget has been reached.",
            )

        if (
            state.entity_count(entity_identity)
            >= self.limits.max_pivots_per_entity
        ):
            return PivotDecision(
                allowed=False,
                code=PivotDecisionCode.PIVOT_BUDGET_EXHAUSTED,
                reason=(
                    "Maximum pivot budget for this entity has been reached."
                ),
            )

        key = PivotKey.build(target_type, value, goal)
        if key in state.visited:
            return PivotDecision(
                allowed=False,
                code=PivotDecisionCode.ALREADY_VISITED,
                reason="This normalized target/goal pivot was already visited.",
            )

        return PivotDecision(
            allowed=True,
            code=PivotDecisionCode.ALLOWED,
            reason="Pivot is allowed by the current automatic OSINT policy.",
        )


def _normalize_target_value(
    target_type: OsintTargetType,
    value: str,
) -> str:
    value = value.strip()

    if target_type is OsintTargetType.EMAIL:
        return value.casefold()

    if target_type is OsintTargetType.USERNAME:
        return value.lstrip("@").casefold()

    if target_type is OsintTargetType.DOMAIN:
        return value.casefold().rstrip(".")

    if target_type is OsintTargetType.PHONE:
        prefix = "+" if value.startswith("+") else ""
        digits = "".join(ch for ch in value if ch.isdigit())
        return prefix + digits

    if target_type in {
        OsintTargetType.URL,
        OsintTargetType.IP,
        OsintTargetType.HASH,
    }:
        return value.casefold()

    return value

"""
M021.1 — OSINT Capability Router.

Converts an allowed pivot into a deterministic set of connector capabilities.
No connector execution happens here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.osint.capabilities import (
    ConnectorDisposition,
    DiscoveryGoal,
    NetworkMode,
    OsintConnectorCapability,
    OSINT_CAPABILITY_CATALOG,
)
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import (
    OsintPivotPolicy,
    PivotDecision,
    PivotTraversalState,
)


@dataclass(frozen=True, slots=True)
class PivotRoute:
    target_type: OsintTargetType
    value: str
    goal: DiscoveryGoal
    depth: int
    decision: PivotDecision
    connectors: tuple[OsintConnectorCapability, ...]

    @property
    def allowed(self) -> bool:
        return self.decision.allowed


class OsintCapabilityRouter:
    """
    Route automatic enrichment only through catalog entries that are:
    - compatible with target type
    - assigned to the requested discovery goal
    - default-enabled
    - not credentialed
    - not CONDITIONAL / SEPARATE / REPLACE
    """

    def __init__(
        self,
        policy: OsintPivotPolicy | None = None,
    ) -> None:
        self.policy = policy or OsintPivotPolicy()

    def route(
        self,
        *,
        target_type: OsintTargetType,
        value: str,
        goal: DiscoveryGoal,
        depth: int,
        entity_identity: str,
        state: PivotTraversalState,
    ) -> PivotRoute:
        decision = self.policy.evaluate(
            target_type=target_type,
            value=value,
            goal=goal,
            depth=depth,
            entity_identity=entity_identity,
            state=state,
        )

        if not decision.allowed:
            return PivotRoute(
                target_type=target_type,
                value=value,
                goal=goal,
                depth=depth,
                decision=decision,
                connectors=(),
            )

        allowed_dispositions = self._allowed_dispositions_for_goal(goal)

        connectors = tuple(
            sorted(
                (
                    capability
                    for capability in OSINT_CAPABILITY_CATALOG.values()
                    if target_type in capability.input_types
                    and goal in capability.goals
                    and capability.default_enabled
                    and not capability.requires_account
                    and not capability.requires_api_key
                    and capability.disposition in allowed_dispositions
                    and self._network_mode_allowed_for_goal(
                        capability=capability,
                        goal=goal,
                    )
                ),
                key=lambda item: (
                    -item.recursive_value,
                    item.display_name.casefold(),
                ),
            )
        )

        return PivotRoute(
            target_type=target_type,
            value=value,
            goal=goal,
            depth=depth,
            decision=decision,
            connectors=connectors,
        )

    @staticmethod
    def _allowed_dispositions_for_goal(
        goal: DiscoveryGoal,
    ) -> frozenset[ConnectorDisposition]:
        """Return product roles allowed in an automatic route for a goal."""

        if goal in {
            DiscoveryGoal.ACCOUNT_DISCOVERY,
            DiscoveryGoal.EMAIL_REGISTRATION,
            DiscoveryGoal.HISTORICAL_WEB,
            DiscoveryGoal.PHONE_ENRICHMENT,
        }:
            return frozenset(
                {
                    ConnectorDisposition.CORE,
                    ConnectorDisposition.SUPPORT,
                }
            )

        return frozenset(
            {
                ConnectorDisposition.CORE,
            }
        )

    @staticmethod
    def _network_mode_allowed_for_goal(
        *,
        capability: OsintConnectorCapability,
        goal: DiscoveryGoal,
    ) -> bool:
        """Keep automatic account discovery strictly passive."""

        if goal in {
            DiscoveryGoal.ACCOUNT_DISCOVERY,
            DiscoveryGoal.EMAIL_REGISTRATION,
            DiscoveryGoal.HISTORICAL_WEB,
            DiscoveryGoal.PHONE_ENRICHMENT,
        }:
            return capability.network_mode in {
                NetworkMode.PASSIVE,
                NetworkMode.PASSIVE_REMOTE,
            }

        # Preserve pre-existing routing behavior for all other goals.
        return True

    def route_defaults(
        self,
        *,
        target_type: OsintTargetType,
        value: str,
        depth: int,
        entity_identity: str,
        state: PivotTraversalState,
    ) -> tuple[PivotRoute, ...]:
        return tuple(
            self.route(
                target_type=target_type,
                value=value,
                goal=goal,
                depth=depth,
                entity_identity=entity_identity,
                state=state,
            )
            for goal in self.policy.default_goals(target_type)
        )

"""M021.1 / R13.28.1 — deterministic OSINT capability routing."""

from __future__ import annotations

from dataclasses import dataclass

from app.osint.capabilities import (
    ConnectorDisposition,
    DiscoveryGoal,
    NetworkMode,
    OsintConnectorCapability,
    OSINT_CAPABILITY_CATALOG,
)
from app.osint.threat_intelligence_policy import (
    AUTO_CREDENTIALED_THREAT_MODULES,
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
    """Select safe automatic connector capabilities.

    Existing keyless defaults keep their old behavior. R13.28.1 additionally
    permits an explicit allow-list of credentialed passive threat-intelligence
    connectors, but only when the composition root confirms that their API
    credential is actually configured.
    """

    def __init__(
        self,
        policy: OsintPivotPolicy | None = None,
        *,
        configured_credential_modules: frozenset[str] | None = None,
    ) -> None:
        self.policy = policy or OsintPivotPolicy()
        self.configured_credential_modules = frozenset(
            configured_credential_modules or ()
        )

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

        connectors = tuple(
            sorted(
                (
                    capability
                    for capability in OSINT_CAPABILITY_CATALOG.values()
                    if target_type in capability.input_types
                    and goal in capability.goals
                    and self._capability_is_automatic(
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

    def default_goals_for(
        self,
        target_type: OsintTargetType,
    ) -> tuple[DiscoveryGoal, ...]:
        """Return default goals that have an executable automatic route.

        Threat-intelligence is policy-allowed for IP/domain/URL/hash, but it is
        omitted unless at least one explicitly supported credentialed source is
        configured. This keeps the historical keyless behavior deterministic.
        """

        goals: list[DiscoveryGoal] = []
        for goal in self.policy.default_goals(target_type):
            if goal is not DiscoveryGoal.THREAT_INTELLIGENCE:
                goals.append(goal)
                continue

            has_configured_route = any(
                target_type in capability.input_types
                and goal in capability.goals
                and self._credentialed_threat_capability_allowed(capability)
                for capability in OSINT_CAPABILITY_CATALOG.values()
            )
            if has_configured_route:
                goals.append(goal)

        return tuple(goals)

    def _capability_is_automatic(
        self,
        *,
        capability: OsintConnectorCapability,
        goal: DiscoveryGoal,
    ) -> bool:
        allowed_dispositions = self._allowed_dispositions_for_goal(goal)

        standard_default = bool(
            capability.default_enabled
            and not capability.requires_account
            and not capability.requires_api_key
            and capability.disposition in allowed_dispositions
            and self._network_mode_allowed_for_goal(
                capability=capability,
                goal=goal,
            )
        )
        if standard_default:
            return True

        return bool(
            goal is DiscoveryGoal.THREAT_INTELLIGENCE
            and self._credentialed_threat_capability_allowed(capability)
        )

    def _credentialed_threat_capability_allowed(
        self,
        capability: OsintConnectorCapability,
    ) -> bool:
        return bool(
            capability.module in AUTO_CREDENTIALED_THREAT_MODULES
            and capability.module in self.configured_credential_modules
            and capability.requires_api_key
            and not capability.requires_account
            and capability.disposition is ConnectorDisposition.CONDITIONAL
            and capability.network_mode is NetworkMode.PASSIVE_REMOTE
            and DiscoveryGoal.THREAT_INTELLIGENCE in capability.goals
        )

    @staticmethod
    def _allowed_dispositions_for_goal(
        goal: DiscoveryGoal,
    ) -> frozenset[ConnectorDisposition]:
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

        return frozenset({ConnectorDisposition.CORE})

    @staticmethod
    def _network_mode_allowed_for_goal(
        *,
        capability: OsintConnectorCapability,
        goal: DiscoveryGoal,
    ) -> bool:
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
            for goal in self.default_goals_for(target_type)
        )

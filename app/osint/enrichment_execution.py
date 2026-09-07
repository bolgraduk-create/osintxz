"""
M021.2 — OSINT Enrichment Execution Boundary.

Connects:
    Pivot Policy -> Capability Router -> existing OsintPipeline

Does NOT persist findings, create entities/evidence, recurse, or call AI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.osint.capabilities import DiscoveryGoal, OsintConnectorCapability
from app.osint.models import ConnectorRequest, OsintTarget, OsintTargetType
from app.osint.pipeline import OsintPipeline
from app.osint.pivot_policy import PivotKey, PivotTraversalState
from app.osint.pivot_router import OsintCapabilityRouter, PivotRoute
from app.osint.result import OsintResult, ResultStatus


class EnrichmentExecutionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ConnectorExecutionRecord:
    capability: OsintConnectorCapability
    runtime_connector_name: str | None
    result: OsintResult

    @property
    def available(self) -> bool:
        return self.result.status is not ResultStatus.NOT_AVAILABLE


@dataclass(slots=True)
class EnrichmentExecutionResult:
    route: PivotRoute
    status: EnrichmentExecutionStatus
    records: list[ConnectorExecutionRecord] = field(default_factory=list)
    error: str | None = None

    @property
    def results(self) -> list[OsintResult]:
        return [record.result for record in self.records]

    @property
    def total_connectors(self) -> int:
        return len(self.records)

    @property
    def total_findings(self) -> int:
        return sum(result.total_findings for result in self.results)

    @property
    def successful_connectors(self) -> int:
        return sum(result.status is ResultStatus.SUCCESS for result in self.results)

    @property
    def partial_connectors(self) -> int:
        return sum(result.status is ResultStatus.PARTIAL for result in self.results)

    @property
    def failed_connectors(self) -> int:
        return sum(result.status is ResultStatus.FAILED for result in self.results)

    @property
    def unavailable_connectors(self) -> int:
        return sum(result.status is ResultStatus.NOT_AVAILABLE for result in self.results)


class OsintEnrichmentExecutionService:
    """Execute only connectors explicitly selected by M021 routing policy."""

    def __init__(
        self,
        *,
        pipeline: OsintPipeline,
        router: OsintCapabilityRouter | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.router = router or OsintCapabilityRouter()

    def execute(
        self,
        *,
        target_type: OsintTargetType,
        value: str,
        goal: DiscoveryGoal,
        depth: int,
        entity_identity: str,
        state: PivotTraversalState,
        case_id: str | None = None,
        timeout: int = 300,
        use_cache: bool = True,
        save_raw_output: bool = False,
        include_metadata: bool = True,
        include_related: bool = True,
    ) -> EnrichmentExecutionResult:
        route = self.router.route(
            target_type=target_type,
            value=value,
            goal=goal,
            depth=depth,
            entity_identity=entity_identity,
            state=state,
        )

        if not route.allowed:
            return EnrichmentExecutionResult(
                route=route,
                status=EnrichmentExecutionStatus.SKIPPED,
                error=route.decision.reason,
            )

        if not route.connectors:
            return EnrichmentExecutionResult(
                route=route,
                status=EnrichmentExecutionStatus.SKIPPED,
                error="Pivot is allowed, but no automatic connector capability is available.",
            )

        state.mark_visited(
            key=PivotKey.build(target_type, value, goal),
            entity_identity=entity_identity,
        )

        request = ConnectorRequest(
            target=OsintTarget(
                target_type=target_type,
                value=value,
                case_id=case_id,
            ),
            timeout=timeout,
            use_cache=use_cache,
            save_raw_output=save_raw_output,
            include_metadata=include_metadata,
            include_related=include_related,
        )

        records: list[ConnectorExecutionRecord] = []

        for capability in route.connectors:
            runtime_name = self._resolve_runtime_connector_name(capability)

            if runtime_name is None:
                result = OsintResult(
                    connector=capability.display_name,
                    status=ResultStatus.NOT_AVAILABLE,
                    error=(
                        "Connector was selected by capability policy but is "
                        "not registered in the current OsintManager runtime."
                    ),
                    metadata={
                        "capability_module": capability.module,
                        "connector_class": capability.connector_class,
                    },
                )
            else:
                result = self._execute_connector(
                    runtime_name=runtime_name,
                    capability=capability,
                    request=request,
                )

            records.append(
                ConnectorExecutionRecord(
                    capability=capability,
                    runtime_connector_name=runtime_name,
                    result=result,
                )
            )

        return EnrichmentExecutionResult(
            route=route,
            status=self._aggregate_status(records),
            records=records,
        )

    def execute_defaults(
        self,
        *,
        target_type: OsintTargetType,
        value: str,
        depth: int,
        entity_identity: str,
        state: PivotTraversalState,
        case_id: str | None = None,
        timeout: int = 300,
        use_cache: bool = True,
        save_raw_output: bool = False,
        include_metadata: bool = True,
        include_related: bool = True,
    ) -> tuple[EnrichmentExecutionResult, ...]:
        goals = self.router.policy.default_goals(target_type)

        return tuple(
            self.execute(
                target_type=target_type,
                value=value,
                goal=goal,
                depth=depth,
                entity_identity=entity_identity,
                state=state,
                case_id=case_id,
                timeout=timeout,
                use_cache=use_cache,
                save_raw_output=save_raw_output,
                include_metadata=include_metadata,
                include_related=include_related,
            )
            for goal in goals
        )

    def _resolve_runtime_connector_name(
        self,
        capability: OsintConnectorCapability,
    ) -> str | None:
        registry = self.pipeline.manager.registry

        for connector in registry.all():
            if connector.__class__.__name__ == capability.connector_class:
                return connector.name

        return None

    def _execute_connector(
        self,
        *,
        runtime_name: str,
        capability: OsintConnectorCapability,
        request: ConnectorRequest,
    ) -> OsintResult:
        try:
            result = self.pipeline.run_connector(runtime_name, request)
        except Exception as exc:  # defensive boundary
            return OsintResult(
                connector=runtime_name,
                status=ResultStatus.FAILED,
                error=str(exc),
                metadata={
                    "capability_module": capability.module,
                    "execution_boundary_exception": True,
                },
            )

        if result is None:
            return OsintResult(
                connector=runtime_name,
                status=ResultStatus.NOT_AVAILABLE,
                error="Connector disappeared from runtime registry before execution.",
                metadata={"capability_module": capability.module},
            )

        result.metadata.setdefault("capability_module", capability.module)
        result.metadata.setdefault(
            "discovery_goals",
            sorted(goal.value for goal in capability.goals),
        )
        return result

    @staticmethod
    def _aggregate_status(
        records: list[ConnectorExecutionRecord],
    ) -> EnrichmentExecutionStatus:
        if not records:
            return EnrichmentExecutionStatus.SKIPPED

        statuses = [record.result.status for record in records]

        if all(status is ResultStatus.SUCCESS for status in statuses):
            return EnrichmentExecutionStatus.SUCCESS

        usable = any(
            status in {ResultStatus.SUCCESS, ResultStatus.PARTIAL}
            for status in statuses
        )
        if usable:
            return EnrichmentExecutionStatus.PARTIAL

        return EnrichmentExecutionStatus.FAILED

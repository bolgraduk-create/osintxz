from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.application.osint_recursive_enrichment_service import (
    OsintRecursiveEnrichmentService,
    RecursiveEnrichmentSeed,
    RecursiveExpansionStopReason,
)
from app.osint.capabilities import DiscoveryGoal
from app.osint.enrichment_execution import (
    OsintEnrichmentExecutionService,
)
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import (
    PivotPolicyLimits,
    PivotTraversalState,
)
from app.osint.result import (
    OsintFinding,
    OsintResult,
    ResultStatus,
)


class FakePolicy:
    def __init__(self, *, limits, goals):
        self.limits = limits
        self._goals = goals

    def default_goals(self, target_type):
        return self._goals


class FakeRouter:
    def __init__(self, *, limits, goals, connectors):
        self.policy = FakePolicy(
            limits=limits,
            goals=goals,
        )
        self.connectors = connectors

    def route(self, **kwargs):
        return SimpleNamespace(
            allowed=True,
            decision=SimpleNamespace(reason="allowed"),
            connectors=self.connectors,
        )


class RecordingExecutionService(OsintEnrichmentExecutionService):
    def __init__(self, *, router, returned_findings: int):
        super().__init__(
            pipeline=SimpleNamespace(
                manager=SimpleNamespace(
                    registry=SimpleNamespace(
                        all=lambda: [],
                    )
                )
            ),
            router=router,
        )
        self.returned_findings = returned_findings
        self.requests = []

    def _resolve_runtime_connector_name(self, capability):
        return capability.display_name

    def _execute_connector(
        self,
        *,
        runtime_name,
        capability,
        request,
    ):
        self.requests.append(request)
        return OsintResult(
            connector=runtime_name,
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="subdomain",
                    value=f"host-{index}.example.com",
                )
                for index in range(self.returned_findings)
            ],
        )


def capability(name: str, goal: DiscoveryGoal):
    return SimpleNamespace(
        display_name=name,
        module=f"test.{name}",
        connector_class=f"{name}Connector",
        goals=frozenset({goal}),
    )


def test_execute_defaults_caps_one_target_without_changing_global_budget():
    goal = DiscoveryGoal.DOMAIN_DISCOVERY
    limits = PivotPolicyLimits(
        max_depth=3,
        max_pivots_per_entity=8,
        max_new_entities=50,
    )
    router = FakeRouter(
        limits=limits,
        goals=(goal,),
        connectors=(capability("discovery", goal),),
    )
    service = RecordingExecutionService(
        router=router,
        returned_findings=50,
    )

    state = PivotTraversalState()

    results = service.execute_defaults(
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
        depth=0,
        entity_identity="root",
        state=state,
        entity_budget_limit=5,
    )

    assert len(service.requests) == 1
    assert service.requests[0].limit == 5
    assert results[0].total_findings == 5
    assert results[0].entity_budget is not None
    assert results[0].entity_budget.limit == 5

    # The target-local budget must not mutate traversal state by itself.
    # Persistence remains the only component that consumes global entities.
    assert state.new_entities_count == 0


def test_target_budget_never_exceeds_remaining_global_budget():
    goal = DiscoveryGoal.DOMAIN_DISCOVERY
    limits = PivotPolicyLimits(
        max_depth=3,
        max_pivots_per_entity=8,
        max_new_entities=50,
    )
    router = FakeRouter(
        limits=limits,
        goals=(goal,),
        connectors=(capability("discovery", goal),),
    )
    service = RecordingExecutionService(
        router=router,
        returned_findings=50,
    )

    state = PivotTraversalState(
        new_entities_count=48,
    )

    results = service.execute_defaults(
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
        depth=1,
        entity_identity="child",
        state=state,
        entity_budget_limit=5,
    )

    assert service.requests[0].limit == 2
    assert results[0].entity_budget.limit == 2
    assert results[0].total_findings == 2


class FakeRecursiveEnrichmentService:
    def __init__(self):
        limits = PivotPolicyLimits(
            max_depth=3,
            max_pivots_per_entity=8,
            max_new_entities=50,
        )
        self.execution_service = SimpleNamespace(
            router=SimpleNamespace(
                policy=SimpleNamespace(limits=limits)
            )
        )
        self.calls = []

    def enrich_target(self, **kwargs):
        self.calls.append(kwargs)

        # Simulate real persistence consumption.
        kwargs["state"].add_new_entities(
            kwargs["new_entity_limit"]
        )

        return SimpleNamespace(
            target_type=kwargs["target_type"],
            target_value=kwargs["value"],
            parent_entity_id=kwargs["parent_entity_id"],
            depth=kwargs["depth"],
            state=kwargs["state"],
            persisted_findings=kwargs["new_entity_limit"],
            entities_created=kwargs["new_entity_limit"],
            sources_created=1,
            evidences_created=kwargs["new_entity_limit"],
            persistence=[],
        )


class OneChildCandidatePolicy:
    def from_enrichment_result(self, run, *, next_depth):
        if run.depth >= 1:
            return ()

        entity_id = uuid4()

        return (
            SimpleNamespace(
                target_type=OsintTargetType.URL,
                value="https://example.com/privacy",
                entity_id=entity_id,
                depth=next_depth,
            ),
        )


def test_recursive_per_target_budget_leaves_room_for_child_pivot():
    enrichment = FakeRecursiveEnrichmentService()

    service = OsintRecursiveEnrichmentService(
        enrichment_service=enrichment,
        candidate_policy=OneChildCandidatePolicy(),
    )

    result = service.enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                target_type=OsintTargetType.DOMAIN,
                value="example.com",
            ),
        ),
        max_targets=2,
        per_target_new_entity_limit=5,
    )

    assert result.targets_processed == 2
    assert result.candidates_enqueued == 1
    assert [call["new_entity_limit"] for call in enrichment.calls] == [5, 5]
    assert result.state.new_entities_count == 10
    assert (
        result.stop_reason
        is RecursiveExpansionStopReason.QUEUE_EXHAUSTED
    )

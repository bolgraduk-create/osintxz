from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.application.osint_recursive_enrichment_service import (
    OsintRecursiveEnrichmentService,
    RecursiveEnrichmentSeed,
    RecursiveExpansionStopReason,
)
from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import (
    OsintPivotPolicy,
    PivotDecisionCode,
    PivotKey,
    PivotPolicyLimits,
    PivotTraversalState,
)


@dataclass(slots=True)
class FakeRun:
    value: str
    depth: int
    parent_entity_id: UUID | None
    persisted_findings: int = 0
    sources_created: int = 0
    evidences_created: int = 0
    entities_created: int = 0


class ChainCandidatePolicy:
    """
    Always proposes one child after every completed run.

    This intentionally keeps proposing beyond max_depth so the real recursive
    service, rather than the fake policy, must enforce the depth boundary.
    """

    def __init__(self) -> None:
        self.generated = 0

    def from_enrichment_result(
        self,
        run: FakeRun,
        *,
        next_depth: int,
    ):
        self.generated += 1
        return (
            SimpleNamespace(
                target_type=OsintTargetType.DOMAIN,
                value=f"depth-{next_depth}.example.com",
                entity_id=uuid4(),
                depth=next_depth,
            ),
        )


class NoCandidatePolicy:
    def from_enrichment_result(
        self,
        run,
        *,
        next_depth: int,
    ):
        return ()


class FanoutCandidatePolicy:
    """
    Produce deterministic child candidates for a bounded tree.

    Children have unique entity ids, matching the normal recursive model where
    persisted entities become future pivots.
    """

    def __init__(
        self,
        *,
        fanout: int,
    ) -> None:
        self.fanout = fanout
        self.generated = 0

    def from_enrichment_result(
        self,
        run: FakeRun,
        *,
        next_depth: int,
    ):
        candidates = []

        for index in range(self.fanout):
            self.generated += 1
            candidates.append(
                SimpleNamespace(
                    target_type=OsintTargetType.DOMAIN,
                    value=(
                        f"d{next_depth}-"
                        f"{self.generated}-"
                        "example.com"
                    ),
                    entity_id=uuid4(),
                    depth=next_depth,
                )
            )

        return tuple(candidates)


class FakeExecutionService:
    def __init__(
        self,
        policy: OsintPivotPolicy,
    ) -> None:
        self.router = SimpleNamespace(
            policy=policy,
        )


class CountingEnrichmentService:
    """
    Minimal deterministic substitute for OsintEnrichmentService.

    It keeps the real recursive service and real PivotPolicyLimits in control,
    while replacing all network/database work.
    """

    def __init__(
        self,
        *,
        limits: PivotPolicyLimits,
        entities_per_run: int = 0,
    ) -> None:
        self.execution_service = FakeExecutionService(
            OsintPivotPolicy(
                limits,
            )
        )
        self.entities_per_run = entities_per_run
        self.calls: list[dict] = []

    def enrich_target(
        self,
        *,
        case_id,
        target_type,
        value,
        parent_entity_id,
        depth,
        state,
        **kwargs,
    ):
        remaining = state.remaining_new_entities(
            self.execution_service.router.policy.limits
        )

        created = min(
            self.entities_per_run,
            remaining,
        )

        if created:
            state.add_new_entities(
                created,
            )

        self.calls.append(
            {
                "target_type": target_type,
                "value": value,
                "parent_entity_id": parent_entity_id,
                "depth": depth,
                "entities_created": created,
            }
        )

        return FakeRun(
            value=value,
            depth=depth,
            parent_entity_id=parent_entity_id,
            persisted_findings=created,
            entities_created=created,
        )


class PolicyAwareEnrichmentService:
    """
    Simulates the real execution boundary using the actual OsintPivotPolicy.

    Multiple scheduled targets may reference the same parent entity. Only the
    first max_pivots_per_entity automatic executions are allowed.
    """

    def __init__(
        self,
        *,
        limits: PivotPolicyLimits,
    ) -> None:
        self.policy = OsintPivotPolicy(
            limits,
        )
        self.execution_service = FakeExecutionService(
            self.policy,
        )
        self.allowed: list[str] = []
        self.blocked: list[
            tuple[str, PivotDecisionCode]
        ] = []

    def enrich_target(
        self,
        *,
        case_id,
        target_type,
        value,
        parent_entity_id,
        depth,
        state,
        **kwargs,
    ):
        entity_identity = (
            str(parent_entity_id)
            if parent_entity_id is not None
            else f"seed:{value}"
        )

        goal = DiscoveryGoal.DOMAIN_DISCOVERY

        decision = self.policy.evaluate(
            target_type=target_type,
            value=value,
            goal=goal,
            depth=depth,
            entity_identity=entity_identity,
            state=state,
        )

        if decision.allowed:
            state.mark_visited(
                key=PivotKey.build(
                    target_type,
                    value,
                    goal,
                ),
                entity_identity=entity_identity,
            )
            self.allowed.append(
                value,
            )
        else:
            self.blocked.append(
                (
                    value,
                    decision.code,
                )
            )

        return FakeRun(
            value=value,
            depth=depth,
            parent_entity_id=parent_entity_id,
        )


def test_recursive_service_never_processes_beyond_max_depth() -> None:
    limits = PivotPolicyLimits(
        max_depth=3,
        max_pivots_per_entity=8,
        max_new_entities=50,
    )

    enrichment = CountingEnrichmentService(
        limits=limits,
    )

    service = OsintRecursiveEnrichmentService(
        enrichment_service=enrichment,
        candidate_policy=ChainCandidatePolicy(),
    )

    result = service.enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                target_type=OsintTargetType.DOMAIN,
                value="example.com",
            ),
        ),
    )

    processed_depths = [
        item["depth"]
        for item in enrichment.calls
    ]

    assert processed_depths == [
        0,
        1,
        2,
        3,
    ]
    assert max(processed_depths) == limits.max_depth
    assert result.targets_processed == 4
    assert (
        result.stop_reason
        is RecursiveExpansionStopReason.MAX_DEPTH_REACHED
    )


def test_recursive_service_stops_exactly_at_global_new_entity_budget() -> None:
    limits = PivotPolicyLimits(
        max_depth=10,
        max_pivots_per_entity=8,
        max_new_entities=5,
    )

    enrichment = CountingEnrichmentService(
        limits=limits,
        entities_per_run=1,
    )

    service = OsintRecursiveEnrichmentService(
        enrichment_service=enrichment,
        candidate_policy=ChainCandidatePolicy(),
    )

    state = PivotTraversalState()

    result = service.enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                target_type=OsintTargetType.DOMAIN,
                value="example.com",
            ),
        ),
        state=state,
    )

    assert state.new_entities_count == 5
    assert state.new_entities_count <= limits.max_new_entities
    assert result.targets_processed == 5
    assert result.entities_created == 5
    assert (
        result.stop_reason
        is RecursiveExpansionStopReason.NEW_ENTITY_BUDGET_REACHED
    )


def test_real_pivot_policy_blocks_ninth_pivot_for_same_entity() -> None:
    limits = PivotPolicyLimits(
        max_depth=3,
        max_pivots_per_entity=8,
        max_new_entities=50,
    )

    enrichment = PolicyAwareEnrichmentService(
        limits=limits,
    )

    service = OsintRecursiveEnrichmentService(
        enrichment_service=enrichment,
        candidate_policy=NoCandidatePolicy(),
    )

    shared_parent = uuid4()

    seeds = tuple(
        RecursiveEnrichmentSeed(
            target_type=OsintTargetType.DOMAIN,
            value=f"candidate-{index}.example.com",
            parent_entity_id=shared_parent,
        )
        for index in range(10)
    )

    state = PivotTraversalState()

    result = service.enrich(
        case_id=uuid4(),
        seeds=seeds,
        state=state,
    )

    entity_identity = str(
        shared_parent,
    )

    assert len(enrichment.allowed) == 8
    assert len(enrichment.blocked) == 2
    assert state.entity_count(entity_identity) == 8
    assert (
        state.entity_count(entity_identity)
        <= limits.max_pivots_per_entity
    )

    assert {
        code
        for _, code in enrichment.blocked
    } == {
        PivotDecisionCode.PIVOT_BUDGET_EXHAUSTED,
    }

    # The recursive scheduler may hand all ten targets to enrichment, but the
    # real pivot policy permits connector-like execution only eight times.
    assert result.targets_processed == 10


def test_combined_recursive_tree_respects_depth_and_entity_budget() -> None:
    limits = PivotPolicyLimits(
        max_depth=3,
        max_pivots_per_entity=8,
        max_new_entities=50,
    )

    enrichment = CountingEnrichmentService(
        limits=limits,
        entities_per_run=3,
    )

    service = OsintRecursiveEnrichmentService(
        enrichment_service=enrichment,
        candidate_policy=FanoutCandidatePolicy(
            fanout=4,
        ),
    )

    state = PivotTraversalState()

    result = service.enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                target_type=OsintTargetType.DOMAIN,
                value="example.com",
            ),
        ),
        state=state,
    )

    assert enrichment.calls

    assert max(
        item["depth"]
        for item in enrichment.calls
    ) <= limits.max_depth

    assert (
        state.new_entities_count
        == limits.max_new_entities
    )

    assert (
        result.entities_created
        == limits.max_new_entities
    )

    assert (
        result.stop_reason
        is RecursiveExpansionStopReason.NEW_ENTITY_BUDGET_REACHED
    )

    # Most importantly: even under branching pressure, the traversal cannot
    # create entity #51.
    assert state.new_entities_count <= 50

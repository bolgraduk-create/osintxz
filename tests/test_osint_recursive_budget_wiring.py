from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.entity import EntityType
from app.osint.capabilities import DiscoveryGoal
from app.osint.enrichment_execution import (
    NewEntityBudget,
    OsintEnrichmentExecutionService,
)
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
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
    def __init__(
        self,
        limits: PivotPolicyLimits,
        goals: tuple[DiscoveryGoal, ...],
    ) -> None:
        self.limits = limits
        self._goals = goals

    def default_goals(
        self,
        target_type: OsintTargetType,
    ) -> tuple[DiscoveryGoal, ...]:
        return self._goals


class FakeRouter:
    def __init__(
        self,
        *,
        limits: PivotPolicyLimits,
        goals: tuple[DiscoveryGoal, ...],
        connectors: tuple[object, ...],
    ) -> None:
        self.policy = FakePolicy(
            limits,
            goals,
        )
        self.connectors = connectors

    def route(
        self,
        **kwargs,
    ):
        return SimpleNamespace(
            allowed=True,
            decision=SimpleNamespace(
                reason="allowed",
            ),
            connectors=self.connectors,
        )


class RecordingExecutionService(
    OsintEnrichmentExecutionService
):
    def __init__(
        self,
        *,
        router,
        findings_per_call: list[int],
    ) -> None:
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
        self.findings_per_call = list(
            findings_per_call
        )
        self.requests = []

    def _resolve_runtime_connector_name(
        self,
        capability,
    ) -> str | None:
        return capability.display_name

    def _execute_connector(
        self,
        *,
        runtime_name,
        capability,
        request,
    ) -> OsintResult:
        self.requests.append(request)

        count = (
            self.findings_per_call.pop(0)
            if self.findings_per_call
            else 0
        )

        return OsintResult(
            connector=runtime_name,
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="subdomain",
                    value=f"host-{index}.example.com",
                )
                for index in range(count)
            ],
        )


def capability(
    name: str,
    goal: DiscoveryGoal,
):
    return SimpleNamespace(
        display_name=name,
        module=f"test.{name}",
        connector_class=f"{name}Connector",
        goals=frozenset({goal}),
    )


def test_traversal_state_exposes_remaining_budgets() -> None:
    limits = PivotPolicyLimits(
        max_depth=3,
        max_pivots_per_entity=8,
        max_new_entities=50,
    )
    state = PivotTraversalState(
        new_entities_count=47,
        pivots_by_entity={
            "entity-1": 6,
        },
    )

    assert (
        state.remaining_new_entities(
            limits
        )
        == 3
    )

    assert (
        state.remaining_pivots(
            entity_identity="entity-1",
            limits=limits,
        )
        == 2
    )


def test_new_entity_budget_tracks_hard_remaining_count() -> None:
    budget = NewEntityBudget(
        limit=3,
    )

    budget.consume(2)

    assert budget.remaining == 1
    assert budget.exhausted is False

    budget.consume(1)

    assert budget.remaining == 0
    assert budget.exhausted is True

    with pytest.raises(ValueError):
        budget.consume(1)


def test_execution_boundary_trims_legacy_connector_to_remaining_budget() -> None:
    goal = DiscoveryGoal.DOMAIN_DISCOVERY
    limits = PivotPolicyLimits(
        max_depth=3,
        max_pivots_per_entity=8,
        max_new_entities=5,
    )

    router = FakeRouter(
        limits=limits,
        goals=(goal,),
        connectors=(
            capability("first", goal),
            capability("second", goal),
        ),
    )

    service = RecordingExecutionService(
        router=router,
        findings_per_call=[
            10,
            10,
        ],
    )

    state = PivotTraversalState(
        new_entities_count=2,
    )

    result = service.execute(
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
        goal=goal,
        depth=0,
        entity_identity="root",
        state=state,
    )

    assert [
        request.limit
        for request in service.requests
    ] == [3]

    assert result.total_findings == 3
    assert result.entity_budget is not None
    assert result.entity_budget.limit == 3

    assert (
        result.records[0]
        .result
        .metadata[
            "execution_boundary_trimmed_findings"
        ]
        == 7
    )


def test_execute_defaults_shares_one_budget_across_goals() -> None:
    goals = (
        DiscoveryGoal.DOMAIN_DISCOVERY,
        DiscoveryGoal.HISTORICAL_WEB,
    )

    limits = PivotPolicyLimits(
        max_depth=3,
        max_pivots_per_entity=8,
        max_new_entities=4,
    )

    router = FakeRouter(
        limits=limits,
        goals=goals,
        connectors=(
            capability(
                "discovery",
                DiscoveryGoal.DOMAIN_DISCOVERY,
            ),
        ),
    )

    service = RecordingExecutionService(
        router=router,
        findings_per_call=[
            2,
            2,
        ],
    )

    results = service.execute_defaults(
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
        depth=0,
        entity_identity="root",
        state=PivotTraversalState(),
    )

    assert len(results) == 2

    assert [
        request.limit
        for request in service.requests
    ] == [
        4,
        2,
    ]

    assert (
        results[0].entity_budget
        is results[1].entity_budget
    )

    assert sum(
        result.total_findings
        for result in results
    ) == 4


def build_persistence_service():
    normalizer = SimpleNamespace(
        normalize=lambda entity_type, value: (
            value.strip().casefold()
        ),
    )

    repository = SimpleNamespace(
        find_in_case=lambda **kwargs: None,
    )

    entity_service = SimpleNamespace(
        normalizer=normalizer,
        repository=repository,
    )

    link_service = SimpleNamespace(
        ensure_link=lambda **kwargs: (
            None,
            True,
        ),
    )

    return OsintFindingPersistenceService(
        source_service=SimpleNamespace(),
        evidence_service=SimpleNamespace(),
        entity_service=entity_service,
        evidence_link_service=link_service,
    )


def test_persistence_does_not_create_entity_after_budget_is_exhausted(
    monkeypatch,
) -> None:
    service = build_persistence_service()

    source = SimpleNamespace(
        id=uuid4(),
    )
    evidence = SimpleNamespace(
        id=uuid4(),
    )

    monkeypatch.setattr(
        service,
        "_ensure_source",
        lambda **kwargs: (
            source,
            False,
        ),
    )

    monkeypatch.setattr(
        service,
        "_ensure_evidence",
        lambda **kwargs: (
            evidence,
            False,
        ),
    )

    created = []

    def resolve_or_create(**kwargs):
        entity = SimpleNamespace(
            id=uuid4(),
            confidence=kwargs["confidence"],
            entity_type=kwargs["entity_type"],
        )
        created.append(entity)
        return entity, True

    monkeypatch.setattr(
        service,
        "_resolve_or_create_entity",
        resolve_or_create,
    )

    budget = NewEntityBudget(
        limit=1,
    )

    persisted = service._persist_finding(
        case_id=uuid4(),
        target_type=OsintTargetType.DOMAIN,
        target_value="example.com",
        goal=DiscoveryGoal.HISTORICAL_WEB,
        connector="test",
        capability_module="test.connector",
        finding=OsintFinding(
            category="account",
            value="example-account",
            url="https://example.com/profile",
        ),
        finding_index=0,
        parent_entity_id=None,
        new_entity_budget=budget,
    )

    # "account" + URL normally exposes two Entity candidates.
    # The hard recursive budget allows only one genuinely new Entity.
    assert persisted.entities_created == 1
    assert len(persisted.entities) == 1
    assert len(created) == 1
    assert budget.remaining == 0


def test_exhausted_budget_still_links_existing_entity(
    monkeypatch,
) -> None:
    service = build_persistence_service()

    source = SimpleNamespace(
        id=uuid4(),
    )
    evidence = SimpleNamespace(
        id=uuid4(),
    )
    existing = SimpleNamespace(
        id=uuid4(),
        confidence=1.0,
        entity_type=EntityType.DOMAIN,
    )

    monkeypatch.setattr(
        service,
        "_ensure_source",
        lambda **kwargs: (
            source,
            False,
        ),
    )
    monkeypatch.setattr(
        service,
        "_ensure_evidence",
        lambda **kwargs: (
            evidence,
            False,
        ),
    )
    monkeypatch.setattr(
        service,
        "_find_existing_entity",
        lambda **kwargs: existing,
    )

    def must_not_create(**kwargs):
        raise AssertionError(
            "resolve/create must not run when budget is exhausted"
        )

    monkeypatch.setattr(
        service,
        "_resolve_or_create_entity",
        must_not_create,
    )

    budget = NewEntityBudget(
        limit=0,
    )

    persisted = service._persist_finding(
        case_id=uuid4(),
        target_type=OsintTargetType.DOMAIN,
        target_value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        connector="test",
        capability_module="test.connector",
        finding=OsintFinding(
            category="subdomain",
            value="www.example.com",
        ),
        finding_index=0,
        parent_entity_id=None,
        new_entity_budget=budget,
    )

    assert persisted.entities == (
        existing,
    )
    assert persisted.entities_created == 0
    assert budget.remaining == 0

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.application.osint_enrichment_service import OsintEnrichmentService
from app.osint.capabilities import DiscoveryGoal
from app.osint.enrichment_execution import (
    EnrichmentExecutionResult,
    EnrichmentExecutionStatus,
)
from app.osint.finding_persistence import OsintPersistenceResult
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import (
    PivotDecision,
    PivotDecisionCode,
    PivotTraversalState,
)
from app.osint.pivot_router import PivotRoute


def route(goal):
    return PivotRoute(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=goal,
        depth=0,
        decision=PivotDecision(
            allowed=True,
            code=PivotDecisionCode.ALLOWED,
            reason="test",
        ),
        connectors=(),
    )


class ExecutionStub:
    def __init__(self, results):
        self.results = tuple(results)
        self.calls = []

    def execute_defaults(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


class PersistenceStub:
    def __init__(self, by_goal=None):
        self.by_goal = by_goal or {}
        self.calls = []

    def persist_execution(self, **kwargs):
        self.calls.append(kwargs)
        goal = kwargs["goal"]
        config = self.by_goal.get(goal, {})
        return OsintPersistenceResult(
            case_id=kwargs["case_id"],
            target_type=kwargs["target_type"],
            target_value=kwargs["target_value"],
            goal=goal,
            persisted=[],
            **config,
        )


def make_execution(goal, status):
    return EnrichmentExecutionResult(
        route=route(goal),
        status=status,
        records=[],
    )


def test_one_application_call_executes_default_policy_routes():
    execution = ExecutionStub([
        make_execution(
            DiscoveryGoal.ACCOUNT_DISCOVERY,
            EnrichmentExecutionStatus.SUCCESS,
        )
    ])
    persistence = PersistenceStub()

    service = OsintEnrichmentService(
        execution_service=execution,
        persistence_service=persistence,
    )
    case_id = uuid4()

    result = service.enrich_target(
        case_id=case_id,
        target_type=OsintTargetType.USERNAME,
        value="example_user",
    )

    assert result.goals_attempted == 1
    assert len(execution.calls) == 1
    assert execution.calls[0]["target_type"] is OsintTargetType.USERNAME
    assert execution.calls[0]["case_id"] == str(case_id)


def test_success_execution_is_persisted():
    execution = ExecutionStub([
        make_execution(
            DiscoveryGoal.ACCOUNT_DISCOVERY,
            EnrichmentExecutionStatus.SUCCESS,
        )
    ])
    persistence = PersistenceStub()

    service = OsintEnrichmentService(
        execution_service=execution,
        persistence_service=persistence,
    )
    service.enrich_target(
        case_id=uuid4(),
        target_type=OsintTargetType.USERNAME,
        value="example_user",
    )

    assert len(persistence.calls) == 1
    assert (
        persistence.calls[0]["goal"]
        is DiscoveryGoal.ACCOUNT_DISCOVERY
    )


def test_partial_execution_is_persisted_to_keep_usable_findings():
    execution = ExecutionStub([
        make_execution(
            DiscoveryGoal.ACCOUNT_DISCOVERY,
            EnrichmentExecutionStatus.PARTIAL,
        )
    ])
    persistence = PersistenceStub()

    service = OsintEnrichmentService(
        execution_service=execution,
        persistence_service=persistence,
    )
    service.enrich_target(
        case_id=uuid4(),
        target_type=OsintTargetType.USERNAME,
        value="example_user",
    )

    assert len(persistence.calls) == 1


def test_failed_and_skipped_goal_are_not_sent_to_persistence():
    execution = ExecutionStub([
        make_execution(
            DiscoveryGoal.ACCOUNT_DISCOVERY,
            EnrichmentExecutionStatus.FAILED,
        ),
        make_execution(
            DiscoveryGoal.EMAIL_REGISTRATION,
            EnrichmentExecutionStatus.SKIPPED,
        ),
    ])
    persistence = PersistenceStub()

    service = OsintEnrichmentService(
        execution_service=execution,
        persistence_service=persistence,
    )
    result = service.enrich_target(
        case_id=uuid4(),
        target_type=OsintTargetType.USERNAME,
        value="example_user",
    )

    assert persistence.calls == []
    assert result.failed_goals == 1
    assert result.skipped_goals == 1


def test_parent_entity_id_is_used_as_stable_entity_identity():
    execution = ExecutionStub([
        make_execution(
            DiscoveryGoal.ACCOUNT_DISCOVERY,
            EnrichmentExecutionStatus.SUCCESS,
        )
    ])
    persistence = PersistenceStub()
    parent_id = uuid4()

    service = OsintEnrichmentService(
        execution_service=execution,
        persistence_service=persistence,
    )
    service.enrich_target(
        case_id=uuid4(),
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        parent_entity_id=parent_id,
    )

    assert (
        execution.calls[0]["entity_identity"]
        == f"entity:{parent_id}"
    )
    assert (
        persistence.calls[0]["parent_entity_id"]
        == parent_id
    )


def test_existing_traversal_state_is_reused_not_replaced():
    execution = ExecutionStub([
        make_execution(
            DiscoveryGoal.ACCOUNT_DISCOVERY,
            EnrichmentExecutionStatus.SUCCESS,
        )
    ])
    persistence = PersistenceStub()
    state = PivotTraversalState()

    service = OsintEnrichmentService(
        execution_service=execution,
        persistence_service=persistence,
    )
    result = service.enrich_target(
        case_id=uuid4(),
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        state=state,
    )

    assert result.state is state
    assert execution.calls[0]["state"] is state


def test_persisted_new_entities_increment_future_recursion_budget():
    execution = ExecutionStub([
        make_execution(
            DiscoveryGoal.ACCOUNT_DISCOVERY,
            EnrichmentExecutionStatus.SUCCESS,
        )
    ])

    class CountingPersistenceStub:
        def __init__(self):
            self.calls = []

        def persist_execution(self, **kwargs):
            self.calls.append(kwargs)
            result = SimpleNamespace(
                persisted_findings=1,
                sources_created=1,
                evidences_created=1,
                entities_created=3,
                links_created=3,
            )
            return result

    persistence = CountingPersistenceStub()
    state = PivotTraversalState()

    service = OsintEnrichmentService(
        execution_service=execution,
        persistence_service=persistence,
    )
    service.enrich_target(
        case_id=uuid4(),
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        state=state,
    )

    assert state.new_entities_count == 3


def test_service_does_not_commit_or_recurse_by_itself():
    assert not hasattr(OsintEnrichmentService, "commit")
    assert not hasattr(OsintEnrichmentService, "enrich_recursively")


def test_execution_options_are_forwarded_to_boundary():
    execution = ExecutionStub([
        make_execution(
            DiscoveryGoal.PHONE_ENRICHMENT,
            EnrichmentExecutionStatus.SUCCESS,
        )
    ])
    persistence = PersistenceStub()

    service = OsintEnrichmentService(
        execution_service=execution,
        persistence_service=persistence,
    )
    service.enrich_target(
        case_id=uuid4(),
        target_type=OsintTargetType.PHONE,
        value="+380671234567",
        timeout=55,
        use_cache=False,
        save_raw_output=True,
        include_metadata=False,
        include_related=False,
    )

    call = execution.calls[0]
    assert call["timeout"] == 55
    assert call["use_cache"] is False
    assert call["save_raw_output"] is True
    assert call["include_metadata"] is False
    assert call["include_related"] is False

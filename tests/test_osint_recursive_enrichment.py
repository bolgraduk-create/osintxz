from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.application.osint_recursive_enrichment_service import (
    OsintRecursiveEnrichmentService,
    RecursiveEnrichmentSeed,
    RecursiveExpansionStopReason,
)
from app.models.entity import EntityType
from app.osint.models import OsintTargetType
from app.osint.pivot_candidates import OsintPivotCandidatePolicy
from app.osint.pivot_policy import (
    PivotPolicyLimits,
    PivotTraversalState,
)


def entity(entity_type, value):
    return SimpleNamespace(
        id=uuid4(),
        entity_type=entity_type,
        value=value,
        normalized_value=value,
    )


def persisted_finding(*entities):
    return SimpleNamespace(
        evidence=SimpleNamespace(id=uuid4()),
        entities=tuple(entities),
    )


def persistence(*findings):
    return SimpleNamespace(
        persisted=list(findings),
    )


def enrichment_result(
    *,
    parent_entity_id=None,
    persisted=(),
    created=0,
):
    return SimpleNamespace(
        parent_entity_id=parent_entity_id,
        persistence=list(persisted),
        persisted_findings=sum(
            len(item.persisted)
            for item in persisted
        ),
        sources_created=0,
        evidences_created=0,
        entities_created=created,
    )


class EnrichmentServiceStub:
    def __init__(self, responses, limits=None):
        self.responses = list(responses)
        self.calls = []
        self.execution_service = SimpleNamespace(
            router=SimpleNamespace(
                policy=SimpleNamespace(
                    limits=(
                        limits
                        or PivotPolicyLimits()
                    )
                )
            )
        )

    def enrich_target(self, **kwargs):
        self.calls.append(kwargs)
        if self.responses:
            response = self.responses.pop(0)
        else:
            response = enrichment_result(
                parent_entity_id=(
                    kwargs.get("parent_entity_id")
                )
            )

        response.parent_entity_id = (
            kwargs.get("parent_entity_id")
        )
        return response


def test_candidate_policy_allows_only_strong_recursive_entity_types():
    policy = OsintPivotCandidatePolicy()

    allowed = {
        EntityType.USERNAME: OsintTargetType.USERNAME,
        EntityType.EMAIL: OsintTargetType.EMAIL,
        EntityType.PHONE: OsintTargetType.PHONE,
        EntityType.DOMAIN: OsintTargetType.DOMAIN,
        EntityType.URL: OsintTargetType.URL,
        EntityType.IP: OsintTargetType.IP,
    }

    for entity_type, target_type in allowed.items():
        assert (
            policy.target_type_for_entity(
                entity_type
            )
            is target_type
        )

    for blocked in (
        EntityType.ACCOUNT,
        EntityType.PERSON,
        EntityType.ORGANIZATION,
        EntityType.LOCATION,
        EntityType.ADDRESS,
        EntityType.DOCUMENT,
        EntityType.OTHER,
    ):
        assert (
            policy.target_type_for_entity(
                blocked
            )
            is None
        )


def test_raw_account_entity_is_not_automatically_pivoted():
    policy = OsintPivotCandidatePolicy()
    account = entity(
        EntityType.ACCOUNT,
        "example_user",
    )

    candidate = policy.from_entity(
        account,
        depth=1,
    )

    assert candidate is None


def test_persisted_url_becomes_recursive_url_candidate():
    policy = OsintPivotCandidatePolicy()
    url = entity(
        EntityType.URL,
        "https://example.com/profile",
    )
    root = enrichment_result(
        persisted=(
            persistence(
                persisted_finding(url)
            ),
        )
    )

    candidates = policy.from_enrichment_result(
        root,
        next_depth=1,
    )

    assert len(candidates) == 1
    assert (
        candidates[0].target_type
        is OsintTargetType.URL
    )
    assert candidates[0].entity_id == url.id
    assert candidates[0].depth == 1


def test_recursive_service_processes_root_then_discovered_pivot_bfs():
    discovered = entity(
        EntityType.DOMAIN,
        "example.com",
    )

    root_response = enrichment_result(
        persisted=(
            persistence(
                persisted_finding(discovered)
            ),
        )
    )
    child_response = enrichment_result()

    stub = EnrichmentServiceStub(
        [root_response, child_response]
    )
    service = OsintRecursiveEnrichmentService(
        enrichment_service=stub
    )

    result = service.enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                target_type=OsintTargetType.USERNAME,
                value="example_user",
            ),
        ),
    )

    assert result.targets_processed == 2
    assert len(stub.calls) == 2
    assert (
        stub.calls[0]["target_type"]
        is OsintTargetType.USERNAME
    )
    assert stub.calls[0]["depth"] == 0
    assert (
        stub.calls[1]["target_type"]
        is OsintTargetType.DOMAIN
    )
    assert stub.calls[1]["value"] == "example.com"
    assert stub.calls[1]["depth"] == 1
    assert (
        stub.calls[1]["parent_entity_id"]
        == discovered.id
    )


def test_unsupported_entities_do_not_enter_recursive_queue():
    account = entity(
        EntityType.ACCOUNT,
        "example_user",
    )
    person = entity(
        EntityType.PERSON,
        "Example Person",
    )

    root = enrichment_result(
        persisted=(
            persistence(
                persisted_finding(
                    account,
                    person,
                )
            ),
        )
    )

    stub = EnrichmentServiceStub([root])
    result = OsintRecursiveEnrichmentService(
        enrichment_service=stub
    ).enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                OsintTargetType.USERNAME,
                "example_user",
            ),
        ),
    )

    assert result.targets_processed == 1
    assert result.candidates_enqueued == 0


def test_duplicate_discovered_entity_is_enqueued_once():
    url = entity(
        EntityType.URL,
        "https://example.com/a",
    )

    root = enrichment_result(
        persisted=(
            persistence(
                persisted_finding(url),
                persisted_finding(url),
            ),
        )
    )

    stub = EnrichmentServiceStub(
        [root, enrichment_result()]
    )
    result = OsintRecursiveEnrichmentService(
        enrichment_service=stub
    ).enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                OsintTargetType.USERNAME,
                "example_user",
            ),
        ),
    )

    assert result.targets_processed == 2
    assert result.candidates_enqueued == 1


def test_duplicate_root_seed_is_scheduled_once():
    stub = EnrichmentServiceStub(
        [enrichment_result()]
    )
    service = OsintRecursiveEnrichmentService(
        enrichment_service=stub
    )

    result = service.enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                OsintTargetType.EMAIL,
                "User@Example.com",
            ),
            RecursiveEnrichmentSeed(
                OsintTargetType.EMAIL,
                "user@example.com",
            ),
        ),
    )

    assert result.targets_processed == 1
    assert result.candidates_deduplicated == 1


def test_max_depth_prevents_child_execution_beyond_limit():
    domain = entity(
        EntityType.DOMAIN,
        "example.com",
    )
    url = entity(
        EntityType.URL,
        "https://example.com/page",
    )

    root = enrichment_result(
        persisted=(
            persistence(
                persisted_finding(domain)
            ),
        )
    )
    child = enrichment_result(
        persisted=(
            persistence(
                persisted_finding(url)
            ),
        )
    )

    stub = EnrichmentServiceStub(
        [root, child],
        limits=PivotPolicyLimits(
            max_depth=1,
        ),
    )

    result = OsintRecursiveEnrichmentService(
        enrichment_service=stub
    ).enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                OsintTargetType.USERNAME,
                "example_user",
            ),
        ),
    )

    assert result.targets_processed == 2
    assert result.stop_reason is (
        RecursiveExpansionStopReason
        .MAX_DEPTH_REACHED
    )


def test_existing_traversal_state_is_reused_across_all_levels():
    domain = entity(
        EntityType.DOMAIN,
        "example.com",
    )
    root = enrichment_result(
        persisted=(
            persistence(
                persisted_finding(domain)
            ),
        )
    )

    stub = EnrichmentServiceStub(
        [root, enrichment_result()]
    )
    state = PivotTraversalState()

    result = OsintRecursiveEnrichmentService(
        enrichment_service=stub
    ).enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                OsintTargetType.USERNAME,
                "example_user",
            ),
        ),
        state=state,
    )

    assert result.state is state
    assert all(
        call["state"] is state
        for call in stub.calls
    )


def test_new_entity_budget_stops_future_recursive_processing():
    domain = entity(
        EntityType.DOMAIN,
        "example.com",
    )
    root = enrichment_result(
        persisted=(
            persistence(
                persisted_finding(domain)
            ),
        )
    )

    class BudgetStub(EnrichmentServiceStub):
        def enrich_target(self, **kwargs):
            response = super().enrich_target(
                **kwargs
            )
            kwargs["state"].add_new_entities(1)
            return response

    stub = BudgetStub(
        [root],
        limits=PivotPolicyLimits(
            max_new_entities=1,
        ),
    )

    result = OsintRecursiveEnrichmentService(
        enrichment_service=stub
    ).enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                OsintTargetType.USERNAME,
                "example_user",
            ),
        ),
    )

    assert result.targets_processed == 1
    assert result.stop_reason is (
        RecursiveExpansionStopReason
        .NEW_ENTITY_BUDGET_REACHED
    )


def test_execution_options_are_forwarded_to_every_recursive_run():
    domain = entity(
        EntityType.DOMAIN,
        "example.com",
    )
    root = enrichment_result(
        persisted=(
            persistence(
                persisted_finding(domain)
            ),
        )
    )
    stub = EnrichmentServiceStub(
        [root, enrichment_result()]
    )

    OsintRecursiveEnrichmentService(
        enrichment_service=stub
    ).enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                OsintTargetType.USERNAME,
                "example_user",
            ),
        ),
        timeout=44,
        use_cache=False,
        save_raw_output=True,
        include_metadata=False,
        include_related=False,
    )

    for call in stub.calls:
        assert call["timeout"] == 44
        assert call["use_cache"] is False
        assert call["save_raw_output"] is True
        assert (
            call["include_metadata"]
            is False
        )
        assert (
            call["include_related"]
            is False
        )


def test_recursive_service_does_not_commit_transaction():
    assert not hasattr(
        OsintRecursiveEnrichmentService,
        "commit",
    )
    assert not hasattr(
        OsintRecursiveEnrichmentService,
        "rollback",
    )

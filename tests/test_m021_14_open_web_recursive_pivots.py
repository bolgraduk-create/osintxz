from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.application.open_web_recursive_pivot_service import OpenWebRecursivePivotService
from app.application.osint_recursive_enrichment_service import RecursiveEnrichmentResult
from app.models.entity import EntityType
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.pivot_candidates import OsintPivotCandidatePolicy
from app.osint.pivot_policy import PivotTraversalState


def entity(entity_type, value):
    return SimpleNamespace(
        id=uuid4(),
        entity_type=entity_type,
        normalized_value=value,
        value=value,
    )


def persisted_finding(entities):
    return SimpleNamespace(
        evidence=SimpleNamespace(id=uuid4()),
        entities=list(entities),
    )


def persistence(entities):
    return SimpleNamespace(persisted=[persisted_finding(entities)])


def open_web_result(entities, *, depth=2):
    return SimpleNamespace(
        query=OpenWebQuery(
            OsintTargetType.URL,
            "https://seed.example/",
            depth=depth,
            parent_entity_id=uuid4(),
        ),
        persistence=[persistence(entities)],
    )


class RecursiveStub:
    def __init__(self):
        self.calls = []

    def enrich(self, **kwargs):
        self.calls.append(kwargs)
        return RecursiveEnrichmentResult(
            case_id=kwargs["case_id"],
            state=kwargs.get("state") or PivotTraversalState(),
        )


def test_only_persisted_supported_entities_become_seeds():
    email = entity(EntityType.EMAIL, "alice@example.org")
    url = entity(EntityType.URL, "https://example.org/")
    person = entity(EntityType.PERSON, "Alice")
    organization = entity(EntityType.ORGANIZATION, "Example Org")

    recursive = RecursiveStub()
    result = OpenWebRecursivePivotService(
        recursive_service=recursive
    ).expand(
        case_id=uuid4(),
        open_web_result=open_web_result(
            [email, url, person, organization]
        ),
    )

    assert {c.target_type for c in result.candidates} == {
        OsintTargetType.EMAIL,
        OsintTargetType.URL,
    }
    assert len(recursive.calls) == 1
    assert {s.target_type for s in recursive.calls[0]["seeds"]} == {
        OsintTargetType.EMAIL,
        OsintTargetType.URL,
    }


def test_open_web_depth_is_carried_into_existing_recursion():
    recursive = RecursiveStub()
    OpenWebRecursivePivotService(
        recursive_service=recursive
    ).expand(
        case_id=uuid4(),
        open_web_result=open_web_result(
            [entity(EntityType.DOMAIN, "example.org")],
            depth=2,
        ),
    )
    assert recursive.calls[0]["seed_depth"] == 3


def test_parent_entity_is_persisted_candidate_entity():
    recursive = RecursiveStub()
    email = entity(EntityType.EMAIL, "alice@example.org")

    OpenWebRecursivePivotService(
        recursive_service=recursive
    ).expand(
        case_id=uuid4(),
        open_web_result=open_web_result([email]),
    )

    assert recursive.calls[0]["seeds"][0].parent_entity_id == email.id


def test_duplicate_persisted_entity_candidate_is_collapsed():
    duplicate = entity(EntityType.URL, "https://example.org/")
    result_obj = open_web_result([])
    result_obj.persistence = [
        SimpleNamespace(
            persisted=[
                persisted_finding([duplicate]),
                persisted_finding([duplicate]),
            ]
        )
    ]

    recursive = RecursiveStub()
    result = OpenWebRecursivePivotService(
        recursive_service=recursive
    ).expand(
        case_id=uuid4(),
        open_web_result=result_obj,
    )

    assert len(result.candidates) == 1
    assert len(recursive.calls[0]["seeds"]) == 1


def test_no_supported_candidate_means_no_recursive_execution():
    recursive = RecursiveStub()
    result = OpenWebRecursivePivotService(
        recursive_service=recursive
    ).expand(
        case_id=uuid4(),
        open_web_result=open_web_result(
            [entity(EntityType.PERSON, "Alice")]
        ),
    )

    assert result.candidates == ()
    assert result.recursion is None
    assert recursive.calls == []


def test_generic_policy_reads_persisted_entities_only():
    policy = OsintPivotCandidatePolicy()
    candidates = policy.from_persistence_results(
        [persistence([entity(EntityType.PHONE, "+380501234567")])],
        next_depth=4,
        discovered_from_entity_id=None,
    )

    assert len(candidates) == 1
    assert candidates[0].depth == 4

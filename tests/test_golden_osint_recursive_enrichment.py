from __future__ import annotations

import json

from app.models.entity import EntityType
from tests.golden_osint_recursive_runtime import (
    build_runtime,
    load_expected,
    run_once,
    snapshot,
)


FORBIDDEN_AUTOMATIC_CONNECTORS = {
    "Nmap",
    "GHunt",
    "Nuclei",
    "Naabu",
    "FFUF",
    "Feroxbuster",
}


def test_recursive_osint_golden_fixture_matches_expected_snapshot():
    runtime = build_runtime()
    result = run_once(runtime)

    assert snapshot(runtime, result) == load_expected()


def test_recursive_osint_golden_fixture_never_executes_forbidden_tools():
    runtime = build_runtime()
    run_once(runtime)

    assert not (
        FORBIDDEN_AUTOMATIC_CONNECTORS
        & set(runtime.executed_connectors)
    )


def test_recursive_osint_golden_fixture_preserves_provenance_on_every_evidence():
    runtime = build_runtime()
    run_once(runtime)

    assert runtime.evidence_service.repository.items

    for evidence in runtime.evidence_service.repository.items:
        metadata = json.loads(evidence.metadata_json)
        assert metadata["workflow"] == "osint_enrichment"
        assert metadata["connector"]
        assert metadata["capability_module"]
        assert metadata["origin"]["target_type"]
        assert metadata["origin"]["target_value"]
        assert metadata["origin"]["goal"]
        assert metadata["evidence_key"]


def test_recursive_osint_golden_fixture_blocks_account_from_recursive_execution():
    runtime = build_runtime()
    result = run_once(runtime)

    account_entities = [
        item
        for item in runtime.entity_service.repository.items
        if item.entity_type is EntityType.ACCOUNT
    ]
    # A username match yields a profile URL, not an independently confirmed account identity.
    assert not account_entities

    # Root USERNAME plus recursive URL/DOMAIN/URL runs are expected.
    # No run may use ACCOUNT as an OSINT target type because no such target
    # type is produced by the recursive candidate policy.
    assert all(
        run.target_type.value != "account"
        for run in result.runs
    )


def test_recursive_osint_golden_fixture_full_rerun_is_persistence_idempotent():
    runtime = build_runtime()

    first = run_once(runtime)

    counts_after_first = (
        len(runtime.source_service.repository.items),
        len(runtime.evidence_service.repository.items),
        len(runtime.entity_service.repository.items),
        len(runtime.evidence_link_service.links),
    )

    # A new recursive run gets a new traversal state, as a real later user
    # action would. Persistence must still remain duplicate-safe.
    second = run_once(runtime)

    counts_after_second = (
        len(runtime.source_service.repository.items),
        len(runtime.evidence_service.repository.items),
        len(runtime.entity_service.repository.items),
        len(runtime.evidence_link_service.links),
    )

    assert counts_after_second == counts_after_first
    assert second.sources_created == 0
    assert second.evidences_created == 0
    assert second.entities_created == 0


def test_recursive_osint_golden_fixture_depth_limit_is_observable():
    runtime = build_runtime()
    result = run_once(runtime)

    assert max(run.depth for run in result.runs) == 2
    assert all(run.depth <= 2 for run in result.runs)

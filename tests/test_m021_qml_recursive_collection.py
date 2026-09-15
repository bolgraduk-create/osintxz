from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.interface.desktop.workers.osint_collection_worker import (
    OsintCollectionWorker,
)
from app.osint.models import OsintTargetType


def _enum(value: str):
    return SimpleNamespace(value=value)


def test_qml_worker_uses_bounded_recursive_enrichment_boundary() -> None:
    source = Path(
        "app/interface/desktop/workers/osint_collection_worker.py"
    ).read_text(encoding="utf-8")

    assert "osint_recursive_enrichment_service.enrich(" in source
    assert "RecursiveEnrichmentSeed(" in source
    assert "progress_callback=self._emit_progress" in source
    assert "max_targets=self.RECURSIVE_MAX_TARGETS" in source
    assert "time_budget_seconds=self.RECURSIVE_TIME_BUDGET_SECONDS" in source
    assert "investigation_target_enrichment_service.enrich(" not in source


def test_recursive_snapshot_preserves_target_depth_and_aggregate_counts() -> None:
    evidence_id = uuid4()
    entity_id = uuid4()

    finding = SimpleNamespace(
        category="username",
        value="alice",
        confidence=0.9,
        source="fixture",
        url="https://example.test/alice",
        reliability=0.8,
        metadata={},
    )
    result = SimpleNamespace(
        connector="FixtureConnector",
        status=_enum("success"),
        error=None,
        execution_time=0.25,
        findings=[finding],
    )
    record = SimpleNamespace(
        result=result,
        capability=SimpleNamespace(
            display_name="Fixture Connector",
            module="fixture_connector",
        ),
        runtime_connector_name="FixtureConnector",
    )
    execution = SimpleNamespace(
        route=SimpleNamespace(goal=_enum("account_discovery")),
        status=_enum("success"),
        error=None,
        records=[record],
    )
    evidence = SimpleNamespace(
        id=evidence_id,
        title="Fixture evidence",
        value="alice",
        evidence_type=_enum("username"),
    )
    entity = SimpleNamespace(
        id=entity_id,
        value="alice",
        normalized_value="alice",
        entity_type=_enum("username"),
        confidence=0.9,
    )
    persisted = SimpleNamespace(
        evidence=evidence,
        entities=[entity],
    )
    persistence = SimpleNamespace(persisted=[persisted])
    run = SimpleNamespace(
        target_type=OsintTargetType.USERNAME,
        target_value="alice",
        parent_entity_id=entity_id,
        depth=1,
        executions=[execution],
        persistence=[persistence],
        persisted_findings=1,
        sources_created=1,
        evidences_created=1,
        entities_created=1,
        links_created=1,
    )
    recursive = SimpleNamespace(
        runs=[run],
        state=SimpleNamespace(new_entities_count=1),
        stop_reason=_enum("queue_exhausted"),
        candidates_discovered=1,
        candidates_enqueued=1,
        candidates_deduplicated=0,
        candidates_unsupported=0,
        persisted_findings=1,
        sources_created=1,
        evidences_created=1,
        entities_created=1,
    )

    snapshot = OsintCollectionWorker._snapshot_recursive_enrichment(recursive)

    assert snapshot["recursion"]["targetsProcessed"] == 1
    assert snapshot["recursion"]["candidatesDiscovered"] == 1
    assert snapshot["recursion"]["candidatesEnqueued"] == 1
    assert snapshot["recursion"]["stopReason"] == "queue_exhausted"
    assert snapshot["counts"]["persistedFindings"] == 1
    assert snapshot["counts"]["linksCreated"] == 1

    first_run = snapshot["runs"][0]
    assert first_run["targetType"] == "username"
    assert first_run["targetValue"] == "alice"
    assert first_run["depth"] == 1
    assert first_run["executions"][0]["records"][0]["findings"][0]["value"] == "alice"
    assert first_run["persistences"][0]["persisted"][0]["entities"][0]["normalizedValue"] == "alice"


def test_qml_result_center_exposes_recursive_progress_and_stop_reason() -> None:
    bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")
    qml = Path(
        "app/interface/desktop/qml/pages/Osint.qml"
    ).read_text(encoding="utf-8")

    assert "worker.progress.connect(self._on_osint_worker_progress)" in bridge
    assert '"targetsProcessed"' in bridge
    assert '"candidatesDiscovered"' in bridge
    assert '"stopReason"' in bridge

    assert 'label: "TARGETS PROCESSED"' in qml
    assert 'label: "PIVOTS DISCOVERED"' in qml
    assert 'label: "PIVOTS QUEUED"' in qml
    assert 'label: "CURRENT PIVOT"' in qml
    assert 'label: "STOP REASON"' in qml

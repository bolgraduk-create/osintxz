from __future__ import annotations

from pathlib import Path


def test_service_container_contains_m021_4_singletons():
    source = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert "self.osint_enrichment_execution_service" in source
    assert "self.osint_finding_persistence_service" in source
    assert "self.osint_enrichment_service" in source


def test_service_container_reuses_existing_osint_manager_and_pipeline():
    source = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert source.count("OsintManager()") == 1
    assert source.count("OsintPipeline(") == 1
    assert (
        "OsintEnrichmentExecutionService(\n"
        "                pipeline=(\n"
        "                    self.osint_pipeline"
    ) in source


def test_manual_osint_workspace_still_uses_shared_pipeline():
    source = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert "self.osint_workspace_service = (" in source
    assert "OsintWorkspaceService(" in source
    assert "self.osint_pipeline" in source


def test_new_enrichment_service_uses_existing_domain_services():
    source = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    for token in (
        "source_service=(",
        "self.source_service",
        "evidence_service=(",
        "self.evidence_service",
        "entity_service=(",
        "self.entity_service",
        "evidence_link_service=(",
        "self.evidence_link_service",
    ):
        assert token in source

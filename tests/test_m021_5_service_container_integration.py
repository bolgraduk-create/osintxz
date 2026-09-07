from __future__ import annotations

from pathlib import Path


def test_service_container_has_recursive_enrichment_singleton():
    source = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert (
        "self.osint_recursive_enrichment_service"
        in source
    )
    assert (
        "OsintRecursiveEnrichmentService("
        in source
    )


def test_recursive_service_wraps_existing_m021_4_service():
    source = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert (
        "OsintRecursiveEnrichmentService(\n"
        "                enrichment_service=(\n"
        "                    self.osint_enrichment_service"
    ) in source


def test_m021_5_does_not_create_second_osint_runtime():
    source = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert source.count("OsintManager()") == 1
    assert source.count("OsintPipeline(") == 1

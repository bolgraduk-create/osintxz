from __future__ import annotations

from pathlib import Path


SERVICE_CONTAINER = Path(
    "app/core/service_container.py"
)


def source() -> str:
    return SERVICE_CONTAINER.read_text(
        encoding="utf-8"
    )


def test_service_container_has_one_open_web_registry():
    text = source()
    assert (
        text.count(
            "self.open_web_provider_registry ="
        )
        == 1
    )


def test_service_container_has_one_open_web_discovery_service():
    text = source()
    assert (
        text.count(
            "self.open_web_discovery_service ="
        )
        == 1
    )


def test_service_container_has_one_open_web_extraction_bridge():
    text = source()
    assert (
        text.count(
            "self.open_web_identifier_extraction_bridge ="
        )
        == 1
    )


def test_service_container_has_one_open_web_enrichment_service():
    text = source()
    assert (
        text.count(
            "self.open_web_enrichment_service ="
        )
        == 1
    )


def test_open_web_bridge_reuses_existing_unified_extraction_singleton():
    text = source()
    anchor = (
        "self.open_web_identifier_extraction_bridge ="
    )
    start = text.index(anchor)
    block = text[start:start + 800]

    assert (
        "self.unified_extraction_service"
        in block
    )
    assert (
        "UnifiedExtractionService("
        not in block
    )


def test_open_web_enrichment_reuses_existing_persistence_singleton():
    text = source()
    anchor = (
        "self.open_web_enrichment_service ="
    )
    start = text.index(anchor)
    block = text[start:start + 1200]

    assert (
        "self.osint_finding_persistence_service"
        in block
    )
    assert (
        "OsintFindingPersistenceService("
        not in block
    )


def test_m021_10_does_not_create_second_osint_runtime():
    text = source()

    assert text.count(
        "self.osint_manager ="
    ) == 1

    assert text.count(
        "self.osint_pipeline ="
    ) == 1

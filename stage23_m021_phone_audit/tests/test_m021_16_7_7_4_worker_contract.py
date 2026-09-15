from pathlib import Path


WORKER = Path(
    "app/interface/desktop/workers/"
    "investigation_search_worker.py"
)


def _compact() -> str:
    return "".join(
        WORKER.read_text(encoding="utf-8").split()
    )


def test_unified_marker_present():
    assert (
        "M021.16.7.7.4unifiedspecialized+Open-Webflow"
        in _compact()
    )


def test_specialized_and_open_web_calls_present():
    text = _compact()

    assert (
        "self.container.osint_enrichment_service."
        "enrich_target("
        in text
    )
    assert (
        "self.container.open_web_enrichment_service."
        "enrich("
        in text
    )


def test_payload_contains_both_results():
    text = _compact()

    assert '"osint":osint_result' in text
    assert '"open_web":open_web_result' in text

from pathlib import Path


WORKER = Path(
    "app/interface/desktop/workers/"
    "investigation_search_worker.py"
)


def _compact() -> str:
    return "".join(
        WORKER.read_text(encoding="utf-8").split()
    )


def test_specialized_osint_is_called():
    text = _compact()

    assert (
        "self.container.osint_enrichment_service."
        "enrich_target("
        in text
    )


def test_open_web_is_still_called():
    text = _compact()

    assert (
        "self.container.open_web_enrichment_service."
        "enrich("
        in text
    )


def test_result_contains_both_paths():
    text = _compact()

    assert '"osint":osint_result' in text
    assert '"open_web":open_web_result' in text


def test_unified_marker_present():
    assert (
        "target_type=target_type"
        in _compact()
    )

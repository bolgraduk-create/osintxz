from pathlib import Path


def test_service_container_registers_gdelt_email_provider():
    text = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert (
        "M021.16.5.2A GDELT exact-email Open-Web registration"
        in text
    )
    assert "GdeltExactEmailOpenWebProvider" in text


def test_email_worker_runs_open_web_and_osint():
    text = Path(
        "app/interface/desktop/workers/investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    assert "osint_enrichment_service.enrich_target" in text
    assert "open_web_enrichment_service.enrich" in text
    assert '"open_web": open_web_result' in text


def test_ui_combines_email_sources():
    text = Path(
        "app/interface/desktop/views/workspace/investigation_search_view.py"
    ).read_text(encoding="utf-8")

    assert (
        "M021.16.5.2A combined EMAIL OSINT/Open-Web presentation"
        in text
    )
    assert "def _fill_email_open_web_sources" in text

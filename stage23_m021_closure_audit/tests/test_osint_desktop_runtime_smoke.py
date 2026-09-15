from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import sys

import pytest
from PySide6.QtWidgets import QApplication

from app.interface.desktop.views.workspace.investigation_search_view import InvestigationSearchView
from app.interface.desktop.workers.investigation_search_worker import InvestigationSearchWorker
from app.osint.models import OsintTargetType


@pytest.fixture(scope="module")
def qt_app():
    application = QApplication.instance() or QApplication(["osint-runtime-smoke", "-platform", "offscreen"])
    yield application


@pytest.mark.parametrize("raw, kind", [
    ("@example_user", OsintTargetType.USERNAME),
    ("public@example.org", OsintTargetType.EMAIL),
    ("+380632874404", OsintTargetType.PHONE),
    ("example.org", OsintTargetType.DOMAIN),
    ("https://example.org/", OsintTargetType.URL),
    ("8.8.8.8", OsintTargetType.IP),
])
def test_real_qt_view_and_worker_send_unified_request(qt_app, raw, kind):
    calls, results, errors, searches = [], [], [], []
    osint_result, web_result = object(), object()

    def specialized(**kwargs):
        calls.append(("osint", kwargs["target_type"]))
        return osint_result

    def open_web(query, **kwargs):
        calls.append(("open_web", query.target_type))
        return web_result

    view = InvestigationSearchView()
    try:
        view.search_requested.connect(lambda *args: searches.append(args))
        view.target_input.setText(raw)
        view.search_button.click()
        qt_app.processEvents()
        assert searches == [(raw, False)]
        assert kind.value.upper() in view.detected_type_label.text().upper()
        worker = InvestigationSearchWorker(
            container=SimpleNamespace(
                osint_enrichment_service=SimpleNamespace(enrich_target=specialized),
                open_web_enrichment_service=SimpleNamespace(enrich=open_web),
            ), case_id=uuid4(), raw_target=raw, recursive=False,
        )
        worker.result_ready.connect(results.append)
        worker.failed.connect(errors.append)
        worker.run()
        assert not errors
        assert calls == [("osint", kind), ("open_web", kind)]
        assert results[0]["osint"] is osint_result
        assert results[0]["open_web"] is web_result
    finally:
        view.close()


def test_syntax_check_for_changed_production_sources():
    root = Path(__file__).resolve().parents[1]
    for relative in [
        "app/interface/desktop/workers/investigation_search_worker.py",
        "app/osint/capabilities.py", "app/osint/pivot_router.py",
        "app/osint/finding_persistence.py", "app/osint/phone_intelligence.py",
        "app/osint/connectors/local_phone_connector.py",
        "app/osint/open_web/public_document_fetcher.py",
        "app/infrastructure/open_web/common_crawl_warc_client.py",
    ]:
        path = root / relative
        compile(path.read_bytes(), str(path), "exec")
    assert Path(sys.executable).resolve() == root / ".venv" / "Scripts" / "python.exe"

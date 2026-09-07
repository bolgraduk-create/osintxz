import httpx
import pytest
from PySide6.QtWidgets import QApplication

from app.application.registry_intelligence_service import RegistryIntelligenceService
from app.infrastructure.registries.gleif_client import GleifRegistryHttpClient
from app.interface.desktop.views.workspace.investigation_search_view import InvestigationSearchView
from app.interface.desktop.workers.investigation_search_worker import InvestigationSearchWorker
from app.registry_intelligence.contracts import RegistryDomain, RegistryQuery, RegistryQueryKind, RegistryResultStatus
from app.registry_intelligence.providers.gleif import GleifRegistryProvider
from app.registry_intelligence.query_detection import detect_registry_query
from app.registry_intelligence.registry import RegistryProviderRegistry
from tests.test_m022_registry_foundation import FakeClient
from tests.test_registry_persistence_integration import runtime
from types import SimpleNamespace


@pytest.mark.parametrize("raw, kind", [
    ("506700GE1G29325QX363", RegistryQueryKind.LEI),
    ("lei:506700ge1g29325qx363", RegistryQueryKind.LEI),
    ("GLOBAL LEGAL ENTITY IDENTIFIER FOUNDATION", RegistryQueryKind.NAME),
    ("company:GLEIF", RegistryQueryKind.NAME),
    ("reg:CH:CHE-200.595.965", RegistryQueryKind.REGISTRATION_ID),
])
def test_registry_detection_preserves_separate_domain(raw, kind):
    query = detect_registry_query(raw)
    assert query.kind is kind and query.domain is RegistryDomain.BUSINESS


@pytest.mark.parametrize("raw", ["8.8.8.8", "::1", "alice", "+380 63 287 44 04", "a@example.org", "https://example.org/"])
def test_osint_inputs_are_not_reinterpreted_as_registries(raw):
    assert detect_registry_query(raw) is None


def test_real_registry_worker_persistence_and_view(runtime):
    session, case_id, persistence = runtime
    app = QApplication.instance() or QApplication(["registry-smoke", "-platform", "offscreen"])
    registry = RegistryProviderRegistry()
    registry.register(GleifRegistryProvider(client=FakeClient()))
    service = RegistryIntelligenceService(registry, persistence_service=persistence)
    worker = InvestigationSearchWorker(container=SimpleNamespace(registry_intelligence_service=service),
        case_id=case_id, raw_target="506700GE1G29325QX363", recursive=False)
    results, errors = [], []
    worker.result_ready.connect(results.append)
    worker.failed.connect(errors.append)
    worker.run()
    assert not errors and len(results) == 1
    session.commit()  # Same transaction ownership as the existing page controller.
    view = InvestigationSearchView()
    try:
        view.target_input.setText(worker.raw_target)
        assert "lei" in view.detected_type_label.text()
        view.show_result(results[0])
        app.processEvents()
        assert view.entities_table.rowCount() == 2
        assert view.sources_table.item(0, 0).text() == "gleif"
        assert view.sources_table.item(0, 1).text() == "success"
        names = [view.entities_table.item(row, 1).text() for row in range(2)]
        assert "GLOBAL LEGAL ENTITY IDENTIFIER FOUNDATION" in names
        assert not any("registry:" in name for name in names)
        repeat = service.enrich(detect_registry_query(worker.raw_target), case_id=case_id)
        assert repeat.persistence.entities_created == repeat.persistence.evidences_created == 0
    finally:
        view.close()


def test_gleif_registration_fulltext_candidate_requires_exact_identifier():
    provider = GleifRegistryProvider(client=FakeClient())
    wrong = provider.search(RegistryQuery(RegistryDomain.BUSINESS, RegistryQueryKind.REGISTRATION_ID, "wrong"))
    assert wrong.status is RegistryResultStatus.SUCCESS and wrong.records == []
    exact = provider.search(RegistryQuery(RegistryDomain.BUSINESS, RegistryQueryKind.REGISTRATION_ID, "CHE-200.595.965"))
    assert len(exact.records) == 1


def test_registration_authority_id_is_not_company_registration_number():
    row = FakeClient().row()
    row["attributes"]["entity"].pop("registeredAs")
    row["attributes"]["entity"]["registeredAt"] = {"id": "RA000000"}
    assert GleifRegistryProvider(client=FakeClient())._to_record(row).registration_id is None


@pytest.mark.parametrize("status, expected", [(429, RegistryResultStatus.PARTIAL), (404, RegistryResultStatus.SUCCESS), (503, RegistryResultStatus.FAILED)])
def test_gleif_http_statuses(status, expected):
    client = GleifRegistryHttpClient(transport=httpx.MockTransport(lambda request: httpx.Response(status)))
    result = GleifRegistryProvider(client=client).search(detect_registry_query("506700GE1G29325QX363"))
    assert result.status is expected
    if status == 429:
        assert result.metadata == {"rate_limited": True, "retryable": True}


def test_gleif_json_download_is_bounded():
    client = GleifRegistryHttpClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"x" * 4_000_001)))
    with pytest.raises(ValueError, match="download limit"):
        client.get_record("506700GE1G29325QX363")

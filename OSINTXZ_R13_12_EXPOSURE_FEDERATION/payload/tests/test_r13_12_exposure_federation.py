from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import httpx

from app.breach_intelligence.contracts import (
    BreachFinding,
    BreachQueryKind,
    BreachResultStatus,
    BreachSearchResult,
)
from app.darkweb_intelligence.contracts import (
    DarkWebFetchResult,
    DarkWebFetchStatus,
    DarkWebIndicator,
    DarkWebIndicatorKind,
    DarkWebPageObservation,
)
from app.exposure_intelligence.persistence import ExposurePersistenceService
from app.exposure_intelligence.service import ExposureFederationService
from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.hibp_breach import HibpBreachAdapter
from app.intelligence_sources.adapters.intelligencex import (
    IntelligenceXMetadataAdapter,
    IntelligenceXSearchClient,
)
from app.intelligence_sources.adapters.registry import RemoteSourceAdapterRegistry
from app.intelligence_sources.adapters.service import RemoteSourceAdapterService
from app.intelligence_sources.adapters.tor_public import TorPublicOnionAdapter
from app.intelligence_sources.builtin_sources import register_massive_remote_sources
from app.intelligence_sources.catalog import IntelligenceSourceCatalog
from app.intelligence_sources.coverage import SourceImplementationStatus
from app.models.evidence import EvidenceType
from app.models.source import SourceType


class _StaticAdapter(RemoteSourceAdapter):
    def __init__(
        self,
        code: str,
        capabilities: set[str],
        records: list[RemoteSourceRecord],
        *,
        automatic: bool = True,
    ) -> None:
        self._code = code
        self._capabilities = frozenset(capabilities)
        self._records = records
        self._automatic = automatic
        self.calls = 0

    @property
    def source_code(self) -> str:
        return self._code

    @property
    def capabilities(self) -> frozenset[str]:
        return self._capabilities

    @property
    def automatic_enabled(self) -> bool:
        return self._automatic

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        self.calls += 1
        return RemoteAdapterResult(
            source=self.source_code,
            status=RemoteAdapterStatus.SUCCESS,
            records=list(self._records),
        )


def test_registry_blocks_nonautomatic_adapter_until_explicitly_selected():
    automatic = _StaticAdapter("auto", {"email"}, [], automatic=True)
    gated = _StaticAdapter("gated", {"email"}, [], automatic=False)
    registry = RemoteSourceAdapterRegistry()
    registry.register(automatic)
    registry.register(gated)
    service = RemoteSourceAdapterService(registry=registry)

    service.search(RemoteSourceQuery(capability="email", value="a@example.com"))
    assert automatic.calls == 1
    assert gated.calls == 0

    service.search(
        RemoteSourceQuery(
            capability="email",
            value="a@example.com",
            sources=("gated",),
        )
    )
    assert gated.calls == 1


def test_remote_service_redacts_secret_fields_and_records_redaction_count():
    record = RemoteSourceRecord(
        source="auto",
        record_id="1",
        record_type="test",
        display_name="test",
        attributes={"password": "never-store-this", "password_exposed": True},
    )
    registry = RemoteSourceAdapterRegistry()
    registry.register(_StaticAdapter("auto", {"email"}, [record]))
    result = RemoteSourceAdapterService(registry=registry).search(
        RemoteSourceQuery(capability="email", value="a@example.com")
    )
    assert result.records[0].attributes["password"] == "[REDACTED]"
    provider = result.provider_results[0]
    assert provider.metadata["secret_fields_redacted"] >= 1
    assert provider.metadata["raw_secret_values_stored"] is False


def test_intelligencex_client_polls_metadata_only_and_never_uses_file_endpoints():
    requests: list[httpx.Request] = []
    polls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal polls
        requests.append(request)
        if request.url.path == "/intelligent/search":
            assert request.method == "POST"
            body = json.loads(request.content.decode("utf-8"))
            assert body["term"] == "person@example.com"
            assert body["maxresults"] == 2
            assert request.headers["x-key"] == "key"
            return httpx.Response(200, json={"id": "search-id"}, request=request)
        if request.url.path == "/intelligent/search/result":
            polls += 1
            assert request.url.params["previewlines"] == "0"
            row = {
                "systemid": f"system-{polls}",
                "storageid": f"storage-{polls}",
                "bucket": "darknet.tor" if polls == 1 else "pastes",
                "bucketh": "Tor Darknet" if polls == 1 else "Pastes",
                "size": 120,
                "media": 24,
                "mediah": "Text file",
                "type": 1,
                "typeh": "Text",
                # These are intentionally ignored by the adapter mapping.
                "name": "password=hunter2",
                "description": "token=secret-value",
            }
            return httpx.Response(
                200,
                json={"records": [row], "status": 0 if polls == 1 else 1},
                request=request,
            )
        raise AssertionError(f"Unexpected IntelX endpoint: {request.url.path}")

    client = IntelligenceXSearchClient(
        api_key="key",
        base_url="https://2.intelx.io",
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda _: None,
        poll_interval=0,
        max_polls=3,
    )
    adapter = IntelligenceXMetadataAdapter(client=client)
    result = adapter.search(
        RemoteSourceQuery(capability="email", value="person@example.com", limit=2)
    )

    assert result.status is RemoteAdapterStatus.SUCCESS
    assert len(result.records) == 2
    assert result.records[0].record_type == "darkweb_index_hit"
    assert result.records[1].record_type == "intelx_index_hit"
    assert result.metadata["raw_content_fetched"] is False
    assert result.metadata["preview_fetched"] is False
    assert result.records[0].attributes["raw_secret_values_stored"] is False
    serialized = json.dumps([record.attributes for record in result.records])
    assert "hunter2" not in serialized
    assert "secret-value" not in serialized
    assert all(not request.url.path.startswith("/file/") for request in requests)


def test_hibp_adapter_preserves_exposure_fact_without_secret_value():
    class FakeBreachService:
        hibp_client = SimpleNamespace(account_lookup_configured=True)

        def search_email(self, email: str, *, timeout: int):
            return BreachSearchResult(
                source="hibp",
                kind=BreachQueryKind.EMAIL,
                status=BreachResultStatus.SUCCESS,
                findings=[
                    BreachFinding(
                        source="hibp",
                        record_id="ExampleLeak",
                        subject_type="email",
                        subject_value=email,
                        breach_name="ExampleLeak",
                        breach_title="Example Leak",
                        exposed_data_classes=("Email addresses", "Passwords"),
                        password_exposed=True,
                    )
                ],
            )

    adapter = HibpBreachAdapter(service=FakeBreachService())
    result = adapter.search(
        RemoteSourceQuery(capability="email", value="person@example.com")
    )
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].attributes["password_exposed"] is True
    assert result.records[0].attributes["raw_secret_values_stored"] is False
    assert "password" not in result.records[0].attributes


def test_tor_adapter_maps_only_safe_public_observation():
    onion = "a" * 56 + ".onion"

    class FakeDarkWebService:
        def fetch_public_onion(self, url: str, *, timeout: int):
            return DarkWebFetchResult(
                status=DarkWebFetchStatus.SUCCESS,
                observation=DarkWebPageObservation(
                    source_url=url,
                    status_code=200,
                    title="Public notice",
                    content_sha256="a" * 64,
                    indicators=[
                        DarkWebIndicator(
                            DarkWebIndicatorKind.EMAIL,
                            "person@example.com",
                            0.95,
                        )
                    ],
                    metadata={
                        "raw_body_stored": False,
                        "page_text_stored": False,
                        "secret_material_stored": False,
                    },
                ),
            )

    adapter = TorPublicOnionAdapter(service=FakeDarkWebService())
    result = adapter.search(
        RemoteSourceQuery(
            capability="onion_url",
            value=f"http://{onion}/",
        )
    )
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].record_type == "darkweb_public_observation"
    assert result.records[0].attributes["raw_body_stored"] is False
    assert result.records[0].attributes["page_text_stored"] is False
    assert result.records[0].attributes["raw_secret_values_stored"] is False


def test_exposure_service_routes_email_to_explicit_gated_sources_and_summarizes():
    breach = RemoteSourceRecord(
        source="hibp_breached_account",
        record_id="breach-1",
        record_type="breach",
        display_name="Breach",
        attributes={"password_exposed": True, "raw_secret_values_stored": False},
    )
    dark = RemoteSourceRecord(
        source="intelligencex_search",
        record_id="intelx-1",
        record_type="darkweb_index_hit",
        display_name="IntelX metadata hit",
        attributes={"raw_secret_values_stored": False},
    )
    registry = RemoteSourceAdapterRegistry()
    hibp = _StaticAdapter("hibp_breached_account", {"email"}, [breach], automatic=False)
    intelx = _StaticAdapter("intelligencex_search", {"email"}, [dark], automatic=False)
    registry.register(hibp)
    registry.register(intelx)
    exposure = ExposureFederationService(
        remote_service=RemoteSourceAdapterService(registry=registry)
    )

    result = exposure.search_email("person@example.com")
    assert hibp.calls == 1
    assert intelx.calls == 1
    assert result.summary.total_records == 2
    assert result.summary.breach_records == 1
    assert result.summary.darkweb_records == 1
    assert result.summary.indexed_leak_records == 1
    assert result.summary.password_exposed is True
    assert result.summary.raw_secret_values_stored is False


def test_catalog_marks_intelx_active_metadata_only():
    catalog = IntelligenceSourceCatalog()
    coverage = register_massive_remote_sources(catalog)
    source = catalog.get("intelligencex_search")
    assert source is not None
    assert source.requires_credentials is True
    assert source.default_enabled is False
    assert source.raw_secret_storage_allowed is False
    entry = coverage.get("intelligencex_search")
    assert entry is not None
    assert entry.status is SourceImplementationStatus.ACTIVE


class _SourceRepo:
    def __init__(self):
        self.items = []

    def get_by_case(self, case_id):
        return list(self.items)


class _EvidenceRepo:
    def __init__(self):
        self.items = []

    def get_by_source(self, source_id):
        return [item for item in self.items if item.source_id == source_id]


class _SourceService:
    def __init__(self):
        self.repository = _SourceRepo()

    def create_source(self, *, case_id, name, source_type, path, description):
        item = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            name=name,
            source_type=source_type,
            original_path=path,
            description=description,
            is_deleted=False,
        )
        self.repository.items.append(item)
        return item


class _EvidenceService:
    def __init__(self):
        self.repository = _EvidenceRepo()

    def create_evidence(self, **kwargs):
        item = SimpleNamespace(
            id=uuid4(),
            source_id=kwargs["source_id"],
            evidence_type=kwargs["evidence_type"],
            title=kwargs["title"],
            value=kwargs.get("value"),
            description=kwargs.get("description"),
            metadata_json=kwargs.get("metadata_json"),
            is_deleted=False,
        )
        self.repository.items.append(item)
        return item


def test_exposure_persistence_redacts_secret_value_and_deduplicates_snapshot():
    unsafe_record = RemoteSourceRecord(
        source="intelligencex_search",
        record_id="x-1",
        record_type="intelx_index_hit",
        display_name="Metadata hit",
        attributes={
            "password": "raw-secret-never-persist",
            "password_exposed": True,
            "raw_secret_values_stored": False,
        },
    )
    provider = RemoteAdapterResult(
        source="intelligencex_search",
        status=RemoteAdapterStatus.SUCCESS,
        records=[unsafe_record],
    )
    federated = SimpleNamespace(
        provider_results=[provider],
        records=[unsafe_record],
    )
    exposure_result = SimpleNamespace(
        capability="email",
        value="person@example.com",
        federated_result=federated,
        summary=SimpleNamespace(
            total_records=1,
            breach_records=0,
            darkweb_records=0,
            indexed_leak_records=1,
            password_exposed=True,
            secret_material_present=True,
            raw_secret_values_stored=False,
            provider_statuses={"intelligencex_search": RemoteAdapterStatus.SUCCESS},
        ),
    )
    # dataclasses.asdict is used by the real result; use an actual-compatible
    # summary dataclass through the real service for persistence test.
    from app.exposure_intelligence.contracts import ExposureSearchResult, ExposureSummary
    exposure_result = ExposureSearchResult(
        capability="email",
        value="person@example.com",
        federated_result=federated,
        summary=ExposureSummary(
            total_records=1,
            indexed_leak_records=1,
            password_exposed=True,
            secret_material_present=True,
            raw_secret_values_stored=False,
            provider_statuses={"intelligencex_search": RemoteAdapterStatus.SUCCESS},
        ),
    )

    sources = _SourceService()
    evidence = _EvidenceService()
    persistence = ExposurePersistenceService(
        source_service=sources,
        evidence_service=evidence,
    )
    case_id = uuid4()
    first = persistence.persist(case_id=case_id, result=exposure_result)
    second = persistence.persist(case_id=case_id, result=exposure_result)

    assert first.records_persisted == 1
    assert first.evidences_created == 1
    assert second.records_persisted == 0
    assert second.records_skipped == 1
    assert len(evidence.repository.items) == 1
    item = evidence.repository.items[0]
    assert item.evidence_type is EvidenceType.METADATA
    assert sources.repository.items[0].source_type is SourceType.API
    assert "raw-secret-never-persist" not in item.metadata_json
    assert "[REDACTED]" in item.metadata_json
    metadata = json.loads(item.metadata_json)
    assert metadata["raw_secret_values_stored"] is False
    assert metadata["person_identity_confirmed"] is False
    assert metadata["ownership_inferred"] is False

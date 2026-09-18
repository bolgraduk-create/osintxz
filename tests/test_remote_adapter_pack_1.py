from __future__ import annotations

import httpx

from app.intelligence_sources.adapters.ares import CzechAresAdapter
from app.intelligence_sources.adapters.brreg import NorwayBrregAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterStatus,
    RemoteSourceQuery,
)
from app.intelligence_sources.adapters.crossref import CrossrefAdapter
from app.intelligence_sources.adapters.openalex import OpenAlexAdapter
from app.intelligence_sources.adapters.registry import RemoteSourceAdapterRegistry
from app.intelligence_sources.adapters.ror import RorAdapter
from app.intelligence_sources.adapters.service import RemoteSourceAdapterService


def test_brreg_name_search_maps_company():
    def handler(request):
        return httpx.Response(200, json={
            "_embedded": {"enheter": [{
                "organisasjonsnummer": "923609016",
                "navn": "EXAMPLE AS",
                "organisasjonsform": {"kode": "AS", "beskrivelse": "Aksjeselskap"},
                "antallAnsatte": 10,
            }]}
        }, request=request)
    adapter = NorwayBrregAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    result = adapter.search(RemoteSourceQuery("company_name", "Example", country="NO"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].record_id == "923609016"


def test_brreg_exact_org_number():
    def handler(request):
        assert request.url.path.endswith("/923609016")
        return httpx.Response(200, json={
            "organisasjonsnummer": "923609016", "navn": "EXAMPLE AS"
        }, request=request)
    adapter = NorwayBrregAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    result = adapter.search(RemoteSourceQuery("registration_id", "923609016", country="NO"))
    assert result.records[0].display_name == "EXAMPLE AS"


def test_ares_exact_ico():
    def handler(request):
        assert request.url.path.endswith("/ekonomicke-subjekty/12345678")
        return httpx.Response(200, json={
            "ico": "12345678",
            "obchodniJmeno": "EXAMPLE S.R.O.",
            "pravniForma": "112",
        }, request=request)
    adapter = CzechAresAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    result = adapter.search(RemoteSourceQuery("registration_id", "12345678", country="CZ"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].identifiers["ICO"] == "12345678"


def test_ares_name_is_explicitly_not_supported_in_pack_1():
    adapter = CzechAresAdapter()
    result = adapter.search(RemoteSourceQuery("company_name", "Example", country="CZ"))
    assert result.status is RemoteAdapterStatus.NOT_SUPPORTED


def test_crossref_search_maps_doi():
    def handler(request):
        assert request.url.params["query.bibliographic"] == "graph theory"
        return httpx.Response(200, json={
            "message": {"items": [{
                "DOI": "10.1234/example",
                "title": ["Graph Theory"],
                "URL": "https://doi.org/10.1234/example",
                "author": [{"given": "Ada", "family": "Example"}],
            }]}
        }, request=request)
    adapter = CrossrefAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    result = adapter.search(RemoteSourceQuery("work", "graph theory"))
    assert result.records[0].identifiers["DOI"] == "10.1234/example"


def test_ror_name_search():
    def handler(request):
        assert request.url.params["query"] == "Harvard"
        return httpx.Response(200, json={
            "items": [{
                "id": "https://ror.org/03vek6s52",
                "names": [{"value": "Harvard University", "types": ["ror_display"]}],
                "status": "active",
                "locations": [{"geonames_details": {"country_code": "US"}}],
            }]
        }, request=request)
    adapter = RorAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    result = adapter.search(RemoteSourceQuery("organization", "Harvard"))
    assert result.records[0].country == "US"


def test_openalex_without_key_not_configured():
    registry = RemoteSourceAdapterRegistry()
    registry.register(OpenAlexAdapter(api_key=None))
    service = RemoteSourceAdapterService(registry=registry)
    result = service.search(RemoteSourceQuery("work", "graphene", sources=("openalex",)))
    assert result.provider_results[0].status is RemoteAdapterStatus.NOT_CONFIGURED


def test_openalex_with_key_search():
    def handler(request):
        assert request.url.params["api_key"] == "free-key"
        assert request.url.path == "/works"
        return httpx.Response(200, json={
            "results": [{
                "id": "https://openalex.org/W1",
                "display_name": "Example Work",
                "doi": "https://doi.org/10.1/x",
            }]
        }, request=request)
    adapter = OpenAlexAdapter(
        api_key="free-key",
        client=JsonHttpClient(transport=httpx.MockTransport(handler)),
    )
    result = adapter.search(RemoteSourceQuery("work", "Example"))
    assert result.records[0].record_id == "https://openalex.org/W1"


def test_federated_service_isolates_and_combines_sources():
    def crossref_handler(request):
        return httpx.Response(200, json={
            "message": {"items": [{
                "DOI": "10.1/a",
                "title": ["A"],
            }]}
        }, request=request)

    registry = RemoteSourceAdapterRegistry()
    registry.register(CrossrefAdapter(client=JsonHttpClient(transport=httpx.MockTransport(crossref_handler))))
    registry.register(RorAdapter(client=JsonHttpClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(500, request=request)
    ))))
    service = RemoteSourceAdapterService(registry=registry)

    result = service.search(RemoteSourceQuery("name", "A"))
    assert any(r.source == "crossref" for r in result.records)
    assert len(result.provider_results) == 2
    assert any(r.source == "ror" and r.status in {RemoteAdapterStatus.PARTIAL, RemoteAdapterStatus.FAILED} for r in result.provider_results)

from __future__ import annotations

import httpx

from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterStatus,
    RemoteSourceQuery,
)
from app.intelligence_sources.adapters.fec import OpenFecAdapter
from app.intelligence_sources.adapters.icij_offshore import IcijOffshoreLeaksAdapter
from app.intelligence_sources.adapters.nppes_npi import NppesNpiAdapter
from app.intelligence_sources.adapters.nvd_cve import NvdCveAdapter
from app.intelligence_sources.adapters.openfda import OpenFdaAdapter
from app.intelligence_sources.adapters.orcid_public import OrcidPublicAdapter
from app.intelligence_sources.adapters.wikidata_search import WikidataEntitySearchAdapter


def test_wikidata_search_maps_candidates():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "www.wikidata.org"
        assert request.url.params["action"] == "wbsearchentities"
        return httpx.Response(200, json={
            "search": [{
                "id": "Q42",
                "label": "Douglas Adams",
                "description": "English writer",
                "concepturi": "https://www.wikidata.org/entity/Q42",
                "aliases": ["Douglas Noël Adams"],
                "match": {"type": "label", "language": "en", "text": "Douglas Adams"},
            }]
        }, request=request)

    adapter = WikidataEntitySearchAdapter(transport=httpx.MockTransport(handler))
    result = adapter.search(RemoteSourceQuery(capability="person", value="Douglas Adams"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].identifiers["WIKIDATA_ID"] == "Q42"
    assert result.records[0].attributes["candidate_only"] is True


def test_wikidata_exact_qid_not_candidate_only():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["action"] == "wbgetentities"
        return httpx.Response(200, json={
            "entities": {
                "Q42": {
                    "labels": {"en": {"value": "Douglas Adams"}},
                    "descriptions": {"en": {"value": "English writer"}},
                    "aliases": {"en": [{"value": "DNA"}]},
                }
            }
        }, request=request)

    adapter = WikidataEntitySearchAdapter(transport=httpx.MockTransport(handler))
    result = adapter.search(RemoteSourceQuery(capability="wikidata_id", value="Q42"))
    assert result.records[0].attributes["candidate_only"] is False
    assert result.records[0].display_name == "Douglas Adams"


def test_orcid_anonymous_expanded_search():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "pub.orcid.org"
        assert request.url.path.endswith("/expanded-search/")
        return httpx.Response(200, json={
            "expanded-result": [{
                "orcid-id": "0000-0002-1825-0097",
                "given-names": "Josiah",
                "family-names": "Carberry",
                "institution-name": ["Brown University"],
            }]
        }, request=request)

    adapter = OrcidPublicAdapter(transport=httpx.MockTransport(handler))
    result = adapter.search(RemoteSourceQuery(capability="person", value="Josiah Carberry"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].identifiers["ORCID"] == "0000-0002-1825-0097"
    assert result.records[0].attributes["candidate_only"] is True


def test_nvd_exact_cve_uses_cve_id_parameter():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["cveId"] == "CVE-2026-12345"
        return httpx.Response(200, json={
            "totalResults": 1,
            "vulnerabilities": [{
                "cve": {
                    "id": "CVE-2026-12345",
                    "vulnStatus": "Analyzed",
                    "published": "2026-01-01T00:00:00.000",
                    "lastModified": "2026-01-02T00:00:00.000",
                    "descriptions": [{"lang": "en", "value": "Example flaw"}],
                    "metrics": {
                        "cvssMetricV31": [{
                            "source": "nvd@nist.gov",
                            "cvssData": {
                                "version": "3.1",
                                "baseScore": 7.5,
                                "baseSeverity": "HIGH",
                                "vectorString": "CVSS:3.1/AV:N",
                            },
                        }]
                    },
                    "weaknesses": [{"description": [{"lang": "en", "value": "CWE-79"}]}],
                    "references": [{"url": "https://example.test/advisory"}],
                }
            }],
        }, request=request)

    adapter = NvdCveAdapter(transport=httpx.MockTransport(handler))
    result = adapter.search(RemoteSourceQuery(capability="cve", value="CVE-2026-12345"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].attributes["cvss"]["base_score"] == 7.5
    assert result.records[0].identifiers["CVE"] == "CVE-2026-12345"


def test_nvd_optional_api_key_is_header_only():
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen["apiKey"] = request.headers.get("apiKey")
        return httpx.Response(200, json={"totalResults": 0, "vulnerabilities": []}, request=request)

    adapter = NvdCveAdapter(api_key="free-key", transport=httpx.MockTransport(handler))
    result = adapter.search(RemoteSourceQuery(capability="keyword", value="openssl"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert seen["apiKey"] == "free-key"


def test_openfda_works_without_key_and_combines_public_datasets():
    calls = []
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert "api_key" not in request.url.params
        if request.url.path.endswith("/drug/label.json"):
            return httpx.Response(200, json={"results": [{
                "id": "drug-1",
                "openfda": {
                    "brand_name": ["ExampleDrug"],
                    "manufacturer_name": ["Example Labs"],
                    "product_ndc": ["12345-678"],
                },
            }]}, request=request)
        return httpx.Response(200, json={"results": [{
            "public_device_record_key": "dev-1",
            "brand_name": "ExampleDevice",
            "company_name": "Example Labs",
        }]}, request=request)

    adapter = OpenFdaAdapter(transport=httpx.MockTransport(handler))
    result = adapter.search(RemoteSourceQuery(capability="manufacturer", value="Example Labs", limit=10))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert len(result.records) == 2
    assert result.metadata["api_key_optional"] is True
    assert len(calls) == 2


def test_openfda_404_for_one_dataset_is_empty_not_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/drug/label.json"):
            return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}}, request=request)
        return httpx.Response(200, json={"results": [{
            "public_device_record_key": "dev-2",
            "brand_name": "OnlyDevice",
        }]}, request=request)

    result = OpenFdaAdapter(transport=httpx.MockTransport(handler)).search(
        RemoteSourceQuery(capability="manufacturer", value="Only Device")
    )
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert len(result.records) == 1


def test_fec_defaults_to_demo_key_and_excludes_street_addresses():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_key"] == "DEMO_KEY"
        return httpx.Response(200, json={"results": [{
            "sub_id": "123",
            "contributor_name": "Public Donor",
            "contribution_receipt_amount": 50,
            "contribution_receipt_date": "2026-01-01",
            "contributor_street_1": "DO NOT RETAIN",
            "contributor_city": "Washington",
            "contributor_state": "DC",
            "committee_id": "C00000001",
        }]}, request=request)

    adapter = OpenFecAdapter(transport=httpx.MockTransport(handler))
    result = adapter.search(RemoteSourceQuery(capability="contributor", value="Public Donor", country="US"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    attrs = result.records[0].attributes
    assert attrs["street_address_fields_retained"] is False
    assert "contributor_street_1" not in attrs


def test_fec_candidate_search_maps_candidate():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{
            "candidate_id": "P00000001",
            "name": "Example Candidate",
            "office_full": "President",
            "party_full": "Example",
            "state": "US",
        }]}, request=request)

    result = OpenFecAdapter(transport=httpx.MockTransport(handler)).search(
        RemoteSourceQuery(capability="candidate", value="Example", country="US")
    )
    assert result.records[0].identifiers["FEC_CANDIDATE_ID"] == "P00000001"
    assert result.records[0].attributes["candidate_only"] is True


def test_icij_reconciliation_results_are_candidates_only():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = request.read().decode()
        assert '"type":"Officer"' in body.replace(" ", "")
        return httpx.Response(200, json={"result": [{
            "id": "12345",
            "name": "Example Person",
            "score": 91.2,
            "match": True,
            "type": [{"id": "officer", "name": "Officer"}],
        }]}, request=request)

    adapter = IcijOffshoreLeaksAdapter(transport=httpx.MockTransport(handler))
    result = adapter.search(RemoteSourceQuery(capability="person", value="Example Person"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].attributes["candidate_only"] is True
    assert result.records[0].attributes["identity_inference_prohibited"] is True


def test_nppes_exact_npi_maps_public_provider_record():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["version"] == "2.1"
        assert request.url.params["number"] == "1234567890"
        return httpx.Response(200, json={
            "result_count": 1,
            "results": [{
                "number": "1234567890",
                "enumeration_type": "NPI-1",
                "basic": {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "credential": "MD",
                    "status": "A",
                },
                "addresses": [{
                    "address_purpose": "LOCATION",
                    "city": "Boston",
                    "state": "MA",
                    "postal_code": "02110",
                }],
                "taxonomies": [{
                    "code": "207Q00000X",
                    "desc": "Family Medicine",
                    "primary": True,
                }],
            }],
        }, request=request)

    adapter = NppesNpiAdapter(transport=httpx.MockTransport(handler))
    result = adapter.search(RemoteSourceQuery(capability="npi", value="1234567890", country="US"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].attributes["candidate_only"] is False
    assert result.records[0].identifiers["NPI"] == "1234567890"


def test_nppes_name_search_queries_person_and_organization_and_deduplicates():
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={
            "result_count": 1,
            "results": [{
                "number": "1234567890",
                "enumeration_type": "NPI-2" if "organization_name" in request.url.params else "NPI-1",
                "basic": {
                    "organization_name": "Example Health" if "organization_name" in request.url.params else None,
                    "first_name": "Example",
                    "last_name": "Health",
                },
            }],
        }, request=request)

    result = NppesNpiAdapter(transport=httpx.MockTransport(handler)).search(
        RemoteSourceQuery(capability="name", value="Example Health", country="US")
    )
    assert calls == 2
    assert len(result.records) == 1
    assert result.records[0].attributes["candidate_only"] is True


def test_country_scoping_blocks_us_only_adapters_for_other_country():
    fec = OpenFecAdapter()
    npi = NppesNpiAdapter()
    q = RemoteSourceQuery(capability="name", value="Example", country="UA")
    assert fec.supports(q) is False
    assert npi.supports(q) is False


def test_all_pack_sources_expose_nonempty_capabilities():
    adapters = [
        WikidataEntitySearchAdapter(),
        OrcidPublicAdapter(),
        NvdCveAdapter(),
        OpenFdaAdapter(),
        OpenFecAdapter(),
        IcijOffshoreLeaksAdapter(),
        NppesNpiAdapter(),
    ]
    assert {a.source_code for a in adapters} == {
        "wikidata_search",
        "orcid_public",
        "nvd_cve_api",
        "openfda",
        "us_fec",
        "icij_offshore_leaks",
        "us_nppes_npi",
    }
    assert all(a.capabilities for a in adapters)

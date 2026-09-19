from __future__ import annotations

import httpx

from app.intelligence_sources.adapters.contracts import RemoteAdapterStatus, RemoteSourceQuery
from app.intelligence_sources.adapters.datacite import DataCiteAdapter
from app.intelligence_sources.adapters.federal_register import FederalRegisterAdapter
from app.intelligence_sources.adapters.google_dns import GooglePublicDnsAdapter
from app.intelligence_sources.adapters.internet_archive import InternetArchiveMetadataAdapter
from app.intelligence_sources.adapters.peeringdb import PeeringDbAdapter
from app.intelligence_sources.adapters.rdap_bootstrap import RdapBootstrapAdapter
from app.intelligence_sources.adapters.ripestat import RipeStatAdapter
from app.intelligence_sources.adapters.un_sanctions import UnSecurityCouncilSanctionsAdapter
from app.intelligence_sources.adapters.usaspending import UsaSpendingRecipientAdapter
from app.intelligence_sources.adapters.zenodo_public import ZenodoPublicAdapter


def q(capability: str, value: str, *, country: str | None = None, limit: int = 20):
    return RemoteSourceQuery(capability=capability, value=value, country=country, limit=limit)


def test_rdap_domain_follows_public_registration_mapping_without_raw_vcard():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/domain/example.com"
        return httpx.Response(200, json={
            "objectClassName": "domain",
            "handle": "EXAMPLE",
            "ldhName": "EXAMPLE.COM",
            "status": ["active"],
            "entities": [{
                "handle": "REG-1", "roles": ["registrar"],
                "vcardArray": ["vcard", [["fn", {}, "text", "Example Registrar"]]],
            }],
            "events": [{"eventAction": "registration", "eventDate": "1995-08-14T00:00:00Z"}],
        }, request=request)
    result = RdapBootstrapAdapter(transport=httpx.MockTransport(handler)).search(q("domain_rdap", "example.com"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].identifiers["DOMAIN"] == "EXAMPLE.COM"
    assert result.records[0].attributes["entities"][0]["roles"] == ["registrar"]
    assert result.records[0].attributes["raw_response_stored"] is False


def test_rdap_rejects_malformed_ip_before_network():
    result = RdapBootstrapAdapter().search(q("ip_rdap", "999.999.1.1"))
    assert result.status is RemoteAdapterStatus.NOT_SUPPORTED


def test_ripestat_network_info_maps_prefix_and_asns():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/network-info/data.json")
        assert request.url.params["resource"] == "1.1.1.1"
        return httpx.Response(200, json={"data": {"prefix": "1.1.1.0/24", "asns": [13335]}}, request=request)
    result = RipeStatAdapter(transport=httpx.MockTransport(handler)).search(q("ip", "1.1.1.1"))
    assert result.records[0].identifiers["PREFIX"] == "1.1.1.0/24"
    assert result.records[0].attributes["asns"] == ["13335"]


def test_ripestat_as_overview_maps_holder():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/as-overview/data.json")
        return httpx.Response(200, json={"data": {"holder": "EXAMPLE-NET", "announced": True, "block": {"resource": "AS1-AS10"}, "type": "as"}}, request=request)
    result = RipeStatAdapter(transport=httpx.MockTransport(handler)).search(q("asn", "AS13335"))
    assert result.records[0].display_name == "EXAMPLE-NET"
    assert result.records[0].identifiers["ASN"] == "AS13335"


def test_peeringdb_uses_guest_exact_asn_and_does_not_request_contacts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["asn"] == "13335"
        assert "poc" not in request.url.params.get("fields", "")
        return httpx.Response(200, json={"data": [{
            "id": 42, "org_id": 9, "name": "Example Network", "asn": 13335,
            "website": "https://example.test", "info_type": "Content", "status": "ok",
        }]}, request=request)
    result = PeeringDbAdapter(transport=httpx.MockTransport(handler)).search(q("asn", "AS13335"))
    assert result.records[0].identifiers["ASN"] == "AS13335"
    assert result.records[0].attributes["contact_data_requested"] is False


def test_google_dns_collects_multiple_record_types_without_disk_cache():
    def handler(request: httpx.Request) -> httpx.Response:
        rtype = request.url.params["type"]
        answers = []
        if rtype == "A":
            answers = [{"name": "example.com.", "type": 1, "TTL": 60, "data": "93.184.216.34"}]
        elif rtype == "MX":
            answers = [{"name": "example.com.", "type": 15, "TTL": 60, "data": "10 mail.example.com."}]
        return httpx.Response(200, json={"Status": 0, "Answer": answers}, request=request)
    result = GooglePublicDnsAdapter(transport=httpx.MockTransport(handler)).search(q("dns", "example.com"))
    records = result.records[0].attributes["dns_records"]
    assert records["A"][0]["data"] == "93.184.216.34"
    assert records["MX"][0]["data"].startswith("10 ")
    assert result.records[0].attributes["no_local_cache"] is True


def test_usaspending_recipient_search_is_candidate_only():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = request.read().decode()
        assert "Example Corp" in body
        return httpx.Response(200, json={"results": [{
            "id": "recipient-1", "name": "Example Corp", "uei": "ABC123", "duns": "123456789", "amount": 123.45, "level": "R",
        }]}, request=request)
    result = UsaSpendingRecipientAdapter(transport=httpx.MockTransport(handler)).search(q("organization", "Example Corp", country="US"))
    assert result.records[0].identifiers["UEI"] == "ABC123"
    assert result.records[0].attributes["candidate_only"] is True


def test_usaspending_country_scope_is_us_only():
    adapter = UsaSpendingRecipientAdapter()
    assert adapter.supports(q("recipient", "Example", country="US")) is True
    assert adapter.supports(q("recipient", "Example", country="UA")) is False


def test_federal_register_maps_mentions_without_downloading_pdf():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["conditions[term]"] == "Example Corp"
        return httpx.Response(200, json={"results": [{
            "document_number": "2026-12345", "title": "Example Notice", "type": "Notice",
            "abstract": "Mentions Example Corp", "publication_date": "2026-09-19",
            "html_url": "https://www.federalregister.gov/documents/2026/09/19/2026-12345/example",
            "pdf_url": "https://example.test/big.pdf", "agencies": [{"name": "Example Agency"}],
        }]}, request=request)
    result = FederalRegisterAdapter(transport=httpx.MockTransport(handler)).search(q("organization", "Example Corp", country="US"))
    attrs = result.records[0].attributes
    assert attrs["candidate_only"] is True
    assert attrs["linked_pdf_downloaded"] is False
    assert attrs["agencies"] == ["Example Agency"]


def test_datacite_exact_doi_is_not_candidate():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {
            "id": "10.1234/example", "attributes": {
                "doi": "10.1234/example", "titles": [{"title": "Example Dataset"}],
                "creators": [{"name": "A. Researcher"}], "publisher": "Example Repo",
                "publicationYear": 2026, "types": {"resourceTypeGeneral": "Dataset"},
                "subjects": [{"subject": "OSINT"}],
            }
        }}, request=request)
    result = DataCiteAdapter(transport=httpx.MockTransport(handler)).search(q("doi", "10.1234/example"))
    assert result.records[0].identifiers["DOI"] == "10.1234/example"
    assert result.records[0].attributes["candidate_only"] is False
    assert result.records[0].attributes["linked_files_downloaded"] is False


def test_datacite_general_search_is_candidate_metadata_only():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == "Example Research"
        return httpx.Response(200, json={"data": [{
            "id": "10.1/x", "attributes": {"doi": "10.1/x", "titles": [{"title": "Example Research"}], "creators": []}
        }]}, request=request)
    result = DataCiteAdapter(transport=httpx.MockTransport(handler)).search(q("research_output", "Example Research"))
    assert result.records[0].attributes["candidate_only"] is True
    assert result.records[0].attributes["public_metadata_only"] is True


def test_zenodo_anonymous_record_search_never_downloads_files():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["size"] == "5"
        return httpx.Response(200, json={"hits": {"hits": [{
            "id": "123", "doi": "10.5281/zenodo.123", "metadata": {
                "title": "Example Archive", "creators": [{"name": "Alice"}], "publication_date": "2026-09-01",
                "resource_type": {"title": "Dataset"}, "keywords": ["osint"]
            }, "links": {"html": "https://zenodo.org/records/123", "files": "https://example.test/files"}
        }]}}, request=request)
    result = ZenodoPublicAdapter(transport=httpx.MockTransport(handler)).search(q("dataset", "Example", limit=5))
    assert result.records[0].attributes["record_files_downloaded"] is False
    assert result.metadata["anonymous_request"] is True


def test_internet_archive_metadata_search_does_not_download_item():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["output"] == "json"
        return httpx.Response(200, json={"response": {"docs": [{
            "identifier": "example_item", "title": "Example Item", "creator": ["Alice"],
            "date": "1999", "collection": ["opensource"], "mediatype": "texts",
        }]}}, request=request)
    result = InternetArchiveMetadataAdapter(transport=httpx.MockTransport(handler)).search(q("archive_search", "Example Item"))
    attrs = result.records[0].attributes
    assert attrs["metadata_search_only"] is True
    assert attrs["archive_item_downloaded"] is False


def test_internet_archive_name_search_is_candidate_only():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"docs": [{"identifier": "x", "title": "Alice Example"}]}}, request=request)
    result = InternetArchiveMetadataAdapter(transport=httpx.MockTransport(handler)).search(q("name", "Alice Example"))
    assert result.records[0].attributes["candidate_only"] is True


def test_un_sanctions_explicit_name_search_is_candidate_only_and_transient():
    xml = b'''<?xml version="1.0"?><CONSOLIDATED_LIST><INDIVIDUALS><INDIVIDUAL>
    <DATAID>1</DATAID><REFERENCE_NUMBER>XXi.001</REFERENCE_NUMBER><FIRST_NAME>Example</FIRST_NAME><SECOND_NAME>Person</SECOND_NAME><LISTED_ON>2026-01-01</LISTED_ON>
    <INDIVIDUAL_ALIAS><ALIAS_NAME>Example Alias</ALIAS_NAME></INDIVIDUAL_ALIAS><DESIGNATION><VALUE>Example role</VALUE></DESIGNATION>
    </INDIVIDUAL></INDIVIDUALS><ENTITIES></ENTITIES></CONSOLIDATED_LIST>'''
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=xml, headers={"Content-Type": "application/xml"}, request=request)
    result = UnSecurityCouncilSanctionsAdapter(transport=httpx.MockTransport(handler)).search(q("sanctions_name", "Example Person"))
    attrs = result.records[0].attributes
    assert attrs["candidate_only"] is True
    assert attrs["guilt_or_criminality_inference_prohibited"] is True
    assert result.metadata["feed_persisted"] is False


def test_un_sanctions_rejects_untrusted_redirect():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://evil.example/file.xml"}, request=request)
    result = UnSecurityCouncilSanctionsAdapter(transport=httpx.MockTransport(handler)).search(q("sanctions_name", "Example Person"))
    assert result.status is RemoteAdapterStatus.FAILED


def test_pack_has_ten_new_low_footprint_sources():
    adapters = [
        RdapBootstrapAdapter(), RipeStatAdapter(), PeeringDbAdapter(), GooglePublicDnsAdapter(),
        UsaSpendingRecipientAdapter(), FederalRegisterAdapter(), DataCiteAdapter(), ZenodoPublicAdapter(),
        InternetArchiveMetadataAdapter(), UnSecurityCouncilSanctionsAdapter(),
    ]
    assert len(adapters) == 10
    assert len({adapter.source_code for adapter in adapters}) == 10
    assert all(adapter.capabilities for adapter in adapters)

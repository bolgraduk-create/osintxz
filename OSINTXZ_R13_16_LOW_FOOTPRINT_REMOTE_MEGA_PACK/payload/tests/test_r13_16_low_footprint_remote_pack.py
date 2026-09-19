from __future__ import annotations

import httpx

from app.intelligence_sources.adapters.circl_hashlookup import CirclHashlookupAdapter
from app.intelligence_sources.adapters.cisa_kev import CisaKevAdapter
from app.intelligence_sources.adapters.europe_pmc import EuropePmcAdapter
from app.intelligence_sources.adapters.fbi_wanted import FbiWantedAdapter
from app.intelligence_sources.adapters.first_epss import FirstEpssAdapter
from app.intelligence_sources.adapters.github_public import GitHubPublicUserAdapter
from app.intelligence_sources.adapters.gitlab_public import GitLabPublicUserAdapter
from app.intelligence_sources.adapters.library_of_congress import LibraryOfCongressAdapter
from app.intelligence_sources.adapters.semantic_scholar import SemanticScholarAdapter
from app.intelligence_sources.adapters.shodan_internetdb import ShodanInternetDbAdapter
from app.intelligence_sources.adapters.contracts import RemoteAdapterStatus, RemoteSourceQuery


def q(capability: str, value: str, *, country: str | None = None, limit: int = 20):
    return RemoteSourceQuery(capability=capability, value=value, country=country, limit=limit)


def test_github_public_user_maps_only_public_profile_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/octocat"
        return httpx.Response(200, json={
            "login": "octocat", "id": 1, "name": "Mona Lisa", "company": "GitHub",
            "html_url": "https://github.com/octocat", "email": "public@example.test",
            "public_repos": 2, "followers": 20,
        }, request=request)

    result = GitHubPublicUserAdapter(transport=httpx.MockTransport(handler)).search(q("username", "@octocat"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].identifiers["GITHUB_USERNAME"] == "octocat"
    assert result.records[0].attributes["person_identity_inference_prohibited"] is True
    assert result.records[0].attributes["raw_response_stored"] is False


def test_github_404_is_successful_empty_lookup():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"}, request=request)
    result = GitHubPublicUserAdapter(transport=httpx.MockTransport(handler)).search(q("username", "missing-user"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records == []


def test_gitlab_exact_username_query_and_mapping():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["username"] == "alice"
        return httpx.Response(200, json=[{
            "id": 7, "username": "alice", "name": "Alice Example",
            "web_url": "https://gitlab.com/alice", "public_email": "alice@example.test",
        }], request=request)
    result = GitLabPublicUserAdapter(transport=httpx.MockTransport(handler)).search(q("username", "alice"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records[0].identifiers["GITLAB_USERNAME"] == "alice"
    assert result.records[0].attributes["account_identity_only"] is True


def test_semantic_scholar_author_search_is_candidate_only():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/author/search")
        return httpx.Response(200, json={"data": [{
            "authorId": "123", "name": "Ada Example", "paperCount": 10,
            "affiliations": ["Example University"], "externalIds": {"ORCID": "0000-0000-0000-0001"},
        }]}, request=request)
    result = SemanticScholarAdapter(transport=httpx.MockTransport(handler)).search(q("academic_author", "Ada Example"))
    assert result.records[0].attributes["candidate_only"] is True
    assert result.records[0].identifiers["ORCID"] == "0000-0000-0000-0001"


def test_semantic_scholar_paper_search_maps_external_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/paper/search")
        return httpx.Response(200, json={"data": [{
            "paperId": "p1", "title": "Example Paper", "year": 2026,
            "externalIds": {"DOI": "10.1000/example"},
            "authors": [{"authorId": "a1", "name": "A. Author"}],
        }]}, request=request)
    result = SemanticScholarAdapter(transport=httpx.MockTransport(handler)).search(q("paper", "Example Paper"))
    assert result.records[0].identifiers["DOI"] == "10.1000/example"
    assert result.records[0].attributes["authors"] == ["A. Author"]


def test_europe_pmc_author_query_is_bounded_candidate_search():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"].startswith('AUTH:"')
        assert request.url.params["pageSize"] == "5"
        return httpx.Response(200, json={"resultList": {"result": [{
            "pmid": "12345", "doi": "10.1/test", "title": "Public Article",
            "authorString": "Jane Doe", "pubYear": "2026",
        }]}}, request=request)
    result = EuropePmcAdapter(transport=httpx.MockTransport(handler)).search(q("author", "Jane Doe", limit=5))
    assert result.records[0].identifiers["PMID"] == "12345"
    assert result.records[0].attributes["candidate_only"] is True


def test_library_of_congress_search_does_not_download_resources():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["fo"] == "json"
        return httpx.Response(200, json={"results": [{
            "id": "https://www.loc.gov/item/abc/", "item_id": "abc", "title": "Historic Record",
            "date": "1918", "subject": ["History"], "resources": [{"url": "https://example.test/big-file.tif"}],
        }], "pagination": {}}, request=request)
    result = LibraryOfCongressAdapter(transport=httpx.MockTransport(handler)).search(q("archive_search", "Historic Record"))
    attrs = result.records[0].attributes
    assert attrs["raw_resource_downloaded"] is False
    assert "resources" not in attrs
    assert attrs["no_local_cache"] is True


def test_fbi_wanted_result_keeps_legal_safety_flags():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["title"] == "Example Name"
        return httpx.Response(200, json={"total": 1, "items": [{
            "uid": "fbi-1", "title": "Example Name", "url": "https://www.fbi.gov/wanted/example",
            "subjects": ["Seeking Information"], "aliases": ["Alias"],
        }]}, request=request)
    result = FbiWantedAdapter(transport=httpx.MockTransport(handler)).search(q("wanted_name", "Example Name", country="US"))
    attrs = result.records[0].attributes
    assert attrs["candidate_only"] is True
    assert attrs["guilt_inference_prohibited"] is True
    assert attrs["notice_is_not_proof_of_identity_or_guilt"] is True


def test_fbi_wanted_country_scope_is_us_only():
    adapter = FbiWantedAdapter()
    assert adapter.supports(q("wanted_name", "Example", country="US")) is True
    assert adapter.supports(q("wanted_name", "Example", country="UA")) is False


def test_first_epss_requires_exact_cve_and_maps_score():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["cve"] == "CVE-2026-12345"
        return httpx.Response(200, json={"data": [{
            "cve": "CVE-2026-12345", "epss": "0.42", "percentile": "0.90", "date": "2026-09-19",
        }]}, request=request)
    result = FirstEpssAdapter(transport=httpx.MockTransport(handler)).search(q("cve", "CVE-2026-12345"))
    assert result.records[0].attributes["epss"] == "0.42"
    bad = FirstEpssAdapter().search(q("cve", "openssl"))
    assert bad.status is RemoteAdapterStatus.NOT_SUPPORTED


def test_circl_hashlookup_exact_sha256_and_no_maliciousness_inference():
    digest = "a" * 64
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/lookup/sha256/{digest.upper()}"
        return httpx.Response(200, json={
            "FileName": "known.dll", "FileSize": "100", "SHA-256": digest.upper(),
            "source": "NSRL", "hashlookup:trust": 90,
        }, request=request)
    result = CirclHashlookupAdapter(transport=httpx.MockTransport(handler)).search(q("hash", digest))
    assert result.records[0].identifiers["SHA-256"] == digest.upper()
    assert result.records[0].attributes["maliciousness_inference_prohibited"] is True


def test_circl_hashlookup_404_is_known_empty_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)
    result = CirclHashlookupAdapter(transport=httpx.MockTransport(handler)).search(q("sha1", "b" * 40))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records == []


def test_shodan_internetdb_maps_small_ip_snapshot_without_banners():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/1.1.1.1"
        return httpx.Response(200, json={
            "ip": "1.1.1.1", "ports": [53, 443], "cpes": ["cpe:/a:test"],
            "hostnames": ["one.one.one.one"], "tags": ["cdn"], "vulns": ["CVE-2026-1"],
        }, request=request)
    result = ShodanInternetDbAdapter(transport=httpx.MockTransport(handler)).search(q("ip", "1.1.1.1"))
    assert result.records[0].attributes["ports"] == [53, 443]
    assert result.records[0].attributes["banner_data_returned"] is False


def test_shodan_internetdb_rejects_non_ip_before_network():
    result = ShodanInternetDbAdapter().search(q("ip", "example.com"))
    assert result.status is RemoteAdapterStatus.NOT_SUPPORTED


def test_cisa_kev_exact_cve_is_transient_feed_only():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("known_exploited_vulnerabilities.json")
        return httpx.Response(200, json={
            "catalogVersion": "2026.09.19", "vulnerabilities": [{
                "cveID": "CVE-2026-12345", "vendorProject": "Example", "product": "Example Product",
                "vulnerabilityName": "Example Vulnerability", "dateAdded": "2026-09-01",
                "shortDescription": "Example", "requiredAction": "Apply mitigations", "dueDate": "2026-09-20",
                "knownRansomwareCampaignUse": "Unknown", "notes": "https://example.test/advisory", "cwes": ["CWE-79"],
            }],
        }, request=request)
    result = CisaKevAdapter(transport=httpx.MockTransport(handler)).search(q("known_exploited", "CVE-2026-12345"))
    assert result.records[0].identifiers["CVE"] == "CVE-2026-12345"
    assert result.metadata["feed_persisted"] is False
    assert result.metadata["transient_feed_bytes_only"] is True


def test_cisa_kev_absent_cve_is_success_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"catalogVersion": "1", "vulnerabilities": []}, request=request)
    result = CisaKevAdapter(transport=httpx.MockTransport(handler)).search(q("cve", "CVE-2026-99999"))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert result.records == []


def test_pack_has_ten_low_footprint_sources():
    adapters = [
        GitHubPublicUserAdapter(), GitLabPublicUserAdapter(), SemanticScholarAdapter(),
        EuropePmcAdapter(), LibraryOfCongressAdapter(), FbiWantedAdapter(), FirstEpssAdapter(),
        CirclHashlookupAdapter(), ShodanInternetDbAdapter(), CisaKevAdapter(),
    ]
    assert len(adapters) == 10
    assert len({item.source_code for item in adapters}) == 10
    assert all(item.capabilities for item in adapters)

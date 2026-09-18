from __future__ import annotations

import httpx
import pytest

from app.exposure_intelligence.service import ExposureFederationService
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterStatus,
    RemoteSourceQuery,
)
from app.intelligence_sources.adapters.github_secret_scanning import (
    GitHubSecretScanningAdapter,
    GitHubSecretScanningClient,
)
from app.intelligence_sources.adapters.hibp_extended import (
    HibpExtendedClient,
    HibpPasteAdapter,
    HibpStealerLogEmailAdapter,
    HibpStealerLogEmailDomainAdapter,
    HibpStealerLogWebsiteDomainAdapter,
    HibpVerifiedDomainAdapter,
)
from app.intelligence_sources.adapters.registry import RemoteSourceAdapterRegistry
from app.intelligence_sources.adapters.service import RemoteSourceAdapterService


def _hibp_transport(routes: dict[str, object], seen: list[httpx.Request] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        value = routes.get(request.url.path, ...)
        if value is ...:
            return httpx.Response(404, request=request)
        if isinstance(value, tuple):
            status, payload = value
            return httpx.Response(status, json=payload, request=request)
        return httpx.Response(200, json=value, request=request)
    return httpx.MockTransport(handler)


def test_remote_query_verified_scope_defaults_false():
    query = RemoteSourceQuery(capability="email", value="a@example.com")
    assert query.verified_scope is False


def test_hibp_paste_adapter_returns_metadata_only_and_never_fetches_paste_body():
    seen: list[httpx.Request] = []
    client = HibpExtendedClient(
        api_key="0" * 32,
        transport=_hibp_transport(
            {
                "/api/v3/pasteAccount/person@example.com": [
                    {
                        "Source": "Pastebin",
                        "Id": "8Q0BvKD8",
                        "Title": "syslog",
                        "Date": "2014-03-04T19:14:54Z",
                        "EmailCount": 139,
                    }
                ]
            },
            seen,
        ),
    )
    adapter = HibpPasteAdapter(client=client)
    result = adapter.search(RemoteSourceQuery(
        capability="paste_exposure",
        value="person@example.com",
        sources=("hibp_pastes",),
    ))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert len(result.records) == 1
    record = result.records[0]
    assert record.record_type == "paste_exposure"
    assert record.attributes["paste_content_fetched"] is False
    assert record.attributes["raw_secret_values_stored"] is False
    assert all("pastebin.com" not in str(req.url) for req in seen)


def test_verified_domain_search_requires_explicit_verified_scope_before_network():
    called = False
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500, request=request)
    adapter = HibpVerifiedDomainAdapter(
        client=HibpExtendedClient(api_key="0" * 32, transport=httpx.MockTransport(handler))
    )
    result = adapter.search(RemoteSourceQuery(
        capability="verified_domain_breach",
        value="example.com",
        sources=("hibp_verified_domain",),
    ))
    assert result.status is RemoteAdapterStatus.NOT_SUPPORTED
    assert result.metadata["verified_scope_required"] is True
    assert called is False


def test_verified_domain_search_checks_subscribed_domains_then_maps_aliases():
    seen: list[httpx.Request] = []
    client = HibpExtendedClient(
        api_key="0" * 32,
        transport=_hibp_transport(
            {
                "/api/v3/subscribedDomains": [
                    {"DomainName": "example.com", "PwnCount": 3}
                ],
                "/api/v3/breachedDomain/example.com": {
                    "alice": ["Adobe", "ExampleBreach"],
                    "bob": ["ExampleBreach"],
                },
            },
            seen,
        ),
    )
    result = HibpVerifiedDomainAdapter(client=client).search(RemoteSourceQuery(
        capability="verified_domain_breach",
        value="example.com",
        sources=("hibp_verified_domain",),
        verified_scope=True,
    ))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert {r.identifiers["EMAIL"] for r in result.records} == {
        "alice@example.com", "bob@example.com"
    }
    assert all(r.attributes["verified_scope"] is True for r in result.records)
    assert [req.url.path for req in seen] == [
        "/api/v3/subscribedDomains",
        "/api/v3/breachedDomain/example.com",
    ]


def test_unverified_hibp_domain_is_blocked_without_sensitive_query():
    seen: list[httpx.Request] = []
    client = HibpExtendedClient(
        api_key="0" * 32,
        transport=_hibp_transport(
            {"/api/v3/subscribedDomains": [{"DomainName": "owned.example"}]},
            seen,
        ),
    )
    result = HibpVerifiedDomainAdapter(client=client).search(RemoteSourceQuery(
        capability="verified_domain_breach",
        value="other.example",
        sources=("hibp_verified_domain",),
        verified_scope=True,
    ))
    assert result.status is RemoteAdapterStatus.NOT_SUPPORTED
    assert [req.url.path for req in seen] == ["/api/v3/subscribedDomains"]


def test_stealer_log_email_returns_exposure_fact_without_password_values():
    client = HibpExtendedClient(
        api_key="0" * 32,
        transport=_hibp_transport({
            "/api/v3/subscribedDomains": [{"DomainName": "example.com"}],
            "/api/v3/stealerLogsByEmail/alice@example.com": [
                "netflix.com", "spotify.com"
            ],
        }),
    )
    result = HibpStealerLogEmailAdapter(client=client).search(RemoteSourceQuery(
        capability="stealer_log_email",
        value="alice@example.com",
        sources=("hibp_stealer_logs_email",),
        verified_scope=True,
    ))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert len(result.records) == 2
    assert all(r.attributes["credential_exposed"] is True for r in result.records)
    assert all(r.attributes["password_value_returned"] is False for r in result.records)
    assert all(r.attributes["raw_secret_values_stored"] is False for r in result.records)


def test_stealer_email_domain_and_website_domain_are_verified_scope_only():
    routes = {
        "/api/v3/subscribedDomains": [{"DomainName": "example.com"}],
        "/api/v3/stealerLogsByEmailDomain/example.com": {
            "alice": ["service-a.example", "service-b.example"]
        },
        "/api/v3/stealerLogsByWebsiteDomain/example.com": [
            "victim1@external.test", "victim2@external.test"
        ],
    }
    client = HibpExtendedClient(api_key="0" * 32, transport=_hibp_transport(routes))
    email_domain = HibpStealerLogEmailDomainAdapter(client=client).search(
        RemoteSourceQuery(
            capability="stealer_log_email_domain",
            value="example.com",
            sources=("hibp_stealer_logs_email_domain",),
            verified_scope=True,
        )
    )
    website_domain = HibpStealerLogWebsiteDomainAdapter(client=client).search(
        RemoteSourceQuery(
            capability="stealer_log_website_domain",
            value="example.com",
            sources=("hibp_stealer_logs_website_domain",),
            verified_scope=True,
        )
    )
    assert email_domain.records[0].identifiers["EMAIL"] == "alice@example.com"
    assert email_domain.records[0].attributes["password_values_returned"] is False
    assert len(website_domain.records) == 2
    assert all(r.attributes["password_values_returned"] is False for r in website_domain.records)


def test_github_secret_scanning_requests_hide_secret_and_discards_defensive_secret_field():
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen["hide_secret"] = request.url.params.get("hide_secret")
        seen["version"] = request.headers.get("X-GitHub-Api-Version")
        return httpx.Response(200, json=[{
            "number": 7,
            "html_url": "https://github.com/acme/repo/security/secret-scanning/7",
            "state": "open",
            "secret_type": "github_pat",
            "secret_type_display_name": "GitHub Personal Access Token",
            "secret": "github_pat_SHOULD_NEVER_PERSIST",
            "validity": "active",
            "publicly_leaked": True,
            "multi_repo": False,
            "first_location_detected": {"path": "config.txt", "commit_sha": "abc"},
        }], request=request)

    adapter = GitHubSecretScanningAdapter(
        client=GitHubSecretScanningClient(
            token="token",
            transport=httpx.MockTransport(handler),
        )
    )
    result = adapter.search(RemoteSourceQuery(
        capability="repository_secret_exposure",
        value="acme/repo",
        sources=("github_secret_scanning",),
        verified_scope=True,
    ))
    assert result.status is RemoteAdapterStatus.SUCCESS
    assert seen["hide_secret"] == "true"
    assert seen["version"] == GitHubSecretScanningClient.API_VERSION
    assert len(result.records) == 1
    attrs = result.records[0].attributes
    assert "secret" not in attrs
    assert "SHOULD_NEVER_PERSIST" not in repr(result.records[0])
    assert attrs["literal_secret_returned"] is False
    assert attrs["raw_secret_values_stored"] is False


def test_github_secret_scanning_requires_verified_scope_before_network():
    called = False
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json=[], request=request)
    adapter = GitHubSecretScanningAdapter(
        client=GitHubSecretScanningClient(token="token", transport=httpx.MockTransport(handler))
    )
    result = adapter.search(RemoteSourceQuery(
        capability="repository_secret_exposure",
        value="acme/repo",
        sources=("github_secret_scanning",),
    ))
    assert result.status is RemoteAdapterStatus.NOT_SUPPORTED
    assert called is False


def test_exposure_federation_email_now_includes_paste_metadata():
    client = HibpExtendedClient(
        api_key="0" * 32,
        transport=_hibp_transport({
            "/api/v3/pasteAccount/person@example.com": [
                {"Source": "Pastebin", "Id": "abc", "EmailCount": 2}
            ]
        }),
    )
    registry = RemoteSourceAdapterRegistry()
    registry.register(HibpPasteAdapter(client=client))
    federation = ExposureFederationService(
        remote_service=RemoteSourceAdapterService(registry=registry)
    )
    result = federation.search_email("person@example.com")
    assert result.summary.paste_records == 1
    assert result.summary.total_records == 1


def test_verified_scope_methods_refuse_without_explicit_authorization_flag():
    registry = RemoteSourceAdapterRegistry()
    federation = ExposureFederationService(
        remote_service=RemoteSourceAdapterService(registry=registry)
    )
    with pytest.raises(ValueError):
        federation.search_verified_domain("example.com")
    with pytest.raises(ValueError):
        federation.search_stealer_logs_email("alice@example.com")
    with pytest.raises(ValueError):
        federation.search_repository_secret_exposure("acme/repo")


def test_exposure_summary_counts_stealer_and_secret_alerts():
    class DummyAdapter:
        source_code = "dummy"
        capabilities = frozenset({"stealer_log_email"})
        configured = True
        automatic_enabled = False
        def supports(self, q): return q.capability == "stealer_log_email"
        def search(self, q):
            from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteSourceRecord
            return RemoteAdapterResult(
                source="dummy",
                status=RemoteAdapterStatus.SUCCESS,
                records=[RemoteSourceRecord(
                    source="dummy",
                    record_id="1",
                    record_type="stealer_log_exposure",
                    display_name="x",
                    attributes={
                        "secret_material_present": True,
                        "credential_exposed": True,
                        "verified_scope": True,
                        "raw_secret_values_stored": False,
                    },
                )],
            )
    # Direct summary check keeps routing source names out of this isolated test.
    registry = RemoteSourceAdapterRegistry(); registry.register(DummyAdapter())
    remote = RemoteSourceAdapterService(registry=registry)
    federated = remote.search(RemoteSourceQuery(
        capability="stealer_log_email", value="x@example.com", sources=("dummy",), verified_scope=True
    ))
    summary = ExposureFederationService._summarize(federated)
    assert summary.stealer_log_records == 1
    assert summary.verified_scope_records == 1
    assert summary.secret_material_present is True
    assert summary.raw_secret_values_stored is False

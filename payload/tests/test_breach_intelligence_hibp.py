from __future__ import annotations

import hashlib

import httpx

from app.breach_intelligence.catalog import register_hibp_sources
from app.breach_intelligence.contracts import BreachResultStatus
from app.breach_intelligence.hibp_client import HibpHttpClient
from app.breach_intelligence.service import BreachIntelligenceService
from app.intelligence_sources.catalog import IntelligenceSourceCatalog


def test_hibp_catalog_registers_two_capabilities():
    catalog = IntelligenceSourceCatalog()
    register_hibp_sources(catalog)

    assert catalog.get("hibp_breached_account") is not None
    assert catalog.get("hibp_pwned_passwords") is not None
    assert (
        catalog.get("hibp_pwned_passwords").automatic_eligible()
        is True
    )
    assert (
        catalog.get("hibp_breached_account").automatic_eligible(
            credentials_available=True
        )
        is False
    )


def test_email_lookup_without_key_is_not_configured():
    service = BreachIntelligenceService(
        hibp_client=HibpHttpClient(api_key=None)
    )
    result = service.search_email("person@example.com")
    assert result.status is BreachResultStatus.NOT_CONFIGURED


def test_email_lookup_maps_breach_metadata_and_password_exposure():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("hibp-api-key")
        seen["ua"] = request.headers.get("user-agent")
        return httpx.Response(
            200,
            json=[
                {
                    "Name": "ExampleBreach",
                    "Title": "Example Breach",
                    "Domain": "example.com",
                    "BreachDate": "2025-01-01",
                    "AddedDate": "2025-02-01T00:00:00Z",
                    "ModifiedDate": "2025-02-02T00:00:00Z",
                    "PwnCount": 1000,
                    "DataClasses": [
                        "Email addresses",
                        "Passwords",
                    ],
                    "IsVerified": True,
                    "IsFabricated": False,
                    "IsSensitive": False,
                    "IsRetired": False,
                    "IsSpamList": False,
                }
            ],
            request=request,
        )

    service = BreachIntelligenceService(
        hibp_client=HibpHttpClient(
            api_key="0" * 32,
            transport=httpx.MockTransport(handler),
        )
    )
    result = service.search_email("person@example.com")

    assert result.status is BreachResultStatus.SUCCESS
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.subject_value == "person@example.com"
    assert finding.breach_name == "ExampleBreach"
    assert finding.password_exposed is True
    assert "Passwords" in finding.exposed_data_classes
    assert seen["key"] == "0" * 32
    assert seen["ua"]


def test_email_404_means_success_zero_breaches():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    service = BreachIntelligenceService(
        hibp_client=HibpHttpClient(
            api_key="0" * 32,
            transport=httpx.MockTransport(handler),
        )
    )
    result = service.search_email("none@example.com")
    assert result.status is BreachResultStatus.SUCCESS
    assert result.findings == []


def test_email_429_is_partial_and_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    service = BreachIntelligenceService(
        hibp_client=HibpHttpClient(
            api_key="0" * 32,
            transport=httpx.MockTransport(handler),
        )
    )
    result = service.search_email("person@example.com")
    assert result.status is BreachResultStatus.PARTIAL
    assert result.metadata["retryable"] is True


def test_pwned_passwords_only_sends_sha1_prefix_and_returns_count():
    password = "correct horse battery staple"
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix = digest[:5]
    suffix = digest[5:]
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["padding"] = request.headers.get("Add-Padding")
        return httpx.Response(
            200,
            text=f"AAAAA:0\n{suffix}:42\nBBBBB:0\n",
            request=request,
        )

    service = BreachIntelligenceService(
        hibp_client=HibpHttpClient(
            passwords_transport=httpx.MockTransport(handler),
        )
    )
    result = service.check_password(password)

    assert seen["path"] == f"/range/{prefix}"
    assert password not in seen["path"]
    assert seen["padding"] == "true"
    assert result.status is BreachResultStatus.SUCCESS
    assert result.metadata["password_exposed"] is True
    assert result.metadata["occurrence_count"] == 42
    assert result.findings[0].subject_value is None
    assert result.findings[0].metadata["plaintext_stored"] is False
    assert result.findings[0].metadata["full_hash_stored"] is False


def test_password_not_found_returns_zero_without_secret_value():
    password = "this-is-a-test-value"
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix = digest[:5]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/range/{prefix}"
        return httpx.Response(
            200,
            text="ABCDE:1\nFFFFF:0\n",
            request=request,
        )

    service = BreachIntelligenceService(
        hibp_client=HibpHttpClient(
            passwords_transport=httpx.MockTransport(handler),
        )
    )
    result = service.check_password(password)
    assert result.status is BreachResultStatus.SUCCESS
    assert result.metadata["password_exposed"] is False
    assert result.metadata["occurrence_count"] == 0
    assert result.findings[0].subject_value is None


def test_defensive_sanitizer_redacts_secret_keys_in_future_metadata():
    service = BreachIntelligenceService(
        hibp_client=HibpHttpClient(api_key="0" * 32)
    )
    payload = [{
        "Name": "B",
        "DataClasses": ["Email addresses"],
        "password": "should-never-pass",
    }]
    # Mapping intentionally does not copy arbitrary keys.
    finding = service._map_hibp_breach("a@b.c", payload[0])
    assert finding is not None
    assert "password" not in finding.metadata

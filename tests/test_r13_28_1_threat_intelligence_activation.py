from __future__ import annotations

import base64
from types import SimpleNamespace

from app.osint.capabilities import DiscoveryGoal
from app.osint.connectors.alienvault_otx_connector import AlienVaultOTXConnector
from app.osint.connectors.urlscan_connector import URLScanConnector
from app.osint.connectors.virustotal_connector import VirusTotalConnector
from app.osint.credential_policy import (
    configured_threat_intelligence_modules,
    secret_text,
)
from app.osint.models import ConnectorRequest, OsintTarget, OsintTargetType
from app.osint.pivot_policy import PivotTraversalState
from app.osint.pivot_router import OsintCapabilityRouter
from app.osint.result import ResultStatus


class _Secret:
    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


def _settings(**values):
    base = {
        "abuseipdb_api_key": None,
        "otx_api_key": None,
        "urlscan_api_key": None,
        "virustotal_api_key": None,
    }
    base.update(values)
    return SimpleNamespace(**base)


def test_secret_text_handles_secret_and_empty_values_without_repr_leak():
    assert secret_text(_Secret("abc")) == "abc"
    assert secret_text(_Secret("")) == ""
    assert secret_text(None) == ""


def test_configured_threat_modules_include_only_nonempty_supported_keys():
    modules = configured_threat_intelligence_modules(
        _settings(
            abuseipdb_api_key=_Secret("a"),
            otx_api_key=_Secret(""),
            urlscan_api_key=_Secret("u"),
            virustotal_api_key=None,
        )
    )

    assert modules == frozenset(
        {
            "abuseipdb_connector",
            "urlscan_connector",
        }
    )


def test_unconfigured_router_preserves_keyless_behavior():
    router = OsintCapabilityRouter()
    routes = router.route_defaults(
        target_type=OsintTargetType.IP,
        value="8.8.8.8",
        depth=0,
        entity_identity="entity:ip:1",
        state=PivotTraversalState(),
    )

    assert [route.goal for route in routes] == [
        DiscoveryGoal.NETWORK_ENRICHMENT
    ]


def test_configured_ip_threat_intelligence_routes_only_explicit_allowlist():
    router = OsintCapabilityRouter(
        configured_credential_modules=frozenset(
            {
                "abuseipdb_connector",
                "alienvault_otx_connector",
                "virustotal_connector",
                # Even if accidentally passed, this must not auto-enable.
                "intelligencex_connector",
            }
        )
    )

    routes = router.route_defaults(
        target_type=OsintTargetType.IP,
        value="8.8.8.8",
        depth=0,
        entity_identity="entity:ip:1",
        state=PivotTraversalState(),
    )
    threat = next(
        route
        for route in routes
        if route.goal is DiscoveryGoal.THREAT_INTELLIGENCE
    )
    names = {item.display_name for item in threat.connectors}

    assert names == {
        "AbuseIPDB",
        "AlienVault OTX",
        "VirusTotal",
    }
    assert "Intelligence X" not in names
    assert all(
        item.network_mode.value == "passive_remote"
        for item in threat.connectors
    )


def test_configured_url_route_includes_passive_urlscan_otx_and_vt():
    router = OsintCapabilityRouter(
        configured_credential_modules=frozenset(
            {
                "alienvault_otx_connector",
                "urlscan_connector",
                "virustotal_connector",
            }
        )
    )

    routes = router.route_defaults(
        target_type=OsintTargetType.URL,
        value="https://example.com/path?a=1",
        depth=0,
        entity_identity="entity:url:1",
        state=PivotTraversalState(),
    )

    threat = next(
        route
        for route in routes
        if route.goal is DiscoveryGoal.THREAT_INTELLIGENCE
    )
    assert {item.display_name for item in threat.connectors} == {
        "AlienVault OTX",
        "urlscan.io",
        "VirusTotal",
    }


def test_hash_route_exists_only_when_supported_keyed_source_is_configured():
    assert OsintCapabilityRouter().route_defaults(
        target_type=OsintTargetType.HASH,
        value="a" * 64,
        depth=0,
        entity_identity="entity:hash:1",
        state=PivotTraversalState(),
    ) == ()

    router = OsintCapabilityRouter(
        configured_credential_modules=frozenset(
            {"virustotal_connector"}
        )
    )
    routes = router.route_defaults(
        target_type=OsintTargetType.HASH,
        value="a" * 64,
        depth=0,
        entity_identity="entity:hash:1",
        state=PivotTraversalState(),
    )
    assert len(routes) == 1
    assert routes[0].goal is DiscoveryGoal.THREAT_INTELLIGENCE
    assert [item.display_name for item in routes[0].connectors] == [
        "VirusTotal"
    ]


def test_virustotal_url_identifier_is_unpadded_urlsafe_base64():
    connector = VirusTotalConnector()
    url = "https://example.com/a?x=1&y=two"

    endpoint, value = connector._build_endpoint(
        OsintTargetType.URL,
        url,
    )

    expected = (
        base64.urlsafe_b64encode(url.encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    assert endpoint == "urls"
    assert value == expected
    assert "=" not in value


def test_otx_url_path_percent_encodes_full_indicator():
    connector = AlienVaultOTXConnector()

    endpoint = connector._build_endpoint(
        OsintTargetType.URL,
        "https://example.com/a/b?x=1",
    )

    assert endpoint is not None
    assert endpoint.startswith("indicators/url/")
    assert "https%3A%2F%2Fexample.com%2Fa%2Fb%3Fx%3D1" in endpoint
    assert endpoint.endswith("/general")


def test_urlscan_query_is_passive_historical_search():
    connector = URLScanConnector()

    assert connector._build_query(
        OsintTargetType.DOMAIN,
        "Example.COM",
    ) == 'page.domain.keyword:"example.com"'
    assert connector._build_query(
        OsintTargetType.URL,
        "https://example.com/a",
    ) == 'task.url.keyword:"https://example.com/a"'


def test_urlscan_execute_uses_get_search_and_never_submit_scan(monkeypatch):
    connector = URLScanConnector()
    calls = []

    class _Response:
        status_code = 200
        text = '{"results": [], "total": 0, "has_more": false}'

        @staticmethod
        def json():
            return {
                "results": [],
                "total": 0,
                "has_more": False,
            }

    def fake_get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return _Response()

    def fail_post(*args, **kwargs):
        raise AssertionError("automatic urlscan connector must not POST scans")

    monkeypatch.setattr(
        "app.osint.connectors.urlscan_connector.connector_secret",
        lambda _name: "test-key",
    )
    monkeypatch.setattr(
        "app.osint.connectors.urlscan_connector.requests.get",
        fake_get,
    )
    monkeypatch.setattr(
        "app.osint.connectors.urlscan_connector.requests.post",
        fail_post,
    )

    result = connector.execute(
        ConnectorRequest(
            target=OsintTarget(
                target_type=OsintTargetType.DOMAIN,
                value="example.com",
            ),
            timeout=5,
            limit=5,
        )
    )

    assert result.status is ResultStatus.SUCCESS
    assert result.metadata["mode"] == "passive_search"
    assert calls[0][0] == "GET"
    assert calls[0][1].endswith("/api/v1/search")
    assert calls[0][2]["params"]["datasource"] == "scans"

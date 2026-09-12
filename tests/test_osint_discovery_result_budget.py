from __future__ import annotations

import json

import pytest

from app.osint.connectors import assetfinder_connector
from app.osint.connectors import dnsx_connector
from app.osint.connectors import gau_connector
from app.osint.connectors import katana_connector
from app.osint.connectors import subfinder_connector
from app.osint.connectors import waybackurls_connector
from app.osint.models import (
    ConnectorRequest,
    OsintTarget,
    OsintTargetType,
)
from app.osint.result import ResultStatus
from app.osint.runner import ToolExecutionResult


class FakeRunner:
    def __init__(
        self,
        result: ToolExecutionResult,
    ) -> None:
        self.result = result
        self.commands: list[list[str]] = []

    def run(
        self,
        command: list[str],
        **kwargs,
    ) -> ToolExecutionResult:
        self.commands.append(
            list(command)
        )
        return self.result


def request(
    *,
    limit: int | None,
) -> ConnectorRequest:
    return ConnectorRequest(
        target=OsintTarget(
            target_type=OsintTargetType.DOMAIN,
            value="example.com",
        ),
        timeout=30,
        include_related=True,
        limit=limit,
    )


def success_execution(
    stdout: str,
) -> ToolExecutionResult:
    return ToolExecutionResult(
        success=True,
        return_code=0,
        stdout=stdout,
        stderr="",
        execution_time=0.1,
    )


def patch_runtime(
    monkeypatch,
    module,
) -> None:
    monkeypatch.setattr(
        module,
        "tool_available",
        lambda name: True,
    )
    monkeypatch.setattr(
        module,
        "build_tool_command",
        lambda name, *args: [
            name,
            *args,
        ],
    )


def assert_budget(
    result,
    expected: int,
) -> None:
    assert result.status in {
        ResultStatus.SUCCESS,
        ResultStatus.PARTIAL,
    }
    assert result.total_findings == expected
    assert result.metadata["result_limit"] == expected
    assert result.metadata["limit_reached"] is True


def test_connector_request_limit_is_backward_compatible() -> None:
    default_request = ConnectorRequest(
        target=OsintTarget(
            target_type=OsintTargetType.DOMAIN,
            value="example.com",
        ),
    )

    assert default_request.limit is None

    limited_request = request(
        limit=5,
    )

    assert limited_request.limit == 5


def test_subfinder_honors_limit(
    monkeypatch,
) -> None:
    patch_runtime(
        monkeypatch,
        subfinder_connector,
    )

    rows = [
        json.dumps(
            {
                "host": f"s{i}.example.com",
                "source": "fixture",
            }
        )
        for i in range(8)
    ]

    connector = (
        subfinder_connector.SubfinderConnector()
    )
    connector.runner = FakeRunner(
        success_execution(
            "\n".join(rows),
        )
    )

    result = connector.execute(
        request(limit=5),
    )

    assert_budget(
        result,
        5,
    )


def test_dnsx_honors_limit(
    monkeypatch,
) -> None:
    patch_runtime(
        monkeypatch,
        dnsx_connector,
    )

    rows = [
        json.dumps(
            {
                "host": f"d{i}.example.com",
                "a": ["192.0.2.1"],
            }
        )
        for i in range(8)
    ]

    connector = (
        dnsx_connector.DNSXConnector()
    )
    connector.runner = FakeRunner(
        success_execution(
            "\n".join(rows),
        )
    )

    result = connector.execute(
        request(limit=5),
    )

    assert_budget(
        result,
        5,
    )


def test_gau_honors_limit(
    monkeypatch,
) -> None:
    patch_runtime(
        monkeypatch,
        gau_connector,
    )

    rows = [
        f"https://example.com/path/{i}"
        for i in range(8)
    ]

    connector = (
        gau_connector.GauConnector()
    )
    connector.runner = FakeRunner(
        success_execution(
            "\n".join(rows),
        )
    )

    result = connector.execute(
        request(limit=5),
    )

    assert_budget(
        result,
        5,
    )


def test_waybackurls_honors_limit(
    monkeypatch,
) -> None:
    patch_runtime(
        monkeypatch,
        waybackurls_connector,
    )

    rows = [
        f"https://example.com/archive/{i}"
        for i in range(8)
    ]

    connector = (
        waybackurls_connector.WaybackurlsConnector()
    )
    connector.runner = FakeRunner(
        success_execution(
            "\n".join(rows),
        )
    )

    result = connector.execute(
        request(limit=5),
    )

    assert_budget(
        result,
        5,
    )


def test_katana_honors_limit(
    monkeypatch,
) -> None:
    patch_runtime(
        monkeypatch,
        katana_connector,
    )

    rows = [
        json.dumps(
            {
                "request": {
                    "endpoint": (
                        f"https://example.com/crawl/{i}"
                    )
                }
            }
        )
        for i in range(8)
    ]

    connector = (
        katana_connector.KatanaConnector()
    )
    connector.runner = FakeRunner(
        success_execution(
            "\n".join(rows),
        )
    )

    result = connector.execute(
        request(limit=5),
    )

    assert_budget(
        result,
        5,
    )


def test_assetfinder_honors_limit(
    monkeypatch,
) -> None:
    patch_runtime(
        monkeypatch,
        assetfinder_connector,
    )

    rows = [
        f"a{i}.example.com"
        for i in range(8)
    ]

    connector = (
        assetfinder_connector.AssetfinderConnector()
    )
    connector.runner = FakeRunner(
        success_execution(
            "\n".join(rows),
        )
    )

    result = connector.execute(
        request(limit=5),
    )

    assert_budget(
        result,
        5,
    )


@pytest.mark.parametrize(
    (
        "module",
        "connector_class",
        "stdout",
    ),
    [
        (
            waybackurls_connector,
            waybackurls_connector.WaybackurlsConnector,
            (
                "https://example.com/a\n"
                "https://example.com/a\n"
                "https://example.com/b\n"
            ),
        ),
        (
            assetfinder_connector,
            assetfinder_connector.AssetfinderConnector,
            (
                "A.EXAMPLE.COM\n"
                "a.example.com.\n"
                "example.com\n"
                "evil.example.net\n"
                "b.example.com\n"
            ),
        ),
    ],
)
def test_discovery_deduplication_does_not_consume_budget(
    monkeypatch,
    module,
    connector_class,
    stdout,
) -> None:
    patch_runtime(
        monkeypatch,
        module,
    )

    connector = connector_class()
    connector.runner = FakeRunner(
        success_execution(
            stdout,
        )
    )

    result = connector.execute(
        request(limit=2),
    )

    assert result.total_findings == 2

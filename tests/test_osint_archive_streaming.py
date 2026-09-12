from __future__ import annotations

import sys
import time

from app.osint.connectors import gau_connector
from app.osint.connectors import waybackurls_connector
from app.osint.models import (
    ConnectorRequest,
    OsintTarget,
    OsintTargetType,
)
from app.osint.result import ResultStatus
from app.osint.runner import (
    ToolExecutionResult,
    ToolRunner,
)


class FakeRunner:
    def __init__(
        self,
        execution: ToolExecutionResult,
    ) -> None:

        self.execution = execution
        self.calls = []

    def run(
        self,
        command,
        **kwargs,
    ):

        self.calls.append(
            {
                "command": list(command),
                **kwargs,
            }
        )

        return self.execution


def domain_request(
    *,
    limit=3,
    timeout=15,
):
    return ConnectorRequest(
        target=OsintTarget(
            target_type=OsintTargetType.DOMAIN,
            value="example.com",
        ),
        timeout=timeout,
        include_related=True,
        limit=limit,
    )


def test_tool_runner_can_stop_streaming_process_after_line_budget() -> None:

    runner = ToolRunner()

    command = [
        sys.executable,
        "-u",
        "-c",
        (
            "import time\n"
            "for i in range(10):\n"
            "    print(f'https://example.com/{i}', flush=True)\n"
            "    time.sleep(0.04)\n"
            "time.sleep(5)\n"
        ),
    ]

    started = time.perf_counter()

    result = runner.run(
        command=command,
        timeout=5,
        stdout_line_limit=3,
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    assert result.success is True
    assert result.return_code == -3
    assert result.stopped_early is True
    assert len(
        [
            line
            for line in result.stdout.splitlines()
            if line.strip()
        ]
    ) == 3
    assert elapsed < 3


def test_gau_bounded_request_uses_fast_providers_and_stream_budget(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        gau_connector,
        "tool_available",
        lambda name: True,
    )

    monkeypatch.setattr(
        gau_connector,
        "build_tool_command",
        lambda name, *args: [
            name,
            *args,
        ],
    )

    execution = ToolExecutionResult(
        success=True,
        return_code=-3,
        stdout=(
            "https://example.com/\n"
            "https://example.com/login\n"
            "https://api.example.com/v1\n"
        ),
        stderr="",
        execution_time=0.5,
        stopped_early=True,
    )

    connector = (
        gau_connector.GauConnector()
    )

    connector.runner = FakeRunner(
        execution
    )

    result = connector.execute(
        domain_request(
            limit=3,
        )
    )

    call = (
        connector
        .runner
        .calls[0]
    )

    command = call["command"]

    assert "--providers" in command
    assert "urlscan,otx" in command
    assert "--config" in command
    assert "--retries" in command
    assert "0" in command

    assert (
        call["stdout_line_limit"]
        == 12
    )

    assert result.status == ResultStatus.SUCCESS
    assert result.total_findings == 3
    assert result.metadata["limit_reached"] is True
    assert (
        result.metadata["provider_strategy"]
        == "bounded_fast"
    )
    assert result.metadata["stream_stopped_early"] is True


def test_gau_unbounded_request_keeps_default_all_provider_mode(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        gau_connector,
        "tool_available",
        lambda name: True,
    )

    monkeypatch.setattr(
        gau_connector,
        "build_tool_command",
        lambda name, *args: [
            name,
            *args,
        ],
    )

    execution = ToolExecutionResult(
        success=True,
        return_code=0,
        stdout="https://example.com/\n",
        stderr="",
        execution_time=0.5,
    )

    connector = (
        gau_connector.GauConnector()
    )

    connector.runner = FakeRunner(
        execution
    )

    result = connector.execute(
        domain_request(
            limit=None,
        )
    )

    call = (
        connector
        .runner
        .calls[0]
    )

    assert "--providers" not in call["command"]
    assert call["stdout_line_limit"] is None
    assert result.status == ResultStatus.SUCCESS
    assert (
        result.metadata["provider_strategy"]
        == "unbounded_all"
    )


def test_waybackurls_timeout_preserves_partial_findings(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        waybackurls_connector,
        "tool_available",
        lambda name: True,
    )

    monkeypatch.setattr(
        waybackurls_connector,
        "build_tool_command",
        lambda name, *args: [
            name,
            *args,
        ],
    )

    execution = ToolExecutionResult(
        success=False,
        return_code=-1,
        stdout=(
            "https://example.com/a\n"
            "https://example.com/b\n"
        ),
        stderr="Process timeout.",
        execution_time=15.0,
    )

    connector = (
        waybackurls_connector
        .WaybackurlsConnector()
    )

    connector.runner = FakeRunner(
        execution
    )

    result = connector.execute(
        domain_request(
            limit=3,
        )
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.total_findings == 2
    assert result.metadata["timed_out"] is True
    assert (
        connector
        .runner
        .calls[0]["stdout_line_limit"]
        == 12
    )


def test_waybackurls_filters_out_of_scope_and_honors_limit(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        waybackurls_connector,
        "tool_available",
        lambda name: True,
    )

    monkeypatch.setattr(
        waybackurls_connector,
        "build_tool_command",
        lambda name, *args: [
            name,
            *args,
        ],
    )

    execution = ToolExecutionResult(
        success=True,
        return_code=0,
        stdout=(
            "https://example.com/a\n"
            "https://outside.test/x\n"
            "https://www.example.com/b\n"
            "https://example.com/c\n"
            "https://example.com/d\n"
        ),
        stderr="",
        execution_time=0.2,
    )

    connector = (
        waybackurls_connector
        .WaybackurlsConnector()
    )

    connector.runner = FakeRunner(
        execution
    )

    result = connector.execute(
        domain_request(
            limit=3,
        )
    )

    assert result.status == ResultStatus.SUCCESS
    assert result.total_findings == 3
    assert result.metadata["limit_reached"] is True
    assert result.metadata["invalid_or_out_of_scope"] == 1

from __future__ import annotations

import subprocess

from app.osint.connectors import gau_connector
from app.osint.connectors import subfinder_connector
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
        result: ToolExecutionResult,
    ) -> None:
        self.result = result
        self.commands: list[
            list[str]
        ] = []

    def run(
        self,
        command: list[str],
        timeout: int = 300,
        **kwargs,
    ) -> ToolExecutionResult:
        self.commands.append(
            list(command)
        )
        return self.result


def domain_request(
    *,
    timeout: int = 30,
    include_related: bool = True,
) -> ConnectorRequest:

    return ConnectorRequest(
        target=OsintTarget(
            target_type=OsintTargetType.DOMAIN,
            value="example.com",
        ),
        timeout=timeout,
        include_related=include_related,
    )


def test_tool_runner_preserves_partial_output_on_timeout(
    monkeypatch,
) -> None:

    def fake_run(
        *args,
        **kwargs,
    ):
        raise subprocess.TimeoutExpired(
            cmd=["tool"],
            timeout=2,
            output=b"partial-out\n",
            stderr=b"partial-err\n",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    result = ToolRunner().run(
        ["tool"],
        timeout=2,
    )

    assert result.success is False
    assert result.return_code == -1
    assert result.stdout == "partial-out\n"
    assert "partial-err" in result.stderr
    assert "Process timeout." in result.stderr


def test_subfinder_filters_scope_and_duplicates(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        subfinder_connector,
        "tool_available",
        lambda name: True,
    )

    monkeypatch.setattr(
        subfinder_connector,
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
            '{"host":"a.example.com","source":"crtsh"}\n'
            '{"host":"A.EXAMPLE.COM","source":"other"}\n'
            '{"host":"example.com","source":"root"}\n'
            '{"host":"evil.example.net","source":"bad"}\n'
            '{"host":"","source":"empty"}\n'
        ),
        stderr="",
        execution_time=1.0,
    )

    connector = (
        subfinder_connector.SubfinderConnector()
    )
    connector.runner = FakeRunner(
        execution,
    )

    result = connector.execute(
        domain_request(),
    )

    assert result.status == ResultStatus.SUCCESS
    assert [
        finding.value
        for finding in result.findings
    ] == [
        "a.example.com",
    ]

    assert (
        result.metadata[
            "duplicates_removed"
        ]
        == 1
    )

    assert (
        result.metadata[
            "filtered_out"
        ]
        == 3
    )


def test_subfinder_timeout_returns_partial_findings(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        subfinder_connector,
        "tool_available",
        lambda name: True,
    )

    monkeypatch.setattr(
        subfinder_connector,
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
            '{"host":"one.example.com","source":"crtsh"}\n'
        ),
        stderr="Process timeout.",
        execution_time=30.0,
    )

    connector = (
        subfinder_connector.SubfinderConnector()
    )
    connector.runner = FakeRunner(
        execution,
    )

    result = connector.execute(
        domain_request(),
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.total_findings == 1
    assert result.metadata["timed_out"] is True


def test_gau_filters_scope_and_duplicates(
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
        stdout=(
            "https://example.com/a\n"
            "https://example.com/a\n"
            "https://sub.example.com/b?x=1\n"
            "https://evil.example.net/nope\n"
            "not-a-url\n"
        ),
        stderr=(
            "config warning"
        ),
        execution_time=2.0,
    )

    connector = (
        gau_connector.GauConnector()
    )
    connector.runner = FakeRunner(
        execution,
    )

    result = connector.execute(
        domain_request(),
    )

    assert result.status == ResultStatus.SUCCESS
    assert [
        finding.value
        for finding in result.findings
    ] == [
        "https://example.com/a",
        "https://sub.example.com/b?x=1",
    ]

    assert (
        result.metadata[
            "duplicates_removed"
        ]
        == 1
    )

    assert (
        result.metadata[
            "filtered_out"
        ]
        == 1
    )

    assert (
        result.metadata[
            "invalid_urls"
        ]
        == 1
    )

    assert (
        result.metadata[
            "tool_warnings"
        ]
        == "config warning"
    )


def test_gau_timeout_returns_partial_findings(
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
        success=False,
        return_code=-1,
        stdout=(
            "https://example.com/a\n"
        ),
        stderr="Process timeout.",
        execution_time=30.0,
    )

    connector = (
        gau_connector.GauConnector()
    )
    connector.runner = FakeRunner(
        execution,
    )

    result = connector.execute(
        domain_request(),
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.total_findings == 1
    assert result.metadata["timed_out"] is True


def test_discovery_connectors_use_bounded_cli_timeouts(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        subfinder_connector,
        "tool_available",
        lambda name: True,
    )
    monkeypatch.setattr(
        subfinder_connector,
        "build_tool_command",
        lambda name, *args: [
            name,
            *args,
        ],
    )

    sub_execution = ToolExecutionResult(
        success=True,
        return_code=0,
        stdout="",
        stderr="",
        execution_time=0.1,
    )

    sub = subfinder_connector.SubfinderConnector()
    sub.runner = FakeRunner(sub_execution)
    sub.execute(domain_request(timeout=30))

    sub_command = sub.runner.commands[0]

    assert "-duc" in sub_command
    assert "-timeout" in sub_command
    assert sub_command[
        sub_command.index("-timeout") + 1
    ] == "7"

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

    gau_execution = ToolExecutionResult(
        success=True,
        return_code=0,
        stdout="",
        stderr="",
        execution_time=0.1,
    )

    gau = gau_connector.GauConnector()
    gau.runner = FakeRunner(gau_execution)
    gau.execute(domain_request(timeout=30))

    gau_command = gau.runner.commands[0]

    assert "--threads" in gau_command
    assert "--timeout" in gau_command
    assert gau_command[
        gau_command.index("--timeout") + 1
    ] == "7"
    assert "--retries" in gau_command
    assert "--subs" in gau_command

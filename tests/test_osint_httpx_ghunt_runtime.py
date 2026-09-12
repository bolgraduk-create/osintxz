from __future__ import annotations

import json

from app.osint.connectors import ghunt_connector
from app.osint.connectors import httpx_connector
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
        results,
    ) -> None:

        if isinstance(
            results,
            ToolExecutionResult,
        ):
            results = [
                results,
            ]

        self.results = list(
            results,
        )

        self.commands: list[
            list[str]
        ] = []

        self.envs: list[
            dict[str, str] | None
        ] = []

    def run(
        self,
        command,
        **kwargs,
    ):

        self.commands.append(
            list(command)
        )

        self.envs.append(
            kwargs.get(
                "env",
            )
        )

        return self.results.pop(
            0
        )


def httpx_request(
    *,
    limit=5,
    timeout=20,
):
    return ConnectorRequest(
        target=OsintTarget(
            target_type=OsintTargetType.URL,
            value="https://example.com",
        ),
        timeout=timeout,
        limit=limit,
    )


def ghunt_request(
    *,
    limit=1,
):
    return ConnectorRequest(
        target=OsintTarget(
            target_type=OsintTargetType.EMAIL,
            value="person@example.com",
        ),
        timeout=20,
        limit=limit,
    )


def test_httpx_uses_managed_command_and_honors_limit(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        httpx_connector,
        "tool_available",
        lambda name: True,
    )

    monkeypatch.setattr(
        httpx_connector,
        "build_tool_command",
        lambda name, *args: [
            "C:/osintxz/tools/osint/bin/httpx.exe",
            *args,
        ],
    )

    execution = ToolExecutionResult(
        success=True,
        return_code=0,
        stdout="\n".join(
            json.dumps(
                {
                    "url": (
                        f"https://host-{index}.example.com"
                    ),
                    "status_code": 200,
                }
            )
            for index in range(10)
        ),
        stderr="",
        execution_time=0.5,
    )

    connector = (
        httpx_connector.HTTPXConnector()
    )

    connector.runner = FakeRunner(
        execution,
    )

    result = connector.execute(
        httpx_request(
            limit=5,
        )
    )

    assert result.status == ResultStatus.SUCCESS
    assert result.total_findings == 5
    assert result.metadata["result_limit"] == 5
    assert result.metadata["limit_reached"] is True

    command = connector.runner.commands[0]

    assert command[0].endswith(
        "httpx.exe"
    )
    assert "-u" in command
    assert "-json" in command
    assert "-silent" in command
    assert "-sc" in command
    assert "-duc" in command


def test_httpx_deduplicates_jsonl_and_survives_parse_noise(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        httpx_connector,
        "tool_available",
        lambda name: True,
    )

    monkeypatch.setattr(
        httpx_connector,
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
            '{"url":"https://example.com","status_code":200}\n'
            '{"url":"https://example.com","status_code":200}\n'
            'not-json\n'
        ),
        stderr="",
        execution_time=0.1,
    )

    connector = httpx_connector.HTTPXConnector()
    connector.runner = FakeRunner(execution)

    result = connector.execute(
        httpx_request(
            limit=5,
        )
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.total_findings == 1
    assert result.findings[0].url == "https://example.com"
    assert result.metadata["duplicates_removed"] == 1
    assert result.metadata["parse_errors"] == 1


def test_httpx_timeout_preserves_partial_findings(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        httpx_connector,
        "tool_available",
        lambda name: True,
    )

    monkeypatch.setattr(
        httpx_connector,
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
            '{"url":"https://example.com","status_code":200}\n'
        ),
        stderr="Process timeout.",
        execution_time=20.0,
    )

    connector = httpx_connector.HTTPXConnector()
    connector.runner = FakeRunner(execution)

    result = connector.execute(
        httpx_request()
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.total_findings == 1
    assert result.metadata["timed_out"] is True


def test_ghunt_health_check_uses_utf8_environment(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        ghunt_connector.shutil,
        "which",
        lambda name: "C:/fake/ghunt.exe",
    )

    health = ToolExecutionResult(
        success=True,
        return_code=0,
        stdout="GHunt v2 usage",
        stderr="",
        execution_time=0.1,
    )

    connector = ghunt_connector.GHuntConnector()
    connector.runner = FakeRunner(health)

    assert connector.is_available() is True

    assert connector.runner.commands[0] == [
        "C:/fake/ghunt.exe",
        "--help",
    ]

    assert connector.runner.envs[0] == {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }


def test_ghunt_health_check_rejects_traceback(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        ghunt_connector.shutil,
        "which",
        lambda name: "C:/fake/ghunt.exe",
    )

    health = ToolExecutionResult(
        success=False,
        return_code=1,
        stdout="GHunt v2",
        stderr=(
            "Traceback (most recent call last):\n"
            "UnicodeEncodeError: boom"
        ),
        execution_time=0.1,
    )

    connector = ghunt_connector.GHuntConnector()
    connector.runner = FakeRunner(health)

    assert connector.is_available() is False


def test_ghunt_execute_returns_not_available_when_health_is_broken(
    monkeypatch,
) -> None:

    monkeypatch.setattr(
        ghunt_connector.shutil,
        "which",
        lambda name: "C:/fake/ghunt.exe",
    )

    health = ToolExecutionResult(
        success=False,
        return_code=1,
        stdout="GHunt v2",
        stderr=(
            "Traceback (most recent call last):\n"
            "UnicodeEncodeError: boom"
        ),
        execution_time=0.1,
    )

    connector = ghunt_connector.GHuntConnector()
    connector.runner = FakeRunner(health)

    result = connector.execute(
        ghunt_request()
    )

    assert result.status == ResultStatus.NOT_AVAILABLE
    assert result.metadata["runtime_health"] == "failed"

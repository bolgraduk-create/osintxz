from __future__ import annotations

import sys

from app.osint.runner import ToolRunner
from app.security.tool_execution_policy import ToolExecutionPolicy


def test_tool_runner_blocks_empty_command_before_subprocess():
    result = ToolRunner().run(command=[], timeout=5)

    assert result.success is False
    assert result.return_code == -4
    assert result.blocked_by_policy is True
    assert "policy" in result.stderr.casefold()


def test_tool_runner_blocks_nul_in_command_argument():
    result = ToolRunner().run(
        command=[sys.executable, "bad\x00argument"],
        timeout=5,
    )

    assert result.success is False
    assert result.return_code == -4
    assert result.blocked_by_policy is True


def test_tool_runner_blocks_dangerous_environment_override():
    result = ToolRunner().run(
        command=[sys.executable, "-c", "print('not reached')"],
        timeout=5,
        env={"PYTHONPATH": "untrusted"},
    )

    assert result.success is False
    assert result.return_code == -4
    assert result.blocked_by_policy is True
    assert "PYTHONPATH" in result.stderr


def test_tool_runner_allows_safe_environment_override():
    result = ToolRunner().run(
        command=[
            sys.executable,
            "-c",
            "import os; print(os.environ.get('OSINTXZ_TEST_FLAG', ''))",
        ],
        timeout=5,
        env={"OSINTXZ_TEST_FLAG": "safe"},
    )

    assert result.success is True
    assert result.return_code == 0
    assert result.blocked_by_policy is False
    assert result.stdout.strip() == "safe"


def test_tool_runner_blocks_timeout_above_policy_ceiling():
    policy = ToolExecutionPolicy(max_timeout_seconds=2)
    result = ToolRunner(policy=policy).run(
        command=[sys.executable, "-c", "print('not reached')"],
        timeout=3,
    )

    assert result.success is False
    assert result.return_code == -4
    assert result.blocked_by_policy is True
    assert "timeout" in result.stderr.casefold()


def test_tool_runner_blocks_oversized_stdin():
    policy = ToolExecutionPolicy(max_stdin_bytes=4)
    result = ToolRunner(policy=policy).run(
        command=[sys.executable, "-c", "print('not reached')"],
        timeout=5,
        stdin="12345",
    )

    assert result.success is False
    assert result.return_code == -4
    assert result.blocked_by_policy is True
    assert "stdin" in result.stderr.casefold()


def test_tool_runner_blocks_missing_working_directory(tmp_path):
    missing = tmp_path / "does-not-exist"

    result = ToolRunner().run(
        command=[sys.executable, "-c", "print('not reached')"],
        timeout=5,
        working_directory=missing,
    )

    assert result.success is False
    assert result.return_code == -4
    assert result.blocked_by_policy is True
    assert "working directory" in result.stderr.casefold()

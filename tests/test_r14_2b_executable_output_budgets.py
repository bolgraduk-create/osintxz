from __future__ import annotations

from pathlib import Path
import os
import sys
import time

from app.osint.runner import ToolRunner
from app.osint.tool_runtime import MANAGED_TOOL_PATHS
from app.security.tool_execution_inventory import (
    APPROVED_OSINT_EXECUTABLES,
    canonical_executable_name,
)
from app.security.tool_execution_policy import (
    ToolExecutionPolicy,
)


def test_managed_tool_inventory_is_approved():
    assert set(MANAGED_TOOL_PATHS).issubset(
        APPROVED_OSINT_EXECUTABLES
    )


def test_inventory_normalizes_platform_suffixes():
    assert canonical_executable_name("NMAP.EXE") == "nmap"
    assert canonical_executable_name("SecretFinder.py") == "secretfinder"
    assert canonical_executable_name("testssl.sh") == "testssl"


def test_unknown_executable_path_is_blocked_before_launch(tmp_path):
    candidate = tmp_path / (
        "evil-tool.exe" if os.name == "nt" else "evil-tool"
    )
    candidate.write_text("not executable", encoding="utf-8")

    result = ToolRunner().run(
        command=[str(candidate)],
        timeout=2,
    )

    assert result.success is False
    assert result.return_code == -4
    assert result.blocked_by_policy is True
    assert "approved OSINT inventory" in result.stderr


def test_current_python_runtime_is_allowed_and_resolved():
    result = ToolRunner().run(
        command=[
            sys.executable,
            "-c",
            "print('runtime-ok')",
        ],
        timeout=5,
    )

    assert result.success is True
    assert result.stdout.strip() == "runtime-ok"
    assert result.resolved_executable is not None
    assert Path(result.resolved_executable).is_absolute()


def test_stdout_capture_is_bounded():
    policy = ToolExecutionPolicy(
        max_stdout_characters=64,
        max_stderr_characters=64,
    )

    result = ToolRunner(policy=policy).run(
        command=[
            sys.executable,
            "-c",
            "print('X' * 4096)",
        ],
        timeout=5,
    )

    assert result.success is True
    assert result.stdout_truncated is True
    assert len(result.stdout) == 64
    assert result.stderr_truncated is False


def test_stderr_capture_is_bounded():
    policy = ToolExecutionPolicy(
        max_stdout_characters=64,
        max_stderr_characters=48,
    )

    result = ToolRunner(policy=policy).run(
        command=[
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('E' * 4096)",
        ],
        timeout=5,
    )

    assert result.success is True
    assert result.stderr_truncated is True
    assert len(result.stderr) == 48


def test_streaming_line_limit_keeps_existing_early_stop_contract():
    result = ToolRunner().run(
        command=[
            sys.executable,
            "-c",
            (
                "import time; "
                "[(print(f'row-{i}', flush=True), time.sleep(0.03)) "
                "for i in range(20)]"
            ),
        ],
        timeout=5,
        stdout_line_limit=3,
    )

    assert result.success is True
    assert result.return_code == -3
    assert result.stopped_early is True
    assert result.stdout.splitlines() == [
        "row-0",
        "row-1",
        "row-2",
    ]


def test_timeout_terminates_child_process_tree(tmp_path):
    marker = tmp_path / "child-survived.txt"
    child_code = (
        "import pathlib,time; "
        "time.sleep(0.9); "
        f"pathlib.Path({str(marker)!r}).write_text('alive', encoding='utf-8')"
    )
    parent_code = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
        "time.sleep(5)"
    )

    result = ToolRunner().run(
        command=[
            sys.executable,
            "-c",
            parent_code,
        ],
        timeout=0.2,
    )

    assert result.success is False
    assert result.return_code == -1
    assert "Process timeout." in result.stderr

    time.sleep(1.1)

    assert marker.exists() is False

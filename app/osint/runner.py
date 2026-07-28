"""
OSINT tool runner.

Executes external OSINT tools
through a unified interface.

Responsibilities:

- execute CLI applications
- collect stdout/stderr
- handle timeouts
- normalize execution results

Does NOT:

- parse tool output
- access database
- create entities
- call AI
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import time


@dataclass(slots=True)
class ToolExecutionResult:
    """
    Result of external tool execution.
    """

    success: bool

    return_code: int

    stdout: str

    stderr: str

    execution_time: float


class ToolRunner:
    """
    Executes external OSINT tools.
    """

    def run(
        self,
        command: list[str],
        timeout: int = 300,
        working_directory: Path | None = None,
        stdin: str | None = None,
    ) -> ToolExecutionResult:
        """
        Execute external command.
        """

        start = time.perf_counter()

        try:

            process = subprocess.run(
                command,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_directory,
                encoding="utf-8",
                errors="replace",
            )

            elapsed = (
                time.perf_counter()
                - start
            )

            return ToolExecutionResult(
                success=process.returncode == 0,
                return_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                execution_time=elapsed,
            )

        except subprocess.TimeoutExpired:

            elapsed = (
                time.perf_counter()
                - start
            )

            return ToolExecutionResult(
                success=False,
                return_code=-1,
                stdout="",
                stderr="Process timeout.",
                execution_time=elapsed,
            )

        except FileNotFoundError:

            elapsed = (
                time.perf_counter()
                - start
            )

            return ToolExecutionResult(
                success=False,
                return_code=-2,
                stdout="",
                stderr="Executable not found.",
                execution_time=elapsed,
            )

        except Exception as exc:

            elapsed = (
                time.perf_counter()
                - start
            )

            return ToolExecutionResult(
                success=False,
                return_code=-999,
                stdout="",
                stderr=str(exc),
                execution_time=elapsed,
            )
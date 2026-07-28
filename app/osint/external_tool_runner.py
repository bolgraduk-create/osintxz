"""
External tool runner.

Provides unified execution
of third-party OSINT tools.

Responsibilities:

- execute subprocesses
- check tool availability
- manage timeouts
- capture stdout/stderr
- execute inside working directory

Does NOT:

- parse tool output
- know specific connectors
- call AI
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ToolExecutionResult:
    """
    Raw execution result.
    """

    success: bool

    return_code: int

    stdout: str

    stderr: str

    execution_time: float

    working_directory: Path | None = None

    error: str | None = None


class ExternalToolRunner:
    """
    Universal subprocess runner.
    """

    def is_available(
        self,
        executable: str,
    ) -> bool:
        """
        Check executable availability.
        """

        return (
            shutil.which(executable)
            is not None
        )

    def run(
        self,
        command: list[str],
        *,
        timeout: int = 300,
        cwd: str | Path | None = None,
    ) -> ToolExecutionResult:
        """
        Execute external tool.
        """

        started = time.perf_counter()

        try:

            process = subprocess.run(

                command,

                capture_output=True,

                text=True,

                timeout=timeout,

                cwd=cwd,

            )

            elapsed = (
                time.perf_counter()
                - started
            )

            return ToolExecutionResult(

                success=(
                    process.returncode == 0
                ),

                return_code=process.returncode,

                stdout=process.stdout,

                stderr=process.stderr,

                execution_time=elapsed,

            )

        except subprocess.TimeoutExpired:

            elapsed = (
                time.perf_counter()
                - started
            )

            return ToolExecutionResult(

                success=False,

                return_code=-1,

                stdout="",

                stderr="",

                execution_time=elapsed,

                error="Execution timeout.",

            )

        except FileNotFoundError:

            elapsed = (
                time.perf_counter()
                - started
            )

            return ToolExecutionResult(

                success=False,

                return_code=-1,

                stdout="",

                stderr="",

                execution_time=elapsed,

                error="Executable not found.",

            )

        except Exception as exc:

            elapsed = (
                time.perf_counter()
                - started
            )

            return ToolExecutionResult(

                success=False,

                return_code=-1,

                stdout="",

                stderr="",

                execution_time=elapsed,

                error=str(exc),

            )

    def run_in_temp_directory(
        self,
        command_builder,
        *,
        timeout: int = 300,
    ) -> tuple[
        ToolExecutionResult,
        Path,
    ]:
        """
        Execute tool inside
        temporary directory.

        command_builder receives
        temporary directory Path.
        """

        with tempfile.TemporaryDirectory() as temp:

            directory = Path(temp)

            command = command_builder(
                directory
            )

            result = self.run(

                command,

                timeout=timeout,

                cwd=directory,

            )

            result.working_directory = (
                directory
            )

            return (
                result,
                directory,
            )
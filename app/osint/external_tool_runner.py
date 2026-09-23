"""Compatibility wrapper for the canonical OSINT ToolRunner.

ExternalToolRunner used to own a second direct subprocess implementation. That
created a security bypass around the R14 runtime policy. It now delegates all
process creation to app.osint.runner.ToolRunner while preserving the historical
result shape used by older connectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile

from app.osint.runner import (
    ToolExecutionResult as CanonicalToolExecutionResult,
    ToolRunner,
)


@dataclass(slots=True)
class ToolExecutionResult:
    """Compatibility result for legacy ExternalToolRunner callers."""

    success: bool
    return_code: int
    stdout: str
    stderr: str
    execution_time: float
    working_directory: Path | None = None
    error: str | None = None
    stopped_early: bool = False
    blocked_by_policy: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    resolved_executable: str | None = None


class ExternalToolRunner:
    """Legacy facade that cannot bypass the canonical runtime policy."""

    def __init__(
        self,
        runner: ToolRunner | None = None,
    ) -> None:
        self.runner = runner or ToolRunner()

    def is_available(
        self,
        executable: str,
    ) -> bool:
        """Check whether an executable is discoverable.

        Availability alone does not grant execution permission. ToolRunner
        performs the authoritative inventory/policy check at launch time.
        """

        return shutil.which(executable) is not None

    def run(
        self,
        command: list[str],
        *,
        timeout: int | float = 300,
        cwd: str | Path | None = None,
    ) -> ToolExecutionResult:
        """Execute through the canonical ToolRunner security boundary."""

        canonical = self.runner.run(
            command=command,
            timeout=timeout,
            working_directory=(
                Path(cwd)
                if cwd is not None
                else None
            ),
        )

        return self._adapt(canonical)

    @staticmethod
    def _adapt(
        result: CanonicalToolExecutionResult,
    ) -> ToolExecutionResult:
        error: str | None = None

        if result.blocked_by_policy:
            error = result.stderr
        elif result.return_code == -1:
            error = "Execution timeout."
        elif result.return_code == -2:
            error = "Executable not found."
        elif result.return_code == -999:
            error = result.stderr or "External tool execution failed."

        return ToolExecutionResult(
            success=result.success,
            return_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            execution_time=result.execution_time,
            error=error,
            stopped_early=result.stopped_early,
            blocked_by_policy=result.blocked_by_policy,
            stdout_truncated=result.stdout_truncated,
            stderr_truncated=result.stderr_truncated,
            resolved_executable=result.resolved_executable,
        )

    def run_in_temp_directory(
        self,
        command_builder,
        *,
        timeout: int | float = 300,
    ) -> tuple[
        ToolExecutionResult,
        Path,
    ]:
        """Execute inside a temporary directory using the canonical runner."""

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

            result.working_directory = directory

            return result, directory

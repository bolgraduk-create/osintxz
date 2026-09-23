"""Security policy for external OSINT tool execution.

All third-party CLI launches pass through this module before subprocess APIs.
The policy is intentionally connector-agnostic and fail-closed.

R14.2a:
- command/input validation;
- timeout and stdin bounds;
- working-directory validation;
- environment override restrictions.

R14.2b:
- explicit executable inventory;
- deterministic executable resolution to an absolute path;
- stdout/stderr capture budgets consumed by ToolRunner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
import shutil
import sys
from typing import Mapping, Sequence

from app.security.tool_execution_inventory import (
    canonical_executable_name,
    is_approved_osint_executable,
)


class ToolExecutionPolicyError(ValueError):
    """Raised when an external-tool launch violates the runtime policy."""


@dataclass(frozen=True, slots=True)
class PreparedToolExecution:
    """Normalized subprocess inputs accepted by ToolExecutionPolicy."""

    command: tuple[str, ...]
    timeout: float
    working_directory: Path | None
    stdin: str | None
    environment_overrides: dict[str, str]
    resolved_executable: Path
    executable_name: str


@dataclass(frozen=True, slots=True)
class ToolExecutionPolicy:
    """Conservative process-launch policy shared by all OSINT CLI tools."""

    max_timeout_seconds: float = 900.0
    max_command_arguments: int = 256
    max_argument_characters: int = 32_768
    max_stdin_bytes: int = 2 * 1024 * 1024
    max_environment_overrides: int = 32
    max_environment_value_characters: int = 32_768

    # Capture limits protect the desktop process from tools that emit
    # unexpectedly large output. ToolRunner keeps draining beyond the limit
    # but discards additional text and marks the result as truncated.
    max_stdout_characters: int = 8 * 1024 * 1024
    max_stderr_characters: int = 2 * 1024 * 1024
    output_read_chunk_characters: int = 8192

    blocked_environment_keys: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "PATH",
                "PATHEXT",
                "COMSPEC",
                "PYTHONHOME",
                "PYTHONPATH",
                "LD_PRELOAD",
                "LD_LIBRARY_PATH",
                "DYLD_INSERT_LIBRARIES",
                "DYLD_LIBRARY_PATH",
            }
        )
    )

    def prepare(
        self,
        *,
        command: Sequence[str | PathLike[str]],
        timeout: int | float,
        working_directory: str | Path | None,
        stdin: str | None,
        environment_overrides: Mapping[str, str] | None,
    ) -> PreparedToolExecution:
        """Validate and normalize one process launch."""

        normalized_command = self._normalize_command(command)
        resolved_executable, executable_name = self._resolve_executable(
            normalized_command[0]
        )

        normalized_command = (
            str(resolved_executable),
            *normalized_command[1:],
        )

        normalized_timeout = self._normalize_timeout(timeout)
        normalized_directory = self._normalize_working_directory(
            working_directory
        )
        normalized_stdin = self._normalize_stdin(stdin)
        normalized_environment = self._normalize_environment(
            environment_overrides
        )

        self._validate_output_limits()

        return PreparedToolExecution(
            command=normalized_command,
            timeout=normalized_timeout,
            working_directory=normalized_directory,
            stdin=normalized_stdin,
            environment_overrides=normalized_environment,
            resolved_executable=resolved_executable,
            executable_name=executable_name,
        )

    def _normalize_command(
        self,
        command: Sequence[str | PathLike[str]],
    ) -> tuple[str, ...]:
        if isinstance(command, (str, bytes)) or not isinstance(
            command, Sequence
        ):
            raise ToolExecutionPolicyError(
                "Command must be a sequence of arguments."
            )

        if not command:
            raise ToolExecutionPolicyError("Command must not be empty.")

        if len(command) > self.max_command_arguments:
            raise ToolExecutionPolicyError(
                "Command contains too many arguments."
            )

        normalized: list[str] = []

        for index, argument in enumerate(command):
            if isinstance(argument, PathLike):
                value = str(argument)
            elif isinstance(argument, str):
                value = argument
            else:
                raise ToolExecutionPolicyError(
                    f"Command argument {index} must be text or a path."
                )

            if "\x00" in value:
                raise ToolExecutionPolicyError(
                    f"Command argument {index} contains a NUL character."
                )

            if len(value) > self.max_argument_characters:
                raise ToolExecutionPolicyError(
                    f"Command argument {index} exceeds the size limit."
                )

            normalized.append(value)

        if not normalized[0].strip():
            raise ToolExecutionPolicyError(
                "Executable argument must not be empty."
            )

        return tuple(normalized)

    def _resolve_executable(
        self,
        raw_executable: str,
    ) -> tuple[Path, str]:
        """Resolve and approve the executable before subprocess launch."""

        requested = str(raw_executable).strip()

        if not requested:
            raise ToolExecutionPolicyError(
                "Executable argument must not be empty."
            )

        current_python = Path(sys.executable).expanduser().resolve()

        candidate: Path | None = None
        requested_path = Path(requested).expanduser()

        # Explicit paths are never searched through PATH.
        if (
            requested_path.is_absolute()
            or requested_path.parent != Path(".")
        ):
            try:
                candidate = requested_path.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise ToolExecutionPolicyError(
                    "Executable path does not exist or cannot be resolved."
                ) from exc
        else:
            resolved = shutil.which(requested)
            if resolved:
                try:
                    candidate = Path(resolved).resolve(strict=True)
                except (OSError, RuntimeError) as exc:
                    raise ToolExecutionPolicyError(
                        "Resolved executable cannot be accessed."
                    ) from exc

        if candidate is None or not candidate.is_file():
            raise ToolExecutionPolicyError(
                f"Executable is not available: {requested}"
            )

        try:
            if candidate.samefile(current_python):
                return candidate, "python-runtime"
        except OSError:
            pass

        if not is_approved_osint_executable(candidate):
            name = canonical_executable_name(candidate)
            raise ToolExecutionPolicyError(
                "Executable is not present in the approved OSINT inventory: "
                f"{name or requested}"
            )

        return candidate, canonical_executable_name(candidate)

    def _normalize_timeout(
        self,
        timeout: int | float,
    ) -> float:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ToolExecutionPolicyError(
                "Process timeout must be numeric."
            )

        value = float(timeout)

        if value <= 0:
            raise ToolExecutionPolicyError(
                "Process timeout must be greater than zero."
            )

        if value > float(self.max_timeout_seconds):
            raise ToolExecutionPolicyError(
                "Process timeout exceeds the runtime policy limit."
            )

        return value

    def _normalize_working_directory(
        self,
        working_directory: str | Path | None,
    ) -> Path | None:
        if working_directory is None:
            return None

        try:
            path = Path(working_directory).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ToolExecutionPolicyError(
                "Working directory does not exist or cannot be resolved."
            ) from exc

        if not path.is_dir():
            raise ToolExecutionPolicyError(
                "Working directory must reference a directory."
            )

        return path

    def _normalize_stdin(
        self,
        stdin: str | None,
    ) -> str | None:
        if stdin is None:
            return None

        if not isinstance(stdin, str):
            raise ToolExecutionPolicyError(
                "Process stdin must be text."
            )

        size = len(stdin.encode("utf-8"))

        if size > self.max_stdin_bytes:
            raise ToolExecutionPolicyError(
                "Process stdin exceeds the runtime policy limit."
            )

        return stdin

    def _normalize_environment(
        self,
        environment_overrides: Mapping[str, str] | None,
    ) -> dict[str, str]:
        if environment_overrides is None:
            return {}

        if not isinstance(environment_overrides, Mapping):
            raise ToolExecutionPolicyError(
                "Environment overrides must be a mapping."
            )

        if len(environment_overrides) > self.max_environment_overrides:
            raise ToolExecutionPolicyError(
                "Too many environment overrides were requested."
            )

        normalized: dict[str, str] = {}

        for raw_key, raw_value in environment_overrides.items():
            key = str(raw_key)
            value = str(raw_value)
            canonical_key = key.strip().upper()

            if not canonical_key:
                raise ToolExecutionPolicyError(
                    "Environment variable names must not be empty."
                )

            if "\x00" in key or "\x00" in value:
                raise ToolExecutionPolicyError(
                    "Environment overrides must not contain NUL characters."
                )

            if canonical_key in self.blocked_environment_keys:
                raise ToolExecutionPolicyError(
                    f"Environment override is blocked by policy: {canonical_key}."
                )

            if len(value) > self.max_environment_value_characters:
                raise ToolExecutionPolicyError(
                    f"Environment override is too large: {canonical_key}."
                )

            normalized[key] = value

        return normalized

    def _validate_output_limits(self) -> None:
        for name, value in (
            ("max_stdout_characters", self.max_stdout_characters),
            ("max_stderr_characters", self.max_stderr_characters),
            (
                "output_read_chunk_characters",
                self.output_read_chunk_characters,
            ),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
            ):
                raise ToolExecutionPolicyError(
                    f"{name} must be an integer greater than zero."
                )


__all__ = [
    "PreparedToolExecution",
    "ToolExecutionPolicy",
    "ToolExecutionPolicyError",
]

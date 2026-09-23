"""OSINT external-tool runner.

All third-party CLI execution flows through this module.

Responsibilities:
- apply ToolExecutionPolicy before process creation;
- execute without a shell;
- resolve executables to approved absolute paths;
- bound in-memory stdout/stderr capture;
- preserve partial output on timeout;
- support bounded streaming by stdout line count;
- terminate the process tree on timeout or controlled early stop.

Does not parse tool-specific output or access the database.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time
from typing import TextIO

from app.security.tool_execution_policy import (
    PreparedToolExecution,
    ToolExecutionPolicy,
    ToolExecutionPolicyError,
)


@dataclass(slots=True)
class ToolExecutionResult:
    """Normalized result of one external-tool execution."""

    success: bool
    return_code: int
    stdout: str
    stderr: str
    execution_time: float
    stopped_early: bool = False
    blocked_by_policy: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    resolved_executable: str | None = None


class _BoundedTextCapture:
    """Keep at most the configured number of characters."""

    __slots__ = ("limit", "_parts", "_size", "truncated")

    def __init__(self, limit: int) -> None:
        self.limit = int(limit)
        self._parts: list[str] = []
        self._size = 0
        self.truncated = False

    @property
    def size(self) -> int:
        return self._size

    def reset(self) -> None:
        self._parts.clear()
        self._size = 0
        self.truncated = False

    def append(self, value: str) -> None:
        if not value:
            return

        remaining = self.limit - self._size

        if remaining <= 0:
            self.truncated = True
            return

        if len(value) > remaining:
            self._parts.append(value[:remaining])
            self._size += remaining
            self.truncated = True
            return

        self._parts.append(value)
        self._size += len(value)

    def getvalue(self) -> str:
        return "".join(self._parts)


_StreamQueue = queue.Queue[tuple[str, str | None]]


def _read_stream_fragments(
    stream: TextIO | None,
    label: str,
    output_queue: _StreamQueue,
    chunk_size: int,
) -> None:
    """Read bounded fragments so one huge line cannot allocate unbounded RAM."""

    if stream is None:
        output_queue.put((label, None))
        return

    try:
        while True:
            fragment = stream.readline(chunk_size)

            if fragment == "":
                break

            output_queue.put((label, fragment))
    finally:
        try:
            stream.close()
        except Exception:
            pass

        output_queue.put((label, None))


def _append_notice(
    value: str,
    notice: str,
    limit: int,
) -> str:
    """Append a diagnostic notice while respecting the configured budget."""

    if not notice:
        return value[:limit]

    separator = "\n" if value else ""
    suffix = f"{separator}{notice}"

    if len(suffix) >= limit:
        return suffix[-limit:]

    allowed_prefix = limit - len(suffix)

    return value[:allowed_prefix] + suffix


class ToolRunner:
    """Execute approved external OSINT tools through one security boundary."""

    def __init__(
        self,
        policy: ToolExecutionPolicy | None = None,
    ) -> None:
        self.policy = policy or ToolExecutionPolicy()

    def run(
        self,
        command: list[str],
        timeout: int | float = 300,
        working_directory: Path | None = None,
        stdin: str | None = None,
        env: dict[str, str] | None = None,
        stdout_line_limit: int | None = None,
    ) -> ToolExecutionResult:
        """Execute one command after policy validation."""

        try:
            prepared = self.policy.prepare(
                command=command,
                timeout=timeout,
                working_directory=working_directory,
                stdin=stdin,
                environment_overrides=env,
            )
        except ToolExecutionPolicyError as exc:
            return ToolExecutionResult(
                success=False,
                return_code=-4,
                stdout="",
                stderr=(
                    "Execution blocked by runtime policy: "
                    f"{exc}"
                ),
                execution_time=0.0,
                blocked_by_policy=True,
            )

        process_env = os.environ.copy()
        process_env.update(prepared.environment_overrides)

        if stdout_line_limit is None:
            return self._run_buffered(
                prepared=prepared,
                process_env=process_env,
            )

        line_limit = max(1, int(stdout_line_limit))

        return self._run_streaming(
            prepared=prepared,
            process_env=process_env,
            stdout_line_limit=line_limit,
        )

    def _spawn(
        self,
        *,
        prepared: PreparedToolExecution,
        process_env: dict[str, str],
    ) -> subprocess.Popen[str]:
        kwargs: dict[str, object] = {
            "args": list(prepared.command),
            "stdin": (
                subprocess.PIPE
                if prepared.stdin is not None
                else subprocess.DEVNULL
            ),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "cwd": prepared.working_directory,
            "encoding": "utf-8",
            "errors": "replace",
            "env": process_env,
            "bufsize": 1,
            "shell": False,
        }

        if os.name == "nt":
            kwargs["creationflags"] = getattr(
                subprocess,
                "CREATE_NEW_PROCESS_GROUP",
                0,
            )
        else:
            kwargs["start_new_session"] = True

        return subprocess.Popen(**kwargs)  # type: ignore[arg-type]

    @staticmethod
    def _write_stdin(
        process: subprocess.Popen[str],
        value: str | None,
    ) -> None:
        if value is None or process.stdin is None:
            return

        try:
            process.stdin.write(value)
            process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass
        finally:
            try:
                process.stdin.close()
            except Exception:
                pass

    @staticmethod
    def _terminate_process_tree(
        process: subprocess.Popen[str],
    ) -> None:
        """Best-effort termination of the process and its descendants."""

        if process.poll() is not None:
            return

        if os.name == "nt":
            try:
                subprocess.run(
                    [
                        "taskkill",
                        "/PID",
                        str(process.pid),
                        "/T",
                        "/F",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                    check=False,
                    shell=False,
                )
            except Exception:
                pass
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass

        try:
            process.wait(timeout=2)
            return
        except Exception:
            pass

        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass

        try:
            process.kill()
        except Exception:
            pass

        try:
            process.wait(timeout=1)
        except Exception:
            pass

    def _start_readers(
        self,
        process: subprocess.Popen[str],
    ) -> tuple[
        _StreamQueue,
        threading.Thread,
        threading.Thread,
    ]:
        output_queue: _StreamQueue = queue.Queue(maxsize=128)
        chunk_size = self.policy.output_read_chunk_characters

        stdout_thread = threading.Thread(
            target=_read_stream_fragments,
            args=(
                process.stdout,
                "stdout",
                output_queue,
                chunk_size,
            ),
            daemon=True,
        )

        stderr_thread = threading.Thread(
            target=_read_stream_fragments,
            args=(
                process.stderr,
                "stderr",
                output_queue,
                chunk_size,
            ),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        return output_queue, stdout_thread, stderr_thread

    @staticmethod
    def _drain_until_readers_finish(
        *,
        output_queue: _StreamQueue,
        stdout_thread: threading.Thread,
        stderr_thread: threading.Thread,
        handler,
        maximum_seconds: float = 1.5,
    ) -> None:
        deadline = time.perf_counter() + maximum_seconds

        while time.perf_counter() < deadline:
            drained = False

            while True:
                try:
                    item = output_queue.get_nowait()
                except queue.Empty:
                    break

                handler(*item)
                drained = True

            if (
                not stdout_thread.is_alive()
                and not stderr_thread.is_alive()
                and output_queue.empty()
            ):
                return

            if not drained:
                time.sleep(0.01)

    def _run_buffered(
        self,
        *,
        prepared: PreparedToolExecution,
        process_env: dict[str, str],
    ) -> ToolExecutionResult:
        start = time.perf_counter()

        try:
            process = self._spawn(
                prepared=prepared,
                process_env=process_env,
            )
        except FileNotFoundError:
            return ToolExecutionResult(
                success=False,
                return_code=-2,
                stdout="",
                stderr="Executable not found.",
                execution_time=time.perf_counter() - start,
                resolved_executable=str(prepared.resolved_executable),
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                return_code=-999,
                stdout="",
                stderr=str(exc),
                execution_time=time.perf_counter() - start,
                resolved_executable=str(prepared.resolved_executable),
            )

        self._write_stdin(process, prepared.stdin)
        output_queue, stdout_thread, stderr_thread = self._start_readers(process)

        stdout_capture = _BoundedTextCapture(self.policy.max_stdout_characters)
        stderr_capture = _BoundedTextCapture(self.policy.max_stderr_characters)
        stdout_done = False
        stderr_done = False
        timed_out = False
        deadline = start + prepared.timeout

        def handle(label: str, fragment: str | None) -> None:
            nonlocal stdout_done, stderr_done

            if fragment is None:
                if label == "stdout":
                    stdout_done = True
                else:
                    stderr_done = True
                return

            if label == "stdout":
                stdout_capture.append(fragment)
            else:
                stderr_capture.append(fragment)

        while True:
            now = time.perf_counter()

            try:
                label, fragment = output_queue.get(timeout=0.03)
                handle(label, fragment)
            except queue.Empty:
                pass

            if process.poll() is not None and stdout_done and stderr_done:
                break

            if process.poll() is None and now >= deadline:
                timed_out = True
                self._terminate_process_tree(process)
                break

        self._drain_until_readers_finish(
            output_queue=output_queue,
            stdout_thread=stdout_thread,
            stderr_thread=stderr_thread,
            handler=handle,
        )

        elapsed = time.perf_counter() - start
        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue()

        if timed_out:
            stderr = _append_notice(
                stderr,
                "Process timeout.",
                self.policy.max_stderr_characters,
            )
            return ToolExecutionResult(
                success=False,
                return_code=-1,
                stdout=stdout,
                stderr=stderr,
                execution_time=elapsed,
                stdout_truncated=stdout_capture.truncated,
                stderr_truncated=stderr_capture.truncated,
                resolved_executable=str(prepared.resolved_executable),
            )

        return_code = process.returncode if process.returncode is not None else -999

        return ToolExecutionResult(
            success=return_code == 0,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            execution_time=elapsed,
            stdout_truncated=stdout_capture.truncated,
            stderr_truncated=stderr_capture.truncated,
            resolved_executable=str(prepared.resolved_executable),
        )

    def _run_streaming(
        self,
        *,
        prepared: PreparedToolExecution,
        process_env: dict[str, str],
        stdout_line_limit: int,
    ) -> ToolExecutionResult:
        start = time.perf_counter()

        try:
            process = self._spawn(
                prepared=prepared,
                process_env=process_env,
            )
        except FileNotFoundError:
            return ToolExecutionResult(
                success=False,
                return_code=-2,
                stdout="",
                stderr="Executable not found.",
                execution_time=time.perf_counter() - start,
                resolved_executable=str(prepared.resolved_executable),
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                return_code=-999,
                stdout="",
                stderr=str(exc),
                execution_time=time.perf_counter() - start,
                resolved_executable=str(prepared.resolved_executable),
            )

        self._write_stdin(process, prepared.stdin)
        output_queue, stdout_thread, stderr_thread = self._start_readers(process)

        stdout_capture = _BoundedTextCapture(self.policy.max_stdout_characters)
        stderr_capture = _BoundedTextCapture(self.policy.max_stderr_characters)
        current_line = _BoundedTextCapture(self.policy.max_stdout_characters)
        current_line_was_truncated = False

        stdout_done = False
        stderr_done = False
        stopped_early = False
        timed_out = False
        accepted_lines = 0
        deadline = start + prepared.timeout

        def finalize_line() -> None:
            nonlocal accepted_lines, stopped_early, current_line_was_truncated

            line = current_line.getvalue().rstrip("\r\n")
            current_line_was_truncated = (
                current_line_was_truncated or current_line.truncated
            )

            if line.strip():
                if accepted_lines:
                    stdout_capture.append("\n")
                stdout_capture.append(line)
                accepted_lines += 1

                if accepted_lines >= stdout_line_limit:
                    stopped_early = True

            current_line.reset()

        def handle(label: str, fragment: str | None) -> None:
            nonlocal stdout_done, stderr_done

            if fragment is None:
                if label == "stdout":
                    if not stopped_early and current_line.size:
                        finalize_line()
                    stdout_done = True
                else:
                    stderr_done = True
                return

            if label == "stderr":
                stderr_capture.append(fragment)
                return

            if stopped_early:
                return

            remaining = fragment

            while remaining and not stopped_early:
                newline_index = remaining.find("\n")

                if newline_index < 0:
                    current_line.append(remaining)
                    return

                piece = remaining[: newline_index + 1]
                current_line.append(piece)
                finalize_line()
                remaining = remaining[newline_index + 1 :]

        while True:
            now = time.perf_counter()

            try:
                label, fragment = output_queue.get(timeout=0.03)
                handle(label, fragment)
            except queue.Empty:
                pass

            if stopped_early:
                self._terminate_process_tree(process)
                break

            if process.poll() is not None and stdout_done and stderr_done:
                break

            if process.poll() is None and now >= deadline:
                timed_out = True
                self._terminate_process_tree(process)
                break

        self._drain_until_readers_finish(
            output_queue=output_queue,
            stdout_thread=stdout_thread,
            stderr_thread=stderr_thread,
            handler=handle,
        )

        elapsed = time.perf_counter() - start
        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue()
        stdout_was_truncated = (
            stdout_capture.truncated
            or current_line_was_truncated
            or current_line.truncated
        )

        if timed_out:
            stderr = _append_notice(
                stderr,
                "Process timeout.",
                self.policy.max_stderr_characters,
            )
            return ToolExecutionResult(
                success=False,
                return_code=-1,
                stdout=stdout,
                stderr=stderr,
                execution_time=elapsed,
                stdout_truncated=stdout_was_truncated,
                stderr_truncated=stderr_capture.truncated,
                resolved_executable=str(prepared.resolved_executable),
            )

        if stopped_early:
            return ToolExecutionResult(
                success=True,
                return_code=-3,
                stdout=stdout,
                stderr=stderr,
                execution_time=elapsed,
                stopped_early=True,
                stdout_truncated=stdout_was_truncated,
                stderr_truncated=stderr_capture.truncated,
                resolved_executable=str(prepared.resolved_executable),
            )

        return_code = process.returncode if process.returncode is not None else -999

        return ToolExecutionResult(
            success=return_code == 0,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            execution_time=elapsed,
            stdout_truncated=stdout_was_truncated,
            stderr_truncated=stderr_capture.truncated,
            resolved_executable=str(prepared.resolved_executable),
        )

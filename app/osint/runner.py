"""
OSINT tool runner.

Executes external OSINT tools
through a unified interface.

Responsibilities:

- execute CLI applications
- collect stdout/stderr
- handle timeouts
- normalize execution results
- optionally stop streaming tools after a bounded number of stdout lines

Does NOT:

- parse tool output
- access database
- create entities
- call AI
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import queue
import subprocess
import threading
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

    stopped_early: bool = False


def _coerce_process_output(
    value: str | bytes | None,
) -> str:
    """
    Normalize output carried by subprocess exceptions.

    ``TimeoutExpired`` may expose bytes even when the original
    process was started in text mode, depending on Python/platform
    details. Keeping the partial output is important for OSINT tools
    that stream findings before the overall command finishes.
    """

    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode(
            "utf-8",
            errors="replace",
        )

    return str(value)


def _read_stream_lines(
    stream,
    label: str,
    output_queue: queue.Queue[
        tuple[str, str]
    ],
) -> None:
    """
    Forward one subprocess text stream into a thread-safe queue.
    """

    try:

        for line in iter(
            stream.readline,
            "",
        ):

            output_queue.put(
                (
                    label,
                    line.rstrip(
                        "\r\n"
                    ),
                )
            )

    finally:

        try:
            stream.close()
        except Exception:
            pass


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
        env: dict[str, str] | None = None,
        stdout_line_limit: int | None = None,
    ) -> ToolExecutionResult:
        """
        Execute external command.

        Optional ``env`` values are merged with the current
        process environment instead of replacing it.

        If a process times out, any stdout/stderr already emitted by
        the tool is preserved. Connectors can therefore return a
        PARTIAL result instead of losing useful discoveries.

        ``stdout_line_limit`` enables controlled streaming execution.
        When the requested number of non-empty stdout lines has been
        collected, the child process is terminated deliberately and
        the result is returned as successful with ``stopped_early=True``.

        Existing callers that do not set ``stdout_line_limit`` retain
        the original buffered subprocess.run behaviour.
        """

        process_env = os.environ.copy()

        if env:
            process_env.update(
                {
                    str(key): str(value)
                    for key, value in env.items()
                }
            )

        if stdout_line_limit is None:

            return self._run_buffered(
                command=command,
                timeout=timeout,
                working_directory=working_directory,
                stdin=stdin,
                process_env=process_env,
            )

        line_limit = max(
            1,
            int(stdout_line_limit),
        )

        return self._run_streaming(
            command=command,
            timeout=timeout,
            working_directory=working_directory,
            stdin=stdin,
            process_env=process_env,
            stdout_line_limit=line_limit,
        )

    @staticmethod
    def _run_buffered(
        *,
        command: list[str],
        timeout: int,
        working_directory: Path | None,
        stdin: str | None,
        process_env: dict[str, str],
    ) -> ToolExecutionResult:

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
                env=process_env,
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

        except subprocess.TimeoutExpired as exc:

            elapsed = (
                time.perf_counter()
                - start
            )

            stdout = _coerce_process_output(
                exc.stdout,
            )

            stderr = _coerce_process_output(
                exc.stderr,
            ).strip()

            if stderr:
                stderr = (
                    f"{stderr}\n"
                    "Process timeout."
                )
            else:
                stderr = "Process timeout."

            return ToolExecutionResult(
                success=False,
                return_code=-1,
                stdout=stdout,
                stderr=stderr,
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

    @staticmethod
    def _terminate_process(
        process: subprocess.Popen,
    ) -> None:

        if process.poll() is not None:
            return

        try:

            process.terminate()

            process.wait(
                timeout=2,
            )

        except Exception:

            try:
                process.kill()
            except Exception:
                pass

    def _run_streaming(
        self,
        *,
        command: list[str],
        timeout: int,
        working_directory: Path | None,
        stdin: str | None,
        process_env: dict[str, str],
        stdout_line_limit: int,
    ) -> ToolExecutionResult:

        start = time.perf_counter()

        try:

            process = subprocess.Popen(
                command,
                stdin=(
                    subprocess.PIPE
                    if stdin is not None
                    else subprocess.DEVNULL
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=working_directory,
                encoding="utf-8",
                errors="replace",
                env=process_env,
                bufsize=1,
            )

        except FileNotFoundError:

            return ToolExecutionResult(
                success=False,
                return_code=-2,
                stdout="",
                stderr="Executable not found.",
                execution_time=(
                    time.perf_counter()
                    - start
                ),
            )

        except Exception as exc:

            return ToolExecutionResult(
                success=False,
                return_code=-999,
                stdout="",
                stderr=str(exc),
                execution_time=(
                    time.perf_counter()
                    - start
                ),
            )

        if (
            stdin is not None
            and process.stdin is not None
        ):

            try:

                process.stdin.write(
                    stdin
                )

                if not stdin.endswith(
                    "\n"
                ):
                    process.stdin.write(
                        "\n"
                    )

                process.stdin.flush()
                process.stdin.close()

            except Exception:
                pass

        output_queue: queue.Queue[
            tuple[str, str]
        ] = queue.Queue()

        stdout_thread = threading.Thread(
            target=_read_stream_lines,
            args=(
                process.stdout,
                "stdout",
                output_queue,
            ),
            daemon=True,
        )

        stderr_thread = threading.Thread(
            target=_read_stream_lines,
            args=(
                process.stderr,
                "stderr",
                output_queue,
            ),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        deadline = (
            start
            + max(
                1,
                float(timeout),
            )
        )

        stopped_early = False
        timed_out = False

        while True:

            now = time.perf_counter()

            try:

                label, line = output_queue.get(
                    timeout=0.03,
                )

                if label == "stdout":

                    if line.strip():

                        stdout_lines.append(
                            line
                        )

                        if (
                            len(stdout_lines)
                            >= stdout_line_limit
                        ):

                            stopped_early = True
                            break

                else:

                    stderr_lines.append(
                        line
                    )

            except queue.Empty:
                pass

            if process.poll() is not None:

                break

            if now >= deadline:

                timed_out = True
                break

        if stopped_early or timed_out:

            self._terminate_process(
                process
            )

        else:

            try:
                process.wait(
                    timeout=1,
                )
            except Exception:
                self._terminate_process(
                    process
                )

        # Drain buffered data. For a controlled early stop, extra stdout
        # generated after the requested line budget is intentionally ignored.
        drain_deadline = (
            time.perf_counter()
            + 0.25
        )

        while (
            time.perf_counter()
            < drain_deadline
        ):

            try:

                label, line = (
                    output_queue.get_nowait()
                )

            except queue.Empty:

                if (
                    not stdout_thread.is_alive()
                    and not stderr_thread.is_alive()
                ):
                    break

                time.sleep(
                    0.01
                )
                continue

            if label == "stderr":

                stderr_lines.append(
                    line
                )

            elif (
                not stopped_early
                and line.strip()
            ):

                stdout_lines.append(
                    line
                )

        elapsed = (
            time.perf_counter()
            - start
        )

        stdout = "\n".join(
            stdout_lines[
                :stdout_line_limit
            ]
            if stopped_early
            else stdout_lines
        )

        stderr = "\n".join(
            stderr_lines
        ).strip()

        if timed_out:

            if stderr:
                stderr = (
                    f"{stderr}\n"
                    "Process timeout."
                )
            else:
                stderr = "Process timeout."

            return ToolExecutionResult(
                success=False,
                return_code=-1,
                stdout=stdout,
                stderr=stderr,
                execution_time=elapsed,
            )

        if stopped_early:

            return ToolExecutionResult(
                success=True,
                return_code=-3,
                stdout=stdout,
                stderr=stderr,
                execution_time=elapsed,
                stopped_early=True,
            )

        return_code = (
            process.returncode
            if process.returncode is not None
            else -999
        )

        return ToolExecutionResult(
            success=return_code == 0,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            execution_time=elapsed,
        )

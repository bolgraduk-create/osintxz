
"""
OSINT Expansion 05D2 — Archive Latency / Streaming Probe

Diagnoses the only failing stage from 05D: archive discovery.

It tests:
- GAU providers individually
- GAU fast combined provider set
- waybackurls
- time to first output
- whether first 3 URLs can be collected before full process completion

No production code changes.
No DB writes.
No vulnerability scanning.
Target: example.com
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import queue
import subprocess
import threading
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "tools" / "osint" / "bin"
OUT = ROOT / "storage" / "cache" / "osint_expansion_05d2"

TARGET = "example.com"
RESULT_LIMIT = 3


@dataclass(slots=True)
class ProbeResult:
    name: str
    command: list[str]
    timeout_seconds: int
    first_output_seconds: float | None
    collected: int
    values: list[str]
    reached_limit: bool
    process_completed_naturally: bool
    exit_code: int | None
    timed_out: bool
    stderr_preview: list[str]
    error: str | None = None


def executable(name: str) -> str:
    path = BIN / f"{name}.exe"

    if not path.exists():
        raise FileNotFoundError(
            f"Missing managed executable: {path}"
        )

    return str(path)


def reader_thread(
    stream,
    output_queue: queue.Queue[tuple[str, str]],
    label: str,
) -> None:
    try:
        for line in iter(stream.readline, ""):
            output_queue.put(
                (
                    label,
                    line.rstrip("\r\n"),
                )
            )
    finally:
        try:
            stream.close()
        except Exception:
            pass


def streaming_probe(
    *,
    name: str,
    command: list[str],
    timeout_seconds: int,
    stdin_text: str | None = None,
) -> ProbeResult:

    started = time.perf_counter()

    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdin=(
            subprocess.PIPE
            if stdin_text is not None
            else subprocess.DEVNULL
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=os.environ.copy(),
    )

    if stdin_text is not None and process.stdin is not None:
        try:
            process.stdin.write(stdin_text)
            process.stdin.flush()
            process.stdin.close()
        except Exception:
            pass

    output_queue: queue.Queue[
        tuple[str, str]
    ] = queue.Queue()

    stdout_thread = threading.Thread(
        target=reader_thread,
        args=(
            process.stdout,
            output_queue,
            "stdout",
        ),
        daemon=True,
    )

    stderr_thread = threading.Thread(
        target=reader_thread,
        args=(
            process.stderr,
            output_queue,
            "stderr",
        ),
        daemon=True,
    )

    stdout_thread.start()
    stderr_thread.start()

    values: list[str] = []
    stderr_lines: list[str] = []

    first_output_seconds: float | None = None
    reached_limit = False
    timed_out = False
    completed_naturally = False

    deadline = (
        started
        + timeout_seconds
    )

    while True:
        now = time.perf_counter()

        while True:
            try:
                label, line = (
                    output_queue.get_nowait()
                )
            except queue.Empty:
                break

            if not line.strip():
                continue

            if label == "stdout":
                if first_output_seconds is None:
                    first_output_seconds = (
                        now - started
                    )

                value = line.strip()

                if value not in values:
                    values.append(
                        value
                    )

                if len(values) >= RESULT_LIMIT:
                    reached_limit = True
                    break
            else:
                if len(stderr_lines) < 20:
                    stderr_lines.append(
                        line.strip()
                    )

        if reached_limit:
            break

        return_code = process.poll()

        if return_code is not None:
            completed_naturally = True

            # Drain any final buffered output.
            drain_until = (
                time.perf_counter()
                + 0.25
            )

            while time.perf_counter() < drain_until:
                try:
                    label, line = output_queue.get(
                        timeout=0.03
                    )
                except queue.Empty:
                    continue

                if not line.strip():
                    continue

                if label == "stdout":
                    if first_output_seconds is None:
                        first_output_seconds = (
                            time.perf_counter()
                            - started
                        )

                    value = line.strip()

                    if value not in values:
                        values.append(
                            value
                        )

                    if len(values) >= RESULT_LIMIT:
                        reached_limit = True
                        break
                elif len(stderr_lines) < 20:
                    stderr_lines.append(
                        line.strip()
                    )

            break

        if now >= deadline:
            timed_out = True
            break

        time.sleep(
            0.03
        )

    if process.poll() is None:
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

    exit_code = process.poll()

    return ProbeResult(
        name=name,
        command=command,
        timeout_seconds=timeout_seconds,
        first_output_seconds=(
            round(
                first_output_seconds,
                3,
            )
            if first_output_seconds is not None
            else None
        ),
        collected=min(
            len(values),
            RESULT_LIMIT,
        ),
        values=values[:RESULT_LIMIT],
        reached_limit=reached_limit,
        process_completed_naturally=completed_naturally,
        exit_code=exit_code,
        timed_out=timed_out,
        stderr_preview=stderr_lines[:10],
    )


def main() -> int:
    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    gau = executable(
        "gau"
    )

    waybackurls = executable(
        "waybackurls"
    )

    probes: list[
        tuple[
            str,
            list[str],
            int,
            str | None,
        ]
    ] = []

    for provider in (
        "wayback",
        "commoncrawl",
        "otx",
        "urlscan",
    ):
        probes.append(
            (
                f"gau:{provider}",
                [
                    gau,
                    "--providers",
                    provider,
                    "--threads",
                    "2",
                    "--timeout",
                    "5",
                    "--retries",
                    "0",
                    TARGET,
                ],
                12,
                None,
            )
        )

    probes.append(
        (
            "gau:wayback+commoncrawl",
            [
                gau,
                "--providers",
                "wayback,commoncrawl",
                "--threads",
                "2",
                "--timeout",
                "5",
                "--retries",
                "0",
                TARGET,
            ],
            15,
            None,
        )
    )

    probes.append(
        (
            "waybackurls",
            [
                waybackurls,
            ],
            25,
            TARGET + "\n",
        )
    )

    print(
        "OSINT Expansion 05D2 — Archive Latency / Streaming Probe",
        flush=True,
    )
    print(
        "=" * 72,
        flush=True,
    )
    print(
        f"Target: {TARGET}",
        flush=True,
    )
    print(
        f"Stop after first {RESULT_LIMIT} unique stdout lines",
        flush=True,
    )
    print(
        "",
        flush=True,
    )

    results: list[
        ProbeResult
    ] = []

    for index, (
        name,
        command,
        timeout_seconds,
        stdin_text,
    ) in enumerate(
        probes,
        start=1,
    ):

        print(
            f"[{index}/{len(probes)}] {name} ...",
            flush=True,
        )

        try:
            result = streaming_probe(
                name=name,
                command=command,
                timeout_seconds=timeout_seconds,
                stdin_text=stdin_text,
            )
        except Exception as exc:
            result = ProbeResult(
                name=name,
                command=command,
                timeout_seconds=timeout_seconds,
                first_output_seconds=None,
                collected=0,
                values=[],
                reached_limit=False,
                process_completed_naturally=False,
                exit_code=None,
                timed_out=False,
                stderr_preview=[],
                error=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        results.append(
            result
        )

        print(
            "      "
            f"first={result.first_output_seconds}s "
            f"collected={result.collected} "
            f"limit={result.reached_limit} "
            f"natural={result.process_completed_naturally} "
            f"timeout={result.timed_out} "
            f"exit={result.exit_code}",
            flush=True,
        )

        if result.error:
            print(
                f"      error: {result.error}",
                flush=True,
            )

        for value in result.values:
            print(
                f"      -> {value[:220]}",
                flush=True,
            )

        for line in result.stderr_preview[:2]:
            print(
                f"      stderr: {line[:220]}",
                flush=True,
            )

    payload = {
        "probe_version": 1,
        "target": TARGET,
        "result_limit": RESULT_LIMIT,
        "results": [
            asdict(result)
            for result in results
        ],
        "notes": [
            "Processes are terminated after 3 unique stdout lines.",
            "No production code is modified.",
            "No DB writes or persistence are performed.",
            "This probe identifies whether archive tools are suitable for streaming early-stop execution.",
        ],
    }

    json_path = (
        OUT
        / "archive_latency_probe.json"
    )

    json_path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    streamable = [
        result.name
        for result in results
        if result.reached_limit
    ]

    no_output = [
        result.name
        for result in results
        if result.collected == 0
    ]

    print(
        "",
        flush=True,
    )
    print(
        "SUMMARY",
        flush=True,
    )
    print(
        "-" * 72,
        flush=True,
    )
    print(
        "streamable_to_limit="
        + (
            ",".join(
                streamable
            )
            if streamable
            else "none"
        ),
        flush=True,
    )
    print(
        "no_output="
        + (
            ",".join(
                no_output
            )
            if no_output
            else "none"
        ),
        flush=True,
    )
    print(
        f"JSON: {json_path}",
        flush=True,
    )
    print(
        "",
        flush=True,
    )
    print(
        "OSINT EXPANSION 05D2 ARCHIVE LATENCY PROBE: PASS",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

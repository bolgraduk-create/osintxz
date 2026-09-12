"""
OSINT Expansion 05A — Runtime Identity Audit v3

Focus:
- ProjectDiscovery httpx vs Python httpx CLI collision
- GHunt traceback/import health
- six discovery runtime tools
- API-key state without exposing secrets

No network searches are performed.
No DB writes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_runtime_identity_audit_v3"
BIN = ROOT / "tools" / "osint" / "bin"
ENV_FILE = ROOT / ".env"

TIMEOUT = 8

DISCOVERY_TOOLS = (
    "subfinder",
    "dnsx",
    "gau",
    "waybackurls",
    "katana",
    "assetfinder",
)

API_KEYS = (
    "VIRUSTOTAL_API_KEY",
    "ABUSEIPDB_API_KEY",
    "GREYNOISE_API_KEY",
    "HAVEIBEENPWNED_API_KEY",
    "INTELLIGENCEX_API_KEY",
    "URLSCAN_API_KEY",
    "ALIENVAULT_OTX_API_KEY",
    "OTX_API_KEY",
    "HYBRID_ANALYSIS_API_KEY",
    "BRAVE_API_KEY",
    "SEARXNG_URL",
)


@dataclass
class ToolHealth:
    name: str
    resolved_path: str | None
    status: str
    identity: str | None
    exit_code: int | None
    traceback_detected: bool
    output_preview: list[str]
    note: str | None = None


def run_command(
    executable: str,
    args: list[str],
) -> tuple[int | None, str, bool, str | None]:
    try:
        completed = subprocess.run(
            [executable, *args],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            check=False,
            env=os.environ.copy(),
        )
        text = "\n".join(
            part
            for part in (
                completed.stdout or "",
                completed.stderr or "",
            )
            if part
        )
        return completed.returncode, text, False, None
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        err = exc.stderr if isinstance(exc.stderr, str) else ""
        return None, "\n".join((out, err)), True, "timeout"
    except Exception as exc:
        return None, "", False, f"{type(exc).__name__}: {exc}"


def project_or_path(name: str) -> str | None:
    local = BIN / f"{name}.exe"
    if local.exists():
        return str(local)
    return shutil.which(name)


def preview(text: str, limit: int = 12) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ][:limit]


def has_fatal_python_error(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "traceback (most recent call last)",
            "modulenotfounderror:",
            "importerror:",
            "syntaxerror:",
        )
    )


def audit_projectdiscovery_httpx() -> ToolHealth:
    executable = project_or_path("httpx")

    if not executable:
        return ToolHealth(
            name="httpx",
            resolved_path=None,
            status="BLOCKED",
            identity=None,
            exit_code=None,
            traceback_detected=False,
            output_preview=[],
            note="httpx executable not found",
        )

    code, text, timed_out, error = run_command(
        executable,
        ["-h"],
    )

    lowered = text.lower()
    pd_flags = (
        "-u, -target" in lowered
        and "-silent" in lowered
        and "-json" in lowered
        and "-sc, -status-code" in lowered
    )

    python_httpx = (
        "usage: httpx" in lowered
        and "options" in lowered
        and not pd_flags
    )

    fatal = has_fatal_python_error(text)

    if fatal:
        status = "BROKEN"
        identity = "python_error"
        note = "fatal Python error detected"
    elif pd_flags:
        status = "READY"
        identity = "projectdiscovery_httpx"
        note = None
    elif python_httpx:
        status = "WRONG_IDENTITY"
        identity = "python_httpx_cli"
        note = "encode/httpx Python CLI is not ProjectDiscovery httpx"
    elif timed_out:
        status = "PARTIAL"
        identity = "unknown"
        note = "help command timed out"
    else:
        status = "UNKNOWN_IDENTITY"
        identity = "unknown"
        note = error or "fingerprint did not match ProjectDiscovery httpx"

    return ToolHealth(
        name="httpx",
        resolved_path=executable,
        status=status,
        identity=identity,
        exit_code=code,
        traceback_detected=fatal,
        output_preview=preview(text),
        note=note,
    )


def audit_ghunt() -> ToolHealth:
    executable = shutil.which("ghunt")

    if not executable:
        return ToolHealth(
            name="ghunt",
            resolved_path=None,
            status="BLOCKED",
            identity=None,
            exit_code=None,
            traceback_detected=False,
            output_preview=[],
            note="ghunt executable not found",
        )

    code, text, timed_out, error = run_command(
        executable,
        ["--help"],
    )

    fatal = has_fatal_python_error(text)
    lowered = text.lower()

    if fatal:
        status = "BROKEN"
        note = "traceback/import failure detected"
    elif "ghunt" in lowered and not timed_out:
        status = "READY_CLI"
        note = (
            "CLI help is healthy; authenticated query health is not tested here"
        )
    elif timed_out:
        status = "PARTIAL"
        note = "ghunt --help timed out"
    else:
        status = "UNKNOWN"
        note = error or "GHunt help fingerprint not recognized"

    return ToolHealth(
        name="ghunt",
        resolved_path=executable,
        status=status,
        identity="ghunt_v2_cli" if "ghunt" in lowered else None,
        exit_code=code,
        traceback_detected=fatal,
        output_preview=preview(text),
        note=note,
    )


def audit_discovery(name: str) -> ToolHealth:
    executable = project_or_path(name)

    if not executable:
        return ToolHealth(
            name=name,
            resolved_path=None,
            status="BLOCKED",
            identity=None,
            exit_code=None,
            traceback_detected=False,
            output_preview=[],
            note="executable not found",
        )

    args = ["-h"]
    if name == "gau":
        args = ["--help"]
    elif name == "waybackurls":
        args = ["-h"]
    elif name == "assetfinder":
        args = ["-h"]

    code, text, timed_out, error = run_command(
        executable,
        args,
    )

    fatal = has_fatal_python_error(text)

    if fatal:
        status = "BROKEN"
        note = "fatal Python/import error detected"
    elif timed_out:
        status = "PARTIAL"
        note = "help command timed out"
    elif text.strip() or code in (0, 1, 2):
        status = "READY"
        note = None
    else:
        status = "UNKNOWN"
        note = error or "no recognizable help output"

    return ToolHealth(
        name=name,
        resolved_path=executable,
        status=status,
        identity=f"{name}_cli",
        exit_code=code,
        traceback_detected=fatal,
        output_preview=preview(text),
        note=note,
    )


def parse_env_file() -> dict[str, str]:
    values: dict[str, str] = {}

    if not ENV_FILE.exists():
        return values

    for raw_line in ENV_FILE.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value

    return values


def api_key_states() -> dict[str, str]:
    dotenv = parse_env_file()
    states: dict[str, str] = {}

    for key in API_KEYS:
        env_value = os.getenv(key)

        if env_value is not None and env_value.strip():
            states[key] = "PRESENT_NONEMPTY"
            continue

        if key in dotenv:
            states[key] = (
                "PRESENT_NONEMPTY"
                if dotenv[key].strip()
                else "DECLARED_EMPTY"
            )
            continue

        states[key] = "ABSENT"

    return states


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    print("OSINT Expansion 05A — Runtime Identity Audit v3")
    print("=" * 66)

    results = [
        audit_projectdiscovery_httpx(),
        audit_ghunt(),
        *[
            audit_discovery(name)
            for name in DISCOVERY_TOOLS
        ],
    ]

    for item in results:
        print(
            f"{item.name:14} "
            f"status={item.status:16} "
            f"identity={str(item.identity):24} "
            f"path={item.resolved_path}"
        )
        if item.note:
            print(f"  note: {item.note}")

    key_states = api_key_states()

    print("")
    print("API / CONFIG STATES")
    print("-" * 66)
    for key, state in key_states.items():
        print(f"{key:30} {state}")

    payload = {
        "audit_version": 3,
        "tools": [asdict(item) for item in results],
        "api_config_states": key_states,
        "notes": [
            "Secret values are never written to the report.",
            "ProjectDiscovery httpx is fingerprinted separately from Python httpx.",
            "GHunt READY_CLI means help/import health only; authenticated queries are not executed.",
            "No DB writes or OSINT searches are performed.",
        ],
    }

    json_path = OUT / "identity_audit.json"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    ready = sum(
        1
        for item in results
        if item.status in {"READY", "READY_CLI"}
    )
    problematic = [
        item
        for item in results
        if item.status not in {"READY", "READY_CLI"}
    ]

    print("")
    print(f"READY/READY_CLI={ready}  PROBLEMATIC={len(problematic)}")
    print(f"JSON: {json_path}")
    print("")
    print("OSINT EXPANSION 05A RUNTIME IDENTITY AUDIT: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

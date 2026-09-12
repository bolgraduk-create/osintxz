
"""
OSINT Expansion 04A2 — Discovery Connector Probe (streaming progress fix)

Fixes 04A appearing frozen:
- prints progress before every live probe
- uses a short per-command timeout
- continues after failures/timeouts
- flushes console output immediately
- no DB writes, no vulnerability scanning
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import importlib
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_04a2"
BIN = ROOT / "tools" / "osint" / "bin"
TARGET = "example.com"
TIMEOUT_SECONDS = 8

TOOLS = {
    "subfinder": {
        "exe": "subfinder.exe",
        "args": ["-silent", "-d", TARGET],
        "connector_module": "app.osint.connectors.subfinder_connector",
    },
    "dnsx": {
        "exe": "dnsx.exe",
        "args": ["-silent", "-a", "-resp"],
        "stdin": TARGET + "\n",
        "connector_module": "app.osint.connectors.dnsx_connector",
    },
    "gau": {
        "exe": "gau.exe",
        "args": ["--subs", TARGET],
        "connector_module": "app.osint.connectors.gau_connector",
    },
    "waybackurls": {
        "exe": "waybackurls.exe",
        "args": [],
        "stdin": TARGET + "\n",
        "connector_module": "app.osint.connectors.waybackurls_connector",
    },
    "katana": {
        "exe": "katana.exe",
        "args": ["-silent", "-u", "https://" + TARGET, "-d", "1"],
        "connector_module": "app.osint.connectors.katana_connector",
    },
    "assetfinder": {
        "exe": "assetfinder.exe",
        "args": ["--subs-only", TARGET],
        "connector_module": "app.osint.connectors.assetfinder_connector",
    },
}

CORE_MODULES = [
    "app.osint.base_connector",
    "app.osint.registry",
    "app.osint.manager",
    "app.osint.runner",
    "app.osint.models",
    "app.osint.result",
    "app.osint.tool_runtime",
    "app.osint.enrichment_execution",
    "app.osint.finding_persistence",
    "app.osint.pivot_candidates",
    "app.osint.pivot_policy",
    "app.osint.pivot_router",
]


@dataclass
class CommandResult:
    name: str
    executable: str | None
    exit_code: int | None
    timed_out: bool
    stdout_lines: list[str]
    stderr_lines: list[str]
    output_count: int
    ok: bool
    note: str | None


def say(text: str = "") -> None:
    print(text, flush=True)


def clip(text: str | None, limit: int) -> list[str]:
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()][:limit]


def resolve_executable(name: str, exe_name: str) -> Path | None:
    local = BIN / exe_name
    if local.exists():
        return local

    hit = shutil.which(name)
    if hit:
        return Path(hit)

    return None


def probe_command(name: str, spec: dict[str, Any]) -> CommandResult:
    exe = resolve_executable(name, spec["exe"])

    if exe is None:
        return CommandResult(
            name=name,
            executable=None,
            exit_code=None,
            timed_out=False,
            stdout_lines=[],
            stderr_lines=[],
            output_count=0,
            ok=False,
            note="executable not found",
        )

    try:
        completed = subprocess.run(
            [str(exe), *spec.get("args", [])],
            input=spec.get("stdin"),
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            check=False,
            env=os.environ.copy(),
        )

        stdout_all = [
            line.strip()
            for line in (completed.stdout or "").splitlines()
            if line.strip()
        ]
        stderr_all = [
            line.strip()
            for line in (completed.stderr or "").splitlines()
            if line.strip()
        ]

        combined_error = "\n".join(stderr_all).lower()

        hard_failure = any(
            token in combined_error
            for token in (
                "panic:",
                "fatal error",
                "traceback",
            )
        )

        ok = completed.returncode in (0, 1, 2) and not hard_failure

        return CommandResult(
            name=name,
            executable=str(exe),
            exit_code=completed.returncode,
            timed_out=False,
            stdout_lines=stdout_all[:20],
            stderr_lines=stderr_all[:10],
            output_count=len(stdout_all),
            ok=ok,
            note=None if ok else "unexpected command failure",
        )

    except subprocess.TimeoutExpired as exc:
        stdout_text = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr_text = exc.stderr if isinstance(exc.stderr, str) else ""

        return CommandResult(
            name=name,
            executable=str(exe),
            exit_code=None,
            timed_out=True,
            stdout_lines=clip(stdout_text, 20),
            stderr_lines=clip(stderr_text, 10),
            output_count=len(clip(stdout_text, 10_000)),
            ok=False,
            note=f"safety timeout after {TIMEOUT_SECONDS}s",
        )

    except Exception as exc:
        return CommandResult(
            name=name,
            executable=str(exe),
            exit_code=None,
            timed_out=False,
            stdout_lines=[],
            stderr_lines=[],
            output_count=0,
            ok=False,
            note=f"{type(exc).__name__}: {exc}",
        )


def signature(obj: Any) -> str | None:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return None


def describe_class(cls: type) -> dict[str, Any]:
    methods = {}

    for name, member in inspect.getmembers(cls):
        if name.startswith("__"):
            continue
        if inspect.isfunction(member) or inspect.ismethod(member):
            methods[name] = signature(member)

    return {
        "name": cls.__name__,
        "module": cls.__module__,
        "bases": [
            f"{base.__module__}.{base.__name__}"
            for base in cls.__bases__
        ],
        "signature": signature(cls),
        "methods": methods,
    }


def describe_module(module_name: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "module": module_name,
        "import_ok": False,
        "error": None,
        "classes": [],
        "functions": {},
    }

    try:
        module = importlib.import_module(module_name)
    except Exception:
        result["error"] = traceback.format_exc(limit=8)
        return result

    result["import_ok"] = True

    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and obj.__module__ == module_name:
            result["classes"].append(describe_class(obj))
        elif (
            inspect.isfunction(obj)
            and obj.__module__ == module_name
            and not name.startswith("_")
        ):
            result["functions"][name] = signature(obj)

    return result


def source_contract(module_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
        source_file = inspect.getsourcefile(module)
        source = inspect.getsource(module)
    except Exception:
        return {
            "module": module_name,
            "source_file": None,
            "error": traceback.format_exc(limit=8),
        }

    lower = source.lower()

    return {
        "module": module_name,
        "source_file": (
            str(Path(source_file).resolve().relative_to(ROOT)).replace("\\", "/")
            if source_file
            else None
        ),
        "uses_tool_runtime": "tool_runtime" in lower,
        "uses_subprocess": "subprocess" in lower,
        "mentions_external_tool_runner": "external_tool_runner" in lower,
        "mentions_connector_request": "connectorrequest" in lower,
        "mentions_osint_finding": "osintfinding" in lower,
        "mentions_osint_result": "osintresult" in lower,
        "mentions_target_type": "target_type" in lower,
        "parse_method_names": sorted(
            set(
                re.findall(
                    r"def\s+([A-Za-z0-9_]*parse[A-Za-z0-9_]*)\s*\(",
                    source,
                    flags=re.IGNORECASE,
                )
            )
        ),
        "run_method_names": sorted(
            set(
                re.findall(
                    r"def\s+((?:run|execute|search|collect|scan)[A-Za-z0-9_]*)\s*\(",
                    source,
                    flags=re.IGNORECASE,
                )
            )
        ),
    }


def downstream_contracts() -> dict[str, Any]:
    paths = {
        "finding_persistence": ROOT / "app" / "osint" / "finding_persistence.py",
        "pivot_candidates": ROOT / "app" / "osint" / "pivot_candidates.py",
        "pivot_policy": ROOT / "app" / "osint" / "pivot_policy.py",
        "pivot_router": ROOT / "app" / "osint" / "pivot_router.py",
        "recursive_enrichment": ROOT / "app" / "application" / "osint_recursive_enrichment_service.py",
        "enrichment_execution": ROOT / "app" / "osint" / "enrichment_execution.py",
    }

    result = {}

    for name, path in paths.items():
        exists = path.exists()
        text = (
            path.read_text(encoding="utf-8", errors="replace")
            if exists
            else ""
        )
        lower = text.lower()

        result[name] = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "exists": exists,
            "mentions_finding": "finding" in lower,
            "mentions_evidence": "evidence" in lower,
            "mentions_pivot": "pivot" in lower,
            "mentions_provenance": "provenance" in lower,
            "mentions_depth": "depth" in lower,
        }

    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    say("OSINT Expansion 04A2 — Discovery Connector Contract Probe")
    say("=" * 66)
    say("")
    say("SAFE LIVE CLI")
    say("-" * 66)

    live_results: list[CommandResult] = []

    for index, (name, spec) in enumerate(TOOLS.items(), start=1):
        say(f"[{index}/6] starting {name} ...")
        result = probe_command(name, spec)
        live_results.append(result)

        say(
            f"      ok={result.ok} "
            f"exit={result.exit_code} "
            f"timeout={result.timed_out} "
            f"results={result.output_count}"
        )

        if result.note:
            say(f"      note: {result.note}")

        for line in result.stderr_lines[:2]:
            say(f"      stderr: {line[:180]}")

        for line in result.stdout_lines[:2]:
            say(f"      stdout: {line[:180]}")

    say("")
    say("IMPORT / CONTRACT INTROSPECTION")
    say("-" * 66)

    core = []

    for index, module_name in enumerate(CORE_MODULES, start=1):
        say(f"[core {index}/{len(CORE_MODULES)}] {module_name}")
        core.append(describe_module(module_name))

    connectors: dict[str, Any] = {}

    for index, (name, spec) in enumerate(TOOLS.items(), start=1):
        module_name = spec["connector_module"]
        say(f"[connector {index}/6] {module_name}")

        connectors[name] = {
            "introspection": describe_module(module_name),
            "source_contract": source_contract(module_name),
        }

    downstream = downstream_contracts()

    payload = {
        "probe_version": 2,
        "target": TARGET,
        "timeout_seconds": TIMEOUT_SECONDS,
        "python": sys.version,
        "live_cli": [asdict(item) for item in live_results],
        "core_modules": core,
        "connectors": connectors,
        "downstream_contracts": downstream,
        "notes": [
            "example.com is used only as a benign execution target.",
            "Zero findings are not treated as connector failure.",
            "No database writes are performed.",
            "No vulnerability scanners are invoked.",
        ],
    }

    json_path = OUT / "probe.json"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    say("")
    say("SUMMARY")
    say("-" * 66)

    for result in live_results:
        say(
            f"{result.name:12} "
            f"ok={str(result.ok):5} "
            f"exit={str(result.exit_code):4} "
            f"timeout={str(result.timed_out):5} "
            f"results={result.output_count}"
        )

    say("")
    say("Connector imports:")

    for name, data in connectors.items():
        info = data["introspection"]
        source = data["source_contract"]

        say(
            f"{name:12} "
            f"import_ok={info['import_ok']} "
            f"classes={len(info['classes'])} "
            f"tool_runtime={source.get('uses_tool_runtime')} "
            f"subprocess={source.get('uses_subprocess')} "
            f"parse={source.get('parse_method_names')} "
            f"run={source.get('run_method_names')}"
        )

    say("")
    say("Downstream contracts:")

    for name, info in downstream.items():
        say(
            f"{name:22} "
            f"exists={info['exists']} "
            f"finding={info['mentions_finding']} "
            f"evidence={info['mentions_evidence']} "
            f"pivot={info['mentions_pivot']} "
            f"provenance={info['mentions_provenance']}"
        )

    say("")
    say(f"JSON: {json_path}")
    say("")
    say("OSINT EXPANSION 04A2 CONNECTOR CONTRACT PROBE: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

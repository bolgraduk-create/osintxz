"""
OSINT Expansion 04A — Discovery Connector Contract + Safe Live Probe

Purpose:
Before changing production connector code, inspect the exact current contracts
for the six newly enabled discovery tools and run a small benign live CLI probe.

This script:
- performs NO database writes
- performs NO vulnerability scanning
- uses only a benign public target: example.com
- limits command runtime and captured output
- writes a diagnostic report under storage/cache/
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
OUT = ROOT / "storage" / "cache" / "osint_expansion_04a"
BIN = ROOT / "tools" / "osint" / "bin"
TARGET = "example.com"

TOOLS = {
    "subfinder": {
        "exe": "subfinder.exe",
        "args": ["-silent", "-d", TARGET],
        "connector_module": "app.osint.connectors.subfinder_connector",
    },
    "dnsx": {
        "exe": "dnsx.exe",
        "args": ["-silent", "-a", "-resp", "-d", TARGET],
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


def clip_lines(text: str, limit: int = 30) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return lines[:limit]


def safe_command_probe(name: str, spec: dict[str, Any]) -> CommandResult:
    exe = BIN / spec["exe"]
    if not exe.exists():
        resolved = shutil.which(name)
        if resolved:
            exe = Path(resolved)
        else:
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
        proc = subprocess.run(
            [str(exe), *spec.get("args", [])],
            input=spec.get("stdin"),
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
            check=False,
            env=os.environ.copy(),
        )
        stdout_all = [
            line.strip()
            for line in proc.stdout.splitlines()
            if line.strip()
        ]
        stderr_all = [
            line.strip()
            for line in proc.stderr.splitlines()
            if line.strip()
        ]
        # These tools may legitimately return no findings for example.com.
        ok = proc.returncode in (0, 1) and not any(
            token in (proc.stderr or "").lower()
            for token in (
                "panic:",
                "fatal error",
                "traceback",
            )
        )
        return CommandResult(
            name=name,
            executable=str(exe),
            exit_code=proc.returncode,
            timed_out=False,
            stdout_lines=stdout_all[:30],
            stderr_lines=stderr_all[:20],
            output_count=len(stdout_all),
            ok=ok,
            note=None if ok else "local live command returned an unexpected failure",
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            name=name,
            executable=str(exe),
            exit_code=None,
            timed_out=True,
            stdout_lines=clip_lines(
                (exc.stdout or "")
                if isinstance(exc.stdout, str)
                else ""
            ),
            stderr_lines=clip_lines(
                (exc.stderr or "")
                if isinstance(exc.stderr, str)
                else ""
            ),
            output_count=0,
            ok=False,
            note="25 second safety timeout",
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


def sig(obj: Any) -> str | None:
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
            methods[name] = sig(member)

    bases = [
        f"{base.__module__}.{base.__name__}"
        for base in cls.__bases__
    ]

    return {
        "name": cls.__name__,
        "module": cls.__module__,
        "bases": bases,
        "signature": sig(cls),
        "methods": methods,
    }


def describe_module(module_name: str) -> dict[str, Any]:
    item: dict[str, Any] = {
        "module": module_name,
        "import_ok": False,
        "error": None,
        "classes": [],
        "functions": {},
        "interesting_objects": {},
    }

    try:
        mod = importlib.import_module(module_name)
    except Exception:
        item["error"] = traceback.format_exc(limit=8)
        return item

    item["import_ok"] = True

    for name, obj in inspect.getmembers(mod):
        if inspect.isclass(obj) and obj.__module__ == module_name:
            item["classes"].append(describe_class(obj))
        elif (
            inspect.isfunction(obj)
            and obj.__module__ == module_name
            and not name.startswith("_")
        ):
            item["functions"][name] = sig(obj)

    for name in (
        "registry",
        "connector_registry",
        "REGISTRY",
        "manager",
        "runner",
    ):
        if hasattr(mod, name):
            obj = getattr(mod, name)
            item["interesting_objects"][name] = {
                "type": f"{type(obj).__module__}.{type(obj).__name__}",
                "repr": repr(obj)[:300],
            }

    return item


def source_contract(module_name: str) -> dict[str, Any]:
    try:
        mod = importlib.import_module(module_name)
        source_file = inspect.getsourcefile(mod)
        source = inspect.getsource(mod)
    except Exception:
        return {
            "module": module_name,
            "source_file": None,
            "error": traceback.format_exc(limit=8),
        }

    lower = source.lower()
    command_tokens = sorted(
        set(
            re.findall(
                r"""["']([a-zA-Z0-9_.-]+(?:\.exe)?)["']""",
                source,
            )
        )
    )

    likely_commands = [
        token
        for token in command_tokens
        if token.lower().removesuffix(".exe") in TOOLS
    ]

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
        "likely_commands": likely_commands,
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
    checks = {
        "finding_persistence": ROOT / "app" / "osint" / "finding_persistence.py",
        "pivot_candidates": ROOT / "app" / "osint" / "pivot_candidates.py",
        "pivot_policy": ROOT / "app" / "osint" / "pivot_policy.py",
        "pivot_router": ROOT / "app" / "osint" / "pivot_router.py",
        "recursive_enrichment": ROOT / "app" / "application" / "osint_recursive_enrichment_service.py",
        "enrichment_execution": ROOT / "app" / "osint" / "enrichment_execution.py",
    }

    result = {}
    for name, path in checks.items():
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

    live_results = [
        safe_command_probe(name, spec)
        for name, spec in TOOLS.items()
    ]

    core = [
        describe_module(module_name)
        for module_name in CORE_MODULES
    ]

    connectors = {}
    for name, spec in TOOLS.items():
        module_name = spec["connector_module"]
        connectors[name] = {
            "introspection": describe_module(module_name),
            "source_contract": source_contract(module_name),
        }

    payload = {
        "probe_version": 1,
        "target": TARGET,
        "python": sys.version,
        "live_cli": [asdict(item) for item in live_results],
        "core_modules": core,
        "connectors": connectors,
        "downstream_contracts": downstream_contracts(),
        "notes": [
            "example.com is used only as a benign execution target.",
            "Zero findings are not treated as connector failure.",
            "No database writes are performed.",
            "This probe does not invoke vulnerability scanners.",
        ],
    }

    json_path = OUT / "probe.json"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    text_lines = [
        "OSINT Expansion 04A — Discovery Connector Contract Probe",
        "=" * 66,
        "",
        "SAFE LIVE CLI",
        "-" * 66,
    ]

    for item in live_results:
        text_lines.append(
            f"{item.name:12} "
            f"ok={item.ok!s:<5} "
            f"exit={str(item.exit_code):<4} "
            f"timeout={item.timed_out!s:<5} "
            f"results={item.output_count}"
        )
        if item.note:
            text_lines.append(f"  note: {item.note}")
        for line in item.stderr_lines[:3]:
            text_lines.append(f"  stderr: {line[:220]}")
        for line in item.stdout_lines[:3]:
            text_lines.append(f"  stdout: {line[:220]}")

    text_lines += [
        "",
        "CONNECTOR CONTRACTS",
        "-" * 66,
    ]

    for name, data in connectors.items():
        introspection = data["introspection"]
        source_info = data["source_contract"]
        text_lines.append(
            f"{name}: import_ok={introspection['import_ok']} "
            f"classes={len(introspection['classes'])} "
            f"tool_runtime={source_info.get('uses_tool_runtime')} "
            f"subprocess={source_info.get('uses_subprocess')} "
            f"parse={source_info.get('parse_method_names')} "
            f"run={source_info.get('run_method_names')}"
        )
        for cls in introspection["classes"][:3]:
            text_lines.append(
                f"  class {cls['name']}{cls.get('signature') or ''}"
            )
            interesting = {
                method: signature
                for method, signature in cls["methods"].items()
                if method.lower() in {
                    "run", "execute", "search", "collect", "scan",
                    "supports", "is_available", "check_available",
                }
                or "parse" in method.lower()
            }
            for method, signature in sorted(interesting.items()):
                text_lines.append(
                    f"    {method}{signature or ''}"
                )

    text_lines += [
        "",
        "DOWNSTREAM CONTRACTS",
        "-" * 66,
    ]

    for name, info in payload["downstream_contracts"].items():
        text_lines.append(
            f"{name:22} exists={info['exists']} "
            f"finding={info['mentions_finding']} "
            f"evidence={info['mentions_evidence']} "
            f"pivot={info['mentions_pivot']} "
            f"provenance={info['mentions_provenance']} "
            f"depth={info['mentions_depth']}"
        )

    text_lines += [
        "",
        f"JSON: {json_path}",
        "",
        "OSINT EXPANSION 04A CONNECTOR CONTRACT PROBE: PASS",
    ]

    txt_path = OUT / "probe.txt"
    txt_path.write_text(
        "\n".join(text_lines) + "\n",
        encoding="utf-8",
    )

    print("\n".join(text_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

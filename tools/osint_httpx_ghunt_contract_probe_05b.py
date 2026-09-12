
"""
OSINT Expansion 05B — HTTPX/GHunt Production Contract Probe

Purpose:
1. Execute the application's current httpx connector against a benign target.
2. Inspect the current GHunt connector without performing account OSINT.
3. Bundle the exact relevant production source files for a minimal 05C patch.

Safety:
- benign target: https://example.com
- no DB writes
- no persistence
- no recursive enrichment
- no vulnerability scanning
- no GHunt account queries
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, is_dataclass
import enum
import importlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_05b"
BIN = ROOT / "tools" / "osint" / "bin"

HTTPX_MODULE = "app.osint.connectors.httpx_connector"
GHUNT_MODULE_CANDIDATES = (
    "app.osint.connectors.ghunt_connector",
    "app.osint.connectors.ghunt",
)

TARGET_VALUE = "https://example.com"
REQUEST_LIMIT = 5
REQUEST_TIMEOUT = 20
HARD_TIMEOUT = 28

SOURCE_PATHS = [
    "app/osint/connectors/httpx_connector.py",
    "app/osint/connectors/ghunt_connector.py",
    "app/osint/tool_runtime.py",
    "app/osint/runner.py",
    "app/osint/models.py",
    "app/osint/result.py",
    "app/osint/base_connector.py",
    "app/osint/registry.py",
    "app/osint/manager.py",
    "app/osint/pipeline.py",
]


def say(text: str = "") -> None:
    print(text, flush=True)


def jsonable(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return repr(value)[:500]

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, enum.Enum):
        return value.value

    if isinstance(value, Path):
        return str(value)

    if is_dataclass(value):
        try:
            return {
                "__type__": f"{type(value).__module__}.{type(value).__name__}",
                **{
                    key: jsonable(item, depth + 1)
                    for key, item in asdict(value).items()
                },
            }
        except Exception:
            pass

    if hasattr(value, "model_dump"):
        try:
            return jsonable(value.model_dump(), depth + 1)
        except Exception:
            pass

    if isinstance(value, dict):
        return {
            str(key): jsonable(item, depth + 1)
            for key, item in list(value.items())[:100]
        }

    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            jsonable(item, depth + 1)
            for item in list(value)[:100]
        ]

    data = {}
    for name in (
        "connector",
        "status",
        "findings",
        "raw_data",
        "execution_time",
        "error",
        "metadata",
        "category",
        "value",
        "url",
        "source",
        "confidence",
        "reliability",
    ):
        if hasattr(value, name):
            try:
                data[name] = jsonable(getattr(value, name), depth + 1)
            except Exception:
                pass

    if data:
        data["__type__"] = f"{type(value).__module__}.{type(value).__name__}"
        return data

    return {
        "__type__": f"{type(value).__module__}.{type(value).__name__}",
        "repr": repr(value)[:1000],
    }


def find_connector_class(module: Any) -> type:
    classes = []

    for _, cls in inspect.getmembers(module, inspect.isclass):
        if cls.__module__ != module.__name__:
            continue
        if callable(getattr(cls, "execute", None)):
            classes.append(cls)

    if not classes:
        raise RuntimeError(
            f"No connector class with execute() found in {module.__name__}"
        )

    classes.sort(
        key=lambda cls: (
            0 if cls.__name__.lower().endswith("connector") else 1,
            cls.__name__,
        )
    )

    return classes[0]


def instantiate(cls: type) -> Any:
    signature = inspect.signature(cls)

    required = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.name not in {"self", "cls"}
        and parameter.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
        and parameter.default is inspect.Parameter.empty
    ]

    if not required:
        return cls()

    raise RuntimeError(
        "Unexpected required connector constructor parameters: "
        + ", ".join(
            f"{parameter.name}:{parameter.annotation!r}"
            for parameter in required
        )
    )


def url_target_type(enum_cls: type[enum.Enum]) -> enum.Enum:
    for candidate in ("URL", "URI", "WEB"):
        if candidate in enum_cls.__members__:
            return enum_cls.__members__[candidate]

    for member in enum_cls:
        if "url" in f"{member.name} {member.value}".lower():
            return member

    raise RuntimeError("No URL-like OsintTargetType found")


def build_request() -> Any:
    models = importlib.import_module("app.osint.models")

    target_cls = getattr(models, "OsintTarget")
    target_type_cls = getattr(models, "OsintTargetType")
    request_cls = getattr(models, "ConnectorRequest")

    target_type = url_target_type(target_type_cls)

    target_kwargs = {}
    for parameter in inspect.signature(target_cls).parameters.values():
        name = parameter.name.lower()

        if name in {"target_type", "type", "kind"}:
            target_kwargs[parameter.name] = target_type
        elif name in {"value", "target", "query", "identifier"}:
            target_kwargs[parameter.name] = TARGET_VALUE
        elif name in {"metadata", "context", "options"}:
            target_kwargs[parameter.name] = {}
        elif parameter.default is inspect.Parameter.empty:
            raise RuntimeError(
                f"Unknown required OsintTarget parameter: {parameter.name}"
            )

    target = target_cls(**target_kwargs)

    request_kwargs = {}
    for parameter in inspect.signature(request_cls).parameters.values():
        name = parameter.name.lower()

        if name in {"target", "osint_target"}:
            request_kwargs[parameter.name] = target
        elif name in {"limit", "max_results"}:
            request_kwargs[parameter.name] = REQUEST_LIMIT
        elif name in {"timeout", "timeout_seconds"}:
            request_kwargs[parameter.name] = REQUEST_TIMEOUT
        elif name in {"metadata", "context", "options"}:
            request_kwargs[parameter.name] = {}
        elif parameter.default is inspect.Parameter.empty:
            raise RuntimeError(
                f"Unknown required ConnectorRequest parameter: {parameter.name}"
            )

    return request_cls(**request_kwargs)


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def source_contract(module_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
        source_file = inspect.getsourcefile(module)
        source = inspect.getsource(module)
    except Exception:
        return {
            "module": module_name,
            "error": traceback.format_exc(limit=10),
        }

    lower = source.lower()

    return {
        "module": module_name,
        "source_file": (
            str(Path(source_file).resolve().relative_to(ROOT)).replace("\\", "/")
            if source_file
            else None
        ),
        "source_size": len(source),
        "uses_tool_runtime": "tool_runtime" in lower,
        "uses_subprocess": "subprocess" in lower,
        "uses_tool_runner": "toolrunner" in lower,
        "uses_request_limit": (
            "request.limit" in source
            or "request.max_results" in source
        ),
        "mentions_json": "json" in lower,
        "mentions_silent": "-silent" in source,
        "mentions_status_code": (
            "-sc" in source
            or "-status-code" in source
        ),
        "mentions_disable_update_check": "-duc" in source,
        "parse_methods": sorted(
            set(
                re.findall(
                    r"def\s+([A-Za-z0-9_]*parse[A-Za-z0-9_]*)\s*\(",
                    source,
                    flags=re.IGNORECASE,
                )
            )
        ),
        "execute_methods": sorted(
            set(
                re.findall(
                    r"def\s+(execute[A-Za-z0-9_]*)\s*\(",
                    source,
                    flags=re.IGNORECASE,
                )
            )
        ),
    }


async def run_httpx_child() -> dict[str, Any]:
    module = importlib.import_module(HTTPX_MODULE)
    cls = find_connector_class(module)
    connector = instantiate(cls)
    request = build_request()

    result = await maybe_await(
        connector.execute(request)
    )

    findings = list(
        getattr(result, "findings", None)
        or []
    )

    return {
        "module": HTTPX_MODULE,
        "class": cls.__name__,
        "class_signature": str(inspect.signature(cls)),
        "execute_signature": str(inspect.signature(connector.execute)),
        "request": {
            "target": TARGET_VALUE,
            "limit": REQUEST_LIMIT,
            "timeout": REQUEST_TIMEOUT,
        },
        "result": {
            "type": f"{type(result).__module__}.{type(result).__name__}",
            "status": jsonable(getattr(result, "status", None)),
            "error": jsonable(getattr(result, "error", None)),
            "metadata": jsonable(getattr(result, "metadata", None)),
            "findings_count": len(findings),
            "limit_honored": len(findings) <= REQUEST_LIMIT,
            "findings_sample": [
                jsonable(item)
                for item in findings[:5]
            ],
        },
        "source_contract": source_contract(HTTPX_MODULE),
    }


def run_isolated_httpx() -> dict[str, Any]:
    env = os.environ.copy()
    env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "")

    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--httpx-child",
            ],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=HARD_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "error": f"httpx wrapper hard timeout after {HARD_TIMEOUT}s",
            "timeout": True,
        }

    payload = None

    for line in reversed((completed.stdout or "").splitlines()):
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            continue

    if payload is None:
        payload = {
            "error": "httpx child produced no JSON payload",
            "stdout_tail": (completed.stdout or "")[-3000:],
        }

    payload["child_exit_code"] = completed.returncode
    payload["child_stderr_tail"] = (completed.stderr or "")[-3000:]

    return payload


def ghunt_contract() -> dict[str, Any]:
    for module_name in GHUNT_MODULE_CANDIDATES:
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        classes = []
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ == module_name:
                classes.append({
                    "name": cls.__name__,
                    "signature": str(inspect.signature(cls)),
                    "methods": {
                        name: str(inspect.signature(member))
                        for name, member in inspect.getmembers(cls)
                        if callable(member)
                        and not name.startswith("__")
                        and (
                            name in {"execute", "is_available", "supports"}
                            or "parse" in name.lower()
                        )
                    },
                })

        return {
            "module": module_name,
            "import_ok": True,
            "classes": classes,
            "source_contract": source_contract(module_name),
        }

    return {
        "module": None,
        "import_ok": False,
        "error": "No GHunt connector module could be imported.",
    }


def ghunt_help_health() -> dict[str, Any]:
    executable = shutil.which("ghunt")

    if not executable:
        return {
            "resolved_path": None,
            "status": "BLOCKED",
            "output": [],
        }

    try:
        completed = subprocess.run(
            [executable, "--help"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )

        text = "\n".join(
            part
            for part in (
                completed.stdout or "",
                completed.stderr or "",
            )
            if part
        )

        lowered = text.lower()

        fatal = any(
            token in lowered
            for token in (
                "traceback (most recent call last)",
                "modulenotfounderror:",
                "importerror:",
            )
        )

        return {
            "resolved_path": executable,
            "exit_code": completed.returncode,
            "status": "BROKEN" if fatal else "READY_CLI",
            "traceback_detected": fatal,
            "output": [
                line.strip()
                for line in text.splitlines()
                if line.strip()
            ][:40],
        }

    except Exception as exc:
        return {
            "resolved_path": executable,
            "status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }


def source_inventory() -> list[dict[str, Any]]:
    result = []

    for relative in SOURCE_PATHS:
        path = ROOT / relative
        result.append({
            "path": relative,
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else None,
        })

    return result


def build_bundle(report_path: Path) -> Path:
    bundle = OUT / "osint_05b_httpx_ghunt_bundle.zip"

    with zipfile.ZipFile(
        bundle,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.write(
            report_path,
            "httpx_ghunt_contract.json",
        )

        for relative in SOURCE_PATHS:
            path = ROOT / relative
            if path.exists() and path.is_file():
                archive.write(
                    path,
                    relative,
                )

    return bundle


def child_main() -> int:
    try:
        payload = asyncio.run(
            run_httpx_child()
        )
        print(
            json.dumps(
                payload,
                ensure_ascii=False,
                default=str,
            )
        )
        return 0
    except Exception:
        print(
            json.dumps(
                {
                    "error": traceback.format_exc(limit=30),
                },
                ensure_ascii=False,
            )
        )
        return 1


def parent_main() -> int:
    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    say("OSINT Expansion 05B — HTTPX/GHunt Production Contract Probe")
    say("=" * 72)

    say("[1/3] production httpx connector...")
    httpx_result = run_isolated_httpx()

    if httpx_result.get("error"):
        say(
            "      FAIL: "
            + str(httpx_result["error"]).splitlines()[-1][:220]
        )
    else:
        result = httpx_result.get("result", {})
        say(
            f"      status={result.get('status')} "
            f"findings={result.get('findings_count')} "
            f"limit_honored={result.get('limit_honored')}"
        )

    say("[2/3] GHunt production connector contract...")
    ghunt_source = ghunt_contract()
    say(
        f"      import_ok={ghunt_source.get('import_ok')} "
        f"module={ghunt_source.get('module')}"
    )

    say("[3/3] GHunt CLI help health...")
    ghunt_health = ghunt_help_health()
    say(
        f"      status={ghunt_health.get('status')} "
        f"path={ghunt_health.get('resolved_path')}"
    )

    report = {
        "probe_version": 1,
        "httpx": httpx_result,
        "ghunt_connector": ghunt_source,
        "ghunt_cli_health": ghunt_health,
        "source_inventory": source_inventory(),
        "notes": [
            "The httpx connector uses only https://example.com.",
            "No DB writes or persistence are performed.",
            "No GHunt account query is executed.",
            "The bundle contains only production sources needed for the next patch.",
        ],
    }

    report_path = OUT / "httpx_ghunt_contract.json"
    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    bundle = build_bundle(report_path)

    say("")
    say(f"JSON:   {report_path}")
    say(f"BUNDLE: {bundle}")
    say("")
    say("OSINT EXPANSION 05B HTTPX/GHUNT CONTRACT PROBE: PASS")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--httpx-child",
        action="store_true",
    )
    args = parser.parse_args()

    if args.httpx_child:
        return child_main()

    return parent_main()


if __name__ == "__main__":
    raise SystemExit(main())


"""
OSINT Expansion 04E — Discovery Result Budget Gate

Checks whether the six discovery connector wrappers honor ConnectorRequest.limit.

No production files are modified.
No DB writes.
Target: example.com
Requested limit: 5
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
import subprocess
import sys
import traceback
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_04e"
BIN = ROOT / "tools" / "osint" / "bin"
TARGET_VALUE = "example.com"
REQUEST_LIMIT = 5
REQUEST_TIMEOUT = 20
HARD_TIMEOUT = 28

CONNECTORS = {
    "subfinder": "app.osint.connectors.subfinder_connector",
    "dnsx": "app.osint.connectors.dnsx_connector",
    "gau": "app.osint.connectors.gau_connector",
    "waybackurls": "app.osint.connectors.waybackurls_connector",
    "katana": "app.osint.connectors.katana_connector",
    "assetfinder": "app.osint.connectors.assetfinder_connector",
}

SOURCE_PATHS = [
    "app/osint/connectors/subfinder_connector.py",
    "app/osint/connectors/dnsx_connector.py",
    "app/osint/connectors/gau_connector.py",
    "app/osint/connectors/waybackurls_connector.py",
    "app/osint/connectors/katana_connector.py",
    "app/osint/connectors/assetfinder_connector.py",
    "app/osint/base_connector.py",
    "app/osint/models.py",
    "app/osint/result.py",
    "app/osint/runner.py",
    "app/osint/tool_runtime.py",
]


def say(text: str = "") -> None:
    print(text, flush=True)


def enum_domain_value(enum_cls: type[enum.Enum]) -> enum.Enum:
    for name in ("DOMAIN", "DOMAIN_NAME", "HOST", "HOSTNAME"):
        if name in enum_cls.__members__:
            return enum_cls.__members__[name]
    for member in enum_cls:
        if "domain" in f"{member.name} {member.value}".lower():
            return member
    raise RuntimeError("No DOMAIN-like target type found")


def build_request() -> Any:
    models = importlib.import_module("app.osint.models")
    target_cls = getattr(models, "OsintTarget")
    target_type_cls = getattr(models, "OsintTargetType")
    request_cls = getattr(models, "ConnectorRequest")

    target_type = enum_domain_value(target_type_cls)

    target_kwargs = {}
    for p in inspect.signature(target_cls).parameters.values():
        n = p.name.lower()
        if n in {"target_type", "type", "kind"}:
            target_kwargs[p.name] = target_type
        elif n in {"value", "target", "query", "identifier"}:
            target_kwargs[p.name] = TARGET_VALUE
        elif n in {"metadata", "context", "options"}:
            target_kwargs[p.name] = {}
        elif p.default is inspect.Parameter.empty:
            raise RuntimeError(f"Unknown OsintTarget parameter: {p.name}")

    target = target_cls(**target_kwargs)

    request_kwargs = {}
    for p in inspect.signature(request_cls).parameters.values():
        n = p.name.lower()
        if n in {"target", "osint_target"}:
            request_kwargs[p.name] = target
        elif n in {"limit", "max_results"}:
            request_kwargs[p.name] = REQUEST_LIMIT
        elif n in {"timeout", "timeout_seconds"}:
            request_kwargs[p.name] = REQUEST_TIMEOUT
        elif n in {"metadata", "context", "options"}:
            request_kwargs[p.name] = {}
        elif p.default is inspect.Parameter.empty:
            raise RuntimeError(f"Unknown ConnectorRequest parameter: {p.name}")

    return request_cls(**request_kwargs)


def find_connector_class(module: Any) -> type:
    classes = []
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if cls.__module__ == module.__name__ and callable(getattr(cls, "execute", None)):
            classes.append(cls)
    if not classes:
        raise RuntimeError("No connector class with execute()")
    classes.sort(key=lambda cls: cls.__name__)
    return classes[0]


def instantiate(cls: type) -> Any:
    sig = inspect.signature(cls)
    required = [
        p for p in sig.parameters.values()
        if p.name not in {"self", "cls"}
        and p.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
        and p.default is inspect.Parameter.empty
    ]
    if not required:
        return cls()
    raise RuntimeError(
        "Unexpected required connector constructor parameters: "
        + ", ".join(p.name for p in required)
    )


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def run_child(name: str) -> dict[str, Any]:
    module_name = CONNECTORS[name]
    module = importlib.import_module(module_name)
    cls = find_connector_class(module)
    connector = instantiate(cls)
    request = build_request()

    result = await maybe_await(connector.execute(request))

    findings = getattr(result, "findings", None)
    findings = list(findings or [])

    metadata = getattr(result, "metadata", None)
    status = getattr(result, "status", None)
    error = getattr(result, "error", None)

    if isinstance(status, enum.Enum):
        status = status.value

    source = Path(inspect.getsourcefile(module) or "")
    source_text = source.read_text(encoding="utf-8", errors="replace") if source.exists() else ""

    return {
        "name": name,
        "module": module_name,
        "class": cls.__name__,
        "requested_limit": REQUEST_LIMIT,
        "returned_findings": len(findings),
        "limit_honored": len(findings) <= REQUEST_LIMIT,
        "status": status,
        "error": error,
        "metadata": metadata,
        "source_mentions_request_limit": (
            "request.limit" in source_text
            or "request.max_results" in source_text
        ),
        "source_size": len(source_text),
    }


def child_main(name: str) -> int:
    try:
        payload = asyncio.run(run_child(name))
        print(json.dumps(payload, ensure_ascii=False, default=str))
        return 0
    except Exception:
        print(json.dumps({
            "name": name,
            "error": traceback.format_exc(limit=30),
        }, ensure_ascii=False))
        return 1


def isolated(name: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "")

    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child", name],
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
            "name": name,
            "requested_limit": REQUEST_LIMIT,
            "timeout": True,
            "limit_honored": None,
            "error": f"hard timeout after {HARD_TIMEOUT}s",
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
            "name": name,
            "error": "child produced no JSON",
        }

    payload["child_exit_code"] = completed.returncode
    payload["stderr_tail"] = (completed.stderr or "")[-2000:]
    return payload


def build_bundle(report_path: Path) -> Path:
    bundle = OUT / "osint_04e_budget_bundle.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(report_path, "budget_report.json")
        for rel in SOURCE_PATHS:
            path = ROOT / rel
            if path.exists():
                zf.write(path, rel)
    return bundle


def parent_main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    say("OSINT Expansion 04E — Discovery Result Budget Gate")
    say("=" * 66)
    say(f"Target: {TARGET_VALUE}")
    say(f"ConnectorRequest.limit: {REQUEST_LIMIT}")
    say("")

    results = []

    for index, name in enumerate(CONNECTORS, 1):
        say(f"[{index}/6] {name} ...")
        item = isolated(name)
        results.append(item)

        if item.get("timeout"):
            say("      TIMEOUT")
        elif item.get("returned_findings") is not None:
            say(
                f"      returned={item['returned_findings']} "
                f"limit_honored={item['limit_honored']} "
                f"status={item.get('status')} "
                f"source_uses_limit={item.get('source_mentions_request_limit')}"
            )
        else:
            say(f"      FAIL: {str(item.get('error'))[-220:]}")

    report = {
        "gate_version": 1,
        "target": TARGET_VALUE,
        "requested_limit": REQUEST_LIMIT,
        "results": results,
    }

    report_path = OUT / "budget_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    bundle = build_bundle(report_path)

    violations = [
        item["name"]
        for item in results
        if item.get("limit_honored") is False
    ]

    say("")
    say("SUMMARY")
    say("-" * 66)
    say("Limit violations: " + (", ".join(violations) if violations else "none"))
    say("")
    say(f"JSON:   {report_path}")
    say(f"BUNDLE: {bundle}")
    say("")
    say("OSINT EXPANSION 04E RESULT BUDGET GATE: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=tuple(CONNECTORS), default=None)
    args = parser.parse_args()

    if args.child:
        return child_main(args.child)

    return parent_main()


if __name__ == "__main__":
    raise SystemExit(main())

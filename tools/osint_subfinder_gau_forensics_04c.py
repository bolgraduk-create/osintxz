
"""
OSINT Expansion 04C — Subfinder/Gau Wrapper Forensics

Purpose:
Capture the exact reason for:
- subfinder producing an implausibly large number of findings
- gau returning status=failed with zero findings

This script does NOT modify production code and does NOT write to the DB.
It produces a small diagnostic JSON and a ZIP containing only the relevant
current project source files plus the diagnostic result.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
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
OUT = ROOT / "storage" / "cache" / "osint_expansion_04c"
BIN = ROOT / "tools" / "osint" / "bin"
TARGET_VALUE = "example.com"
TIMEOUT_SECONDS = 45

CONNECTORS = {
    "subfinder": "app.osint.connectors.subfinder_connector",
    "gau": "app.osint.connectors.gau_connector",
}

SOURCE_PATHS = (
    "app/osint/connectors/subfinder_connector.py",
    "app/osint/connectors/gau_connector.py",
    "app/osint/base_cli_connector.py",
    "app/osint/external_tool_runner.py",
    "app/osint/tool_runtime.py",
    "app/osint/models.py",
    "app/osint/result.py",
    "app/osint/runner.py",
    "app/osint/manager.py",
    "app/osint/registry.py",
)


def say(text: str = "") -> None:
    print(text, flush=True)


def primitive(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return repr(value)[:300]

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, enum.Enum):
        return value.value

    if is_dataclass(value):
        try:
            return {
                k: primitive(v, depth + 1)
                for k, v in asdict(value).items()
            }
        except Exception:
            pass

    if hasattr(value, "model_dump"):
        try:
            return primitive(value.model_dump(), depth + 1)
        except Exception:
            pass

    if isinstance(value, dict):
        return {
            str(k): primitive(v, depth + 1)
            for k, v in list(value.items())[:60]
        }

    if isinstance(value, (list, tuple, set, frozenset)):
        return [primitive(v, depth + 1) for v in list(value)[:60]]

    data = {}
    for name in (
        "kind", "type", "value", "title", "description", "source",
        "confidence", "metadata", "url", "domain", "hostname",
        "status", "errors", "warnings",
    ):
        if hasattr(value, name):
            try:
                data[name] = primitive(getattr(value, name), depth + 1)
            except Exception:
                pass

    if data:
        data["__type__"] = f"{type(value).__module__}.{type(value).__name__}"
        return data

    return {
        "__type__": f"{type(value).__module__}.{type(value).__name__}",
        "repr": repr(value)[:500],
    }


def required_parameters(obj: Any) -> list[inspect.Parameter]:
    sig = inspect.signature(obj)
    out = []
    for p in sig.parameters.values():
        if p.name in {"self", "cls"}:
            continue
        if p.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if p.default is inspect.Parameter.empty:
            out.append(p)
    return out


def enum_domain_value(enum_cls: type[enum.Enum]) -> enum.Enum:
    for name in ("DOMAIN", "DOMAIN_NAME", "HOST", "HOSTNAME"):
        if name in enum_cls.__members__:
            return enum_cls.__members__[name]
    for member in enum_cls:
        if "domain" in f"{member.name} {member.value}".lower():
            return member
    raise RuntimeError("No DOMAIN-like OsintTargetType found")


def construct_target_request() -> tuple[Any, Any]:
    models = importlib.import_module("app.osint.models")
    target_cls = getattr(models, "OsintTarget")
    target_type_cls = getattr(models, "OsintTargetType")
    request_cls = getattr(models, "ConnectorRequest")

    target_type = enum_domain_value(target_type_cls)
    kwargs = {}
    for p in inspect.signature(target_cls).parameters.values():
        n = p.name.lower()
        if n in {"target_type", "type", "kind"}:
            kwargs[p.name] = target_type
        elif n in {"value", "target", "query", "identifier"}:
            kwargs[p.name] = TARGET_VALUE
        elif n in {"metadata", "context", "options"}:
            kwargs[p.name] = {}
        elif p.default is inspect.Parameter.empty:
            raise RuntimeError(f"Unknown OsintTarget parameter: {p.name}")
    target = target_cls(**kwargs)

    kwargs = {}
    for p in inspect.signature(request_cls).parameters.values():
        n = p.name.lower()
        if n in {"target", "osint_target"}:
            kwargs[p.name] = target
        elif n in {"metadata", "context", "options"}:
            kwargs[p.name] = {}
        elif n in {"limit", "max_results"}:
            kwargs[p.name] = 100
        elif n in {"timeout", "timeout_seconds"}:
            kwargs[p.name] = 30
        elif p.default is inspect.Parameter.empty:
            raise RuntimeError(f"Unknown ConnectorRequest parameter: {p.name}")
    return target, request_cls(**kwargs)


def find_connector_class(module: Any) -> type:
    candidates = []
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if cls.__module__ != module.__name__:
            continue
        if callable(getattr(cls, "execute", None)):
            candidates.append(cls)
    if not candidates:
        raise RuntimeError("No connector class with execute()")
    candidates.sort(key=lambda c: c.__name__)
    return candidates[0]


def instantiate(cls: type) -> Any:
    required = required_parameters(cls)
    if not required:
        return cls()

    kwargs = {}
    for p in required:
        name = p.name.lower()
        annotation = str(p.annotation).lower()

        if "tool_runtime" in name or "toolruntime" in annotation:
            mod = importlib.import_module("app.osint.tool_runtime")
            kwargs[p.name] = getattr(mod, "ToolRuntime")()
            continue

        if "runner" in name or "runner" in annotation:
            mod = importlib.import_module("app.osint.external_tool_runner")
            kwargs[p.name] = getattr(mod, "ExternalToolRunner")()
            continue

        raise RuntimeError(
            f"Unresolved constructor parameter {p.name}: {p.annotation!r}"
        )

    return cls(**kwargs)


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def finding_key(finding: Any) -> str:
    for name in (
        "value", "url", "domain", "hostname", "title", "description"
    ):
        if hasattr(finding, name):
            try:
                value = getattr(finding, name)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            except Exception:
                pass

    if isinstance(finding, dict):
        for name in (
            "value", "url", "domain", "hostname", "title", "description"
        ):
            value = finding.get(name)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return repr(finding)[:300]


DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z]{2,63}$",
    re.IGNORECASE,
)


def analyze_findings(findings: list[Any]) -> dict[str, Any]:
    keys = [finding_key(item) for item in findings]
    normalized = [key.lower().strip().rstrip(".") for key in keys]

    type_counts = Counter(
        f"{type(item).__module__}.{type(item).__name__}"
        for item in findings
    )

    duplicate_count = len(normalized) - len(set(normalized))
    domain_like = sum(
        1 for value in normalized
        if DOMAIN_RE.fullmatch(value)
    )
    target_related = sum(
        1 for value in normalized
        if value == TARGET_VALUE
        or value.endswith("." + TARGET_VALUE)
        or TARGET_VALUE in value
    )

    weird_examples = [
        key for key in keys
        if not DOMAIN_RE.fullmatch(key.lower().strip().rstrip("."))
    ][:25]

    return {
        "count": len(findings),
        "unique_keys": len(set(normalized)),
        "duplicates": duplicate_count,
        "domain_like": domain_like,
        "target_related": target_related,
        "type_counts": dict(type_counts),
        "first_20": [primitive(x) for x in findings[:20]],
        "last_10": [primitive(x) for x in findings[-10:]],
        "weird_key_examples": weird_examples,
    }


async def run_connector(name: str) -> dict[str, Any]:
    module_name = CONNECTORS[name]
    module = importlib.import_module(module_name)
    cls = find_connector_class(module)
    connector = instantiate(cls)
    target, request = construct_target_request()

    result = await maybe_await(connector.execute(request))

    findings = getattr(result, "findings", None)
    if findings is None and isinstance(result, dict):
        findings = result.get("findings")
    findings = list(findings or [])

    result_attrs = {}
    for attr in (
        "status", "errors", "error", "warnings", "metadata",
        "connector", "source", "duration", "return_code",
        "stdout", "stderr", "raw_output",
    ):
        if hasattr(result, attr):
            try:
                result_attrs[attr] = primitive(getattr(result, attr))
            except Exception:
                pass

    return {
        "name": name,
        "module": module_name,
        "class": cls.__name__,
        "class_signature": str(inspect.signature(cls)),
        "execute_signature": str(inspect.signature(connector.execute)),
        "result_type": f"{type(result).__module__}.{type(result).__name__}",
        "result_attrs": result_attrs,
        "findings": analyze_findings(findings),
        "result_preview": primitive(result),
    }


def child(name: str) -> int:
    try:
        payload = asyncio.run(run_connector(name))
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({
            "name": name,
            "error": traceback.format_exc(limit=30),
        }, ensure_ascii=False))
        return 1


def run_isolated(name: str) -> dict[str, Any]:
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
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "name": name,
            "timeout": True,
            "error": f"hard timeout after {TIMEOUT_SECONDS}s",
        }

    lines = [
        line.strip()
        for line in (completed.stdout or "").splitlines()
        if line.strip()
    ]

    payload = None
    for line in reversed(lines):
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            pass

    if payload is None:
        payload = {
            "name": name,
            "error": "child produced no JSON payload",
            "stdout_tail": lines[-20:],
        }

    payload["child_exit_code"] = completed.returncode
    payload["child_stderr_tail"] = (completed.stderr or "")[-3000:]
    return payload


def source_inventory() -> list[dict[str, Any]]:
    items = []
    for rel in SOURCE_PATHS:
        path = ROOT / rel
        items.append({
            "path": rel,
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else None,
        })
    return items


def build_bundle(report_path: Path) -> Path:
    bundle = OUT / "osint_04c_diagnostic_bundle.zip"

    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(report_path, "diagnostic.json")

        for rel in SOURCE_PATHS:
            path = ROOT / rel
            if path.exists() and path.is_file():
                zf.write(path, rel)

    return bundle


def parent() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    say("OSINT Expansion 04C — Subfinder/Gau Wrapper Forensics")
    say("=" * 68)

    results = []
    for index, name in enumerate(CONNECTORS, 1):
        say(f"[{index}/2] {name} wrapper ...")
        result = run_isolated(name)
        results.append(result)

        if result.get("error"):
            say(f"      FAIL: {str(result['error']).splitlines()[-1][:220]}")
            continue

        findings = result.get("findings", {})
        attrs = result.get("result_attrs", {})
        say(
            f"      status={attrs.get('status')} "
            f"count={findings.get('count')} "
            f"unique={findings.get('unique_keys')} "
            f"duplicates={findings.get('duplicates')} "
            f"domain_like={findings.get('domain_like')} "
            f"target_related={findings.get('target_related')}"
        )

    report = {
        "forensics_version": 1,
        "target": TARGET_VALUE,
        "results": results,
        "source_inventory": source_inventory(),
        "notes": [
            "No production files are modified.",
            "No database persistence is invoked.",
            "The diagnostic bundle contains only relevant project source files.",
        ],
    }

    report_path = OUT / "diagnostic.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    bundle_path = build_bundle(report_path)

    say("")
    say(f"JSON:   {report_path}")
    say(f"BUNDLE: {bundle_path}")
    say("")
    say("OSINT EXPANSION 04C FORENSICS: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=tuple(CONNECTORS), default=None)
    args = parser.parse_args()

    if args.child:
        return child(args.child)

    return parent()


if __name__ == "__main__":
    raise SystemExit(main())

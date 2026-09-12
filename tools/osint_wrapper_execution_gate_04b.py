
"""
OSINT Expansion 04B — Connector Wrapper Execution Gate

Runs the six *project connector wrappers* against a benign public domain
(example.com) in isolated child processes.

This is the bridge between:
    raw CLI works
and
    the application connector actually produces OsintResult/OsintFinding.

Safety:
- no DB writes
- no persistence calls
- no vulnerability scanners
- one benign public target: example.com
- each wrapper is isolated with a hard timeout
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


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_04b"
BIN = ROOT / "tools" / "osint" / "bin"
TARGET_VALUE = "example.com"
WRAPPER_TIMEOUT_SECONDS = 30

CONNECTORS = {
    "subfinder": "app.osint.connectors.subfinder_connector",
    "dnsx": "app.osint.connectors.dnsx_connector",
    "gau": "app.osint.connectors.gau_connector",
    "waybackurls": "app.osint.connectors.waybackurls_connector",
    "katana": "app.osint.connectors.katana_connector",
    "assetfinder": "app.osint.connectors.assetfinder_connector",
}


def say(text: str = "") -> None:
    print(text, flush=True)


def jsonable(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return repr(value)[:500]

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, enum.Enum):
        return {
            "enum": f"{type(value).__module__}.{type(value).__name__}",
            "name": value.name,
            "value": jsonable(value.value, depth=depth + 1),
        }

    if is_dataclass(value):
        try:
            return {
                "__type__": f"{type(value).__module__}.{type(value).__name__}",
                **{
                    key: jsonable(item, depth=depth + 1)
                    for key, item in asdict(value).items()
                },
            }
        except Exception:
            pass

    if hasattr(value, "model_dump"):
        try:
            return {
                "__type__": f"{type(value).__module__}.{type(value).__name__}",
                **jsonable(value.model_dump(), depth=depth + 1),
            }
        except Exception:
            pass

    if isinstance(value, dict):
        return {
            str(key): jsonable(item, depth=depth + 1)
            for key, item in list(value.items())[:100]
        }

    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            jsonable(item, depth=depth + 1)
            for item in list(value)[:100]
        ]

    data = {}
    for name in (
        "status",
        "findings",
        "errors",
        "warnings",
        "metadata",
        "source",
        "connector",
        "target",
        "value",
        "type",
        "kind",
        "title",
        "description",
        "confidence",
    ):
        if hasattr(value, name):
            try:
                data[name] = jsonable(
                    getattr(value, name),
                    depth=depth + 1,
                )
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
    candidates = []

    for _, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue

        methods = {
            name
            for name, member in inspect.getmembers(obj)
            if callable(member)
        }

        if "execute" in methods:
            candidates.append(obj)

    if not candidates:
        raise RuntimeError(
            f"No connector class with execute() found in {module.__name__}"
        )

    candidates.sort(
        key=lambda cls: (
            0 if cls.__name__.lower().endswith("connector") else 1,
            cls.__name__,
        )
    )

    return candidates[0]


def required_parameters(callable_obj: Any) -> list[inspect.Parameter]:
    signature = inspect.signature(callable_obj)
    result = []

    for parameter in signature.parameters.values():
        if parameter.name in {"self", "cls"}:
            continue
        if parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue
        if parameter.default is inspect.Parameter.empty:
            result.append(parameter)

    return result


def instantiate_connector(cls: type) -> Any:
    required = required_parameters(cls)

    if not required:
        return cls()

    # Conservative dependency resolver for shared runtime abstractions.
    kwargs: dict[str, Any] = {}

    for parameter in required:
        name = parameter.name.lower()
        annotation = str(parameter.annotation).lower()

        if "tool_runtime" in name or "toolruntime" in annotation:
            runtime_module = importlib.import_module("app.osint.tool_runtime")
            runtime_cls = getattr(runtime_module, "ToolRuntime")
            kwargs[parameter.name] = runtime_cls()
            continue

        if "runner" in name or "runner" in annotation:
            try:
                runner_module = importlib.import_module("app.osint.external_tool_runner")
                runner_cls = getattr(runner_module, "ExternalToolRunner")
                kwargs[parameter.name] = runner_cls()
                continue
            except Exception:
                pass

        raise RuntimeError(
            "Connector constructor has an unresolved required parameter: "
            f"{parameter.name}: {parameter.annotation!r}"
        )

    return cls(**kwargs)


def enum_domain_value(enum_cls: type[enum.Enum]) -> enum.Enum:
    members = enum_cls.__members__

    for candidate in ("DOMAIN", "DOMAIN_NAME", "HOST", "HOSTNAME"):
        if candidate in members:
            return members[candidate]

    for member in enum_cls:
        text = f"{member.name} {member.value}".lower()
        if "domain" in text:
            return member

    raise RuntimeError(
        f"Could not find DOMAIN-like value in {enum_cls.__name__}: "
        f"{list(members)}"
    )


def build_target_and_request() -> tuple[Any, Any, dict[str, Any]]:
    models = importlib.import_module("app.osint.models")

    target_cls = getattr(models, "OsintTarget")
    target_type_cls = getattr(models, "OsintTargetType")
    request_cls = getattr(models, "ConnectorRequest")

    target_type = enum_domain_value(target_type_cls)

    target_sig = inspect.signature(target_cls)
    target_kwargs: dict[str, Any] = {}

    for parameter in target_sig.parameters.values():
        name = parameter.name.lower()

        if name in {"target_type", "type", "kind"}:
            target_kwargs[parameter.name] = target_type
        elif name in {"value", "target", "query", "identifier"}:
            target_kwargs[parameter.name] = TARGET_VALUE
        elif name in {"metadata", "context", "options"}:
            target_kwargs[parameter.name] = {}
        elif parameter.default is inspect.Parameter.empty:
            raise RuntimeError(
                "Cannot construct OsintTarget; unknown required parameter "
                f"{parameter.name}: {parameter.annotation!r}"
            )

    target = target_cls(**target_kwargs)

    request_sig = inspect.signature(request_cls)
    request_kwargs: dict[str, Any] = {}

    for parameter in request_sig.parameters.values():
        name = parameter.name.lower()

        if name in {"target", "osint_target"}:
            request_kwargs[parameter.name] = target
        elif name in {"metadata", "context", "options"}:
            request_kwargs[parameter.name] = {}
        elif name in {"limit", "max_results"}:
            request_kwargs[parameter.name] = 25
        elif name in {"timeout", "timeout_seconds"}:
            request_kwargs[parameter.name] = 20
        elif parameter.default is inspect.Parameter.empty:
            raise RuntimeError(
                "Cannot construct ConnectorRequest; unknown required parameter "
                f"{parameter.name}: {parameter.annotation!r}"
            )

    request = request_cls(**request_kwargs)

    contract = {
        "OsintTarget_signature": str(target_sig),
        "ConnectorRequest_signature": str(request_sig),
        "target_kwargs": jsonable(target_kwargs),
        "request_kwargs": jsonable(request_kwargs),
    }

    return target, request, contract


async def await_result(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def result_summary(result: Any) -> dict[str, Any]:
    serialized = jsonable(result)

    findings = getattr(result, "findings", None)
    if findings is None and isinstance(result, dict):
        findings = result.get("findings")

    try:
        findings_count = len(findings) if findings is not None else None
    except Exception:
        findings_count = None

    status = getattr(result, "status", None)
    if status is None and isinstance(result, dict):
        status = result.get("status")

    return {
        "result_type": f"{type(result).__module__}.{type(result).__name__}",
        "status": jsonable(status),
        "findings_count": findings_count,
        "serialized": serialized,
    }


async def run_child(connector_name: str) -> dict[str, Any]:
    module_name = CONNECTORS[connector_name]
    module = importlib.import_module(module_name)
    cls = find_connector_class(module)

    target, request, request_contract = build_target_and_request()
    connector = instantiate_connector(cls)

    execute = getattr(connector, "execute")
    execute_signature = str(inspect.signature(execute))

    supports_result = None
    if hasattr(connector, "supports"):
        supports = getattr(connector, "supports")
        try:
            target_type = getattr(target, "target_type", None)
            if target_type is None:
                target_type = getattr(target, "type", None)
            supports_result = supports(target_type)
            supports_result = await await_result(supports_result)
        except Exception as exc:
            supports_result = {
                "error": f"{type(exc).__name__}: {exc}"
            }

    raw_result = execute(request)
    result = await await_result(raw_result)

    return {
        "connector_name": connector_name,
        "module": module_name,
        "class": cls.__name__,
        "class_signature": str(inspect.signature(cls)),
        "execute_signature": execute_signature,
        "supports_result": jsonable(supports_result),
        "request_contract": request_contract,
        "result": result_summary(result),
    }


def child_main(connector_name: str) -> int:
    try:
        payload = asyncio.run(run_child(connector_name))
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception:
        payload = {
            "connector_name": connector_name,
            "error": traceback.format_exc(limit=20),
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 1


def parent_main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    say("OSINT Expansion 04B — Connector Wrapper Execution Gate")
    say("=" * 68)
    say(f"Target: {TARGET_VALUE}")
    say(f"Per-wrapper timeout: {WRAPPER_TIMEOUT_SECONDS}s")
    say("")

    env = os.environ.copy()
    env["PATH"] = str(BIN) + os.pathsep + env.get("PATH", "")

    results = []

    for index, name in enumerate(CONNECTORS, start=1):
        say(f"[{index}/6] wrapper: {name}")

        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--child",
                    name,
                ],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=WRAPPER_TIMEOUT_SECONDS,
                check=False,
            )

            stdout_lines = [
                line.strip()
                for line in (completed.stdout or "").splitlines()
                if line.strip()
            ]

            payload = None
            for line in reversed(stdout_lines):
                try:
                    payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue

            if payload is None:
                payload = {
                    "connector_name": name,
                    "error": "child produced no JSON payload",
                    "stdout": stdout_lines[-30:],
                    "stderr": (completed.stderr or "")[-4000:],
                }

            payload["child_exit_code"] = completed.returncode
            payload["child_stderr"] = (
                completed.stderr or ""
            )[-4000:]

            results.append(payload)

            error = payload.get("error")
            result = payload.get("result") or {}

            if error:
                say("      FAIL")
                first_line = error.strip().splitlines()[-1]
                say(f"      {first_line[:220]}")
            else:
                say(
                    "      PASS "
                    f"type={result.get('result_type')} "
                    f"findings={result.get('findings_count')} "
                    f"status={result.get('status')}"
                )
                say(
                    f"      class={payload.get('class')} "
                    f"execute{payload.get('execute_signature')}"
                )

        except subprocess.TimeoutExpired:
            results.append(
                {
                    "connector_name": name,
                    "timeout": True,
                    "error": (
                        f"wrapper exceeded hard timeout of "
                        f"{WRAPPER_TIMEOUT_SECONDS}s"
                    ),
                }
            )
            say(
                f"      TIMEOUT after {WRAPPER_TIMEOUT_SECONDS}s"
            )

    report = {
        "gate_version": 1,
        "target": TARGET_VALUE,
        "wrapper_timeout_seconds": WRAPPER_TIMEOUT_SECONDS,
        "results": results,
        "notes": [
            "This gate executes project connector wrappers, not raw CLIs.",
            "No DB persistence service is called.",
            "No vulnerability scanner is invoked.",
        ],
    }

    json_path = OUT / "wrapper_gate.json"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    pass_count = sum(
        1
        for item in results
        if not item.get("error") and not item.get("timeout")
    )
    fail_count = len(results) - pass_count

    say("")
    say("SUMMARY")
    say("-" * 68)
    say(f"PASS={pass_count} FAIL={fail_count}")

    for item in results:
        name = item["connector_name"]

        if item.get("error") or item.get("timeout"):
            say(f"  FAIL {name}")
        else:
            result = item.get("result") or {}
            say(
                f"  PASS {name:12} "
                f"findings={result.get('findings_count')} "
                f"type={result.get('result_type')}"
            )

    say("")
    say(f"JSON: {json_path}")
    say("")
    say("OSINT EXPANSION 04B WRAPPER EXECUTION GATE: PASS")
    say(
        "PASS here means the diagnostic gate completed; individual connector "
        "FAIL/TIMEOUT results are expected inputs for the next production patch."
    )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--child",
        choices=tuple(CONNECTORS),
        default=None,
    )
    args = parser.parse_args()

    if args.child:
        return child_main(args.child)

    return parent_main()


if __name__ == "__main__":
    raise SystemExit(main())

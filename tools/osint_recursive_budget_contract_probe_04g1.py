
"""
OSINT Expansion 04G1 — Recursive Budget Contract Probe

Collects the exact current recursive OSINT execution path before wiring
ConnectorRequest.limit into max_pivots_per_entity / max_new_entities.

No production code modifications.
No DB writes.
No network calls.
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
import re
import traceback
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_04g1"

CANDIDATE_MODULES = [
    "app.application.osint_recursive_enrichment_service",
    "app.osint.enrichment_execution",
    "app.osint.manager",
    "app.osint.pipeline",
    "app.osint.runner",
    "app.osint.models",
    "app.osint.result",
    "app.osint.finding_persistence",
    "app.osint.pivot_candidates",
    "app.osint.pivot_policy",
    "app.osint.pivot_router",
    "app.osint.registry",
]

SOURCE_PATHS = [
    "app/application/osint_recursive_enrichment_service.py",
    "app/osint/enrichment_execution.py",
    "app/osint/manager.py",
    "app/osint/pipeline.py",
    "app/osint/runner.py",
    "app/osint/models.py",
    "app/osint/result.py",
    "app/osint/finding_persistence.py",
    "app/osint/pivot_candidates.py",
    "app/osint/pivot_policy.py",
    "app/osint/pivot_router.py",
    "app/osint/registry.py",
    "app/osint/base_connector.py",
]


def sig(obj):
    try:
        return str(inspect.signature(obj))
    except Exception:
        return None


def describe_module(module_name: str) -> dict:
    result = {
        "module": module_name,
        "import_ok": False,
        "error": None,
        "source_file": None,
        "classes": [],
        "functions": {},
        "budget_mentions": {},
    }

    try:
        module = importlib.import_module(module_name)
    except Exception:
        result["error"] = traceback.format_exc(limit=10)
        return result

    result["import_ok"] = True
    source_file = inspect.getsourcefile(module)

    if source_file:
        path = Path(source_file).resolve()
        try:
            result["source_file"] = str(path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            result["source_file"] = str(path)

    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and obj.__module__ == module_name:
            methods = {}
            for method_name, member in inspect.getmembers(obj):
                if method_name.startswith("__"):
                    continue
                if inspect.isfunction(member) or inspect.ismethod(member):
                    methods[method_name] = sig(member)

            result["classes"].append({
                "name": obj.__name__,
                "signature": sig(obj),
                "methods": methods,
                "bases": [
                    f"{base.__module__}.{base.__name__}"
                    for base in obj.__bases__
                ],
            })

        elif inspect.isfunction(obj) and obj.__module__ == module_name:
            if not name.startswith("_"):
                result["functions"][name] = sig(obj)

    try:
        source = inspect.getsource(module)
    except Exception:
        source = ""

    patterns = {
        "ConnectorRequest": r"\bConnectorRequest\b",
        "limit": r"\blimit\b",
        "max_pivots_per_entity": r"\bmax_pivots_per_entity\b",
        "max_new_entities": r"\bmax_new_entities\b",
        "max_depth": r"\bmax_depth\b",
        "findings": r"\bfindings\b",
        "pivot": r"\bpivot",
        "remaining": r"\bremaining\b",
        "budget": r"\bbudget\b",
        "execute": r"\bexecute\b",
        "manager": r"\bmanager\b",
        "pipeline": r"\bpipeline\b",
    }

    result["budget_mentions"] = {
        key: len(re.findall(pattern, source, flags=re.IGNORECASE))
        for key, pattern in patterns.items()
    }

    interesting_lines = []
    for lineno, line in enumerate(source.splitlines(), 1):
        lower = line.lower()
        if any(
            token in lower
            for token in (
                "connectorrequest",
                "max_pivots_per_entity",
                "max_new_entities",
                "max_depth",
                "remaining",
                "budget",
                "limit=",
                "findings",
                "pivot",
            )
        ):
            interesting_lines.append({
                "line": lineno,
                "text": line.rstrip()[:500],
            })

    result["interesting_lines"] = interesting_lines[:250]
    return result


def source_inventory() -> list[dict]:
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
    bundle = OUT / "osint_04g1_recursive_budget_bundle.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(report_path, "recursive_budget_contract.json")

        for rel in SOURCE_PATHS:
            path = ROOT / rel
            if path.exists() and path.is_file():
                zf.write(path, rel)

    return bundle


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    print("OSINT Expansion 04G1 — Recursive Budget Contract Probe", flush=True)
    print("=" * 70, flush=True)

    modules = []
    for index, module_name in enumerate(CANDIDATE_MODULES, 1):
        print(f"[{index}/{len(CANDIDATE_MODULES)}] {module_name}", flush=True)
        item = describe_module(module_name)
        modules.append(item)

        print(
            f"      import_ok={item['import_ok']} "
            f"source={item.get('source_file')} "
            f"ConnectorRequest={item['budget_mentions'].get('ConnectorRequest', 0)} "
            f"max_pivots={item['budget_mentions'].get('max_pivots_per_entity', 0)} "
            f"max_new={item['budget_mentions'].get('max_new_entities', 0)} "
            f"limit={item['budget_mentions'].get('limit', 0)}",
            flush=True,
        )

    report = {
        "probe_version": 1,
        "modules": modules,
        "source_inventory": source_inventory(),
        "notes": [
            "No network calls are made.",
            "No database writes are made.",
            "No production code is modified.",
            "The bundle contains only current project source files relevant to recursive OSINT budgeting.",
        ],
    }

    report_path = OUT / "recursive_budget_contract.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    bundle = build_bundle(report_path)

    print("", flush=True)
    print(f"JSON:   {report_path}", flush=True)
    print(f"BUNDLE: {bundle}", flush=True)
    print("", flush=True)
    print("OSINT EXPANSION 04G1 RECURSIVE BUDGET CONTRACT PROBE: PASS", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

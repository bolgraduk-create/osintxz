
"""
OSINT Expansion 05E1 — Persistence / Entity / Pivot Contract Probe

Purpose:
Capture the exact current production path before wiring the verified discovery
chain into persistence and recursive pivots.

No network calls.
No DB writes.
No production modifications.
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
OUT = ROOT / "storage" / "cache" / "osint_expansion_05e1"

MODULES = [
    "app.application.osint_enrichment_service",
    "app.application.osint_recursive_enrichment_service",
    "app.osint.enrichment_execution",
    "app.osint.finding_persistence",
    "app.osint.pivot_candidates",
    "app.osint.pivot_policy",
    "app.osint.pivot_router",
    "app.osint.models",
    "app.osint.result",
]

SOURCE_PATHS = [
    "app/application/osint_enrichment_service.py",
    "app/application/osint_recursive_enrichment_service.py",
    "app/osint/enrichment_execution.py",
    "app/osint/finding_persistence.py",
    "app/osint/pivot_candidates.py",
    "app/osint/pivot_policy.py",
    "app/osint/pivot_router.py",
    "app/osint/models.py",
    "app/osint/result.py",
    "app/osint/manager.py",
    "app/osint/pipeline.py",
    "app/osint/registry.py",
    "app/osint/base_connector.py",
    "app/osint/capabilities.py",
    "app/services/source_service.py",
    "app/services/evidence_service.py",
    "app/services/entity_service.py",
    "app/services/evidence_link_service.py",
    "app/models/source.py",
    "app/models/evidence.py",
    "app/models/entity.py",
    "app/models/evidence_entity.py",
]


def signature(obj):
    try:
        return str(inspect.signature(obj))
    except Exception:
        return None


def relative_source_file(module) -> str | None:
    source_file = inspect.getsourcefile(module)
    if not source_file:
        return None

    path = Path(source_file).resolve()
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def describe_module(module_name: str) -> dict:
    result = {
        "module": module_name,
        "import_ok": False,
        "error": None,
        "source_file": None,
        "classes": [],
        "functions": {},
        "mentions": {},
        "interesting_lines": [],
    }

    try:
        module = importlib.import_module(module_name)
    except Exception:
        result["error"] = traceback.format_exc(limit=12)
        return result

    result["import_ok"] = True
    result["source_file"] = relative_source_file(module)

    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and obj.__module__ == module_name:
            methods = {}
            properties = []

            for method_name, member in inspect.getmembers(obj):
                if method_name.startswith("__"):
                    continue

                if inspect.isfunction(member) or inspect.ismethod(member):
                    methods[method_name] = signature(member)
                elif isinstance(
                    inspect.getattr_static(obj, method_name, None),
                    property,
                ):
                    properties.append(method_name)

            result["classes"].append(
                {
                    "name": obj.__name__,
                    "signature": signature(obj),
                    "methods": methods,
                    "properties": sorted(properties),
                    "bases": [
                        f"{base.__module__}.{base.__name__}"
                        for base in obj.__bases__
                    ],
                }
            )

        elif inspect.isfunction(obj) and obj.__module__ == module_name:
            if not name.startswith("_"):
                result["functions"][name] = signature(obj)

    try:
        source = inspect.getsource(module)
    except Exception:
        source = ""

    patterns = {
        "persist_execution": r"\bpersist_execution\b",
        "persist_findings": r"\bpersist_findings\b",
        "entities_created": r"\bentities_created\b",
        "NewEntityBudget": r"\bNewEntityBudget\b",
        "remaining_new_entities": r"\bremaining_new_entities\b",
        "ConnectorRequest": r"\bConnectorRequest\b",
        "request_limit": r"request\.limit",
        "from_enrichment_result": r"\bfrom_enrichment_result\b",
        "from_persistence_results": r"\bfrom_persistence_results\b",
        "parent_entity_id": r"\bparent_entity_id\b",
        "EvidenceEntity": r"\bEvidenceEntity\b",
        "commit": r"\bcommit\b",
        "flush": r"\bflush\b",
        "rollback": r"\brollback\b",
    }

    result["mentions"] = {
        key: len(
            re.findall(
                pattern,
                source,
                flags=re.IGNORECASE,
            )
        )
        for key, pattern in patterns.items()
    }

    tokens = (
        "persist_execution",
        "persist_findings",
        "entities_created",
        "newentitybudget",
        "remaining_new_entities",
        "connectorrequest",
        "request.limit",
        "from_enrichment_result",
        "from_persistence_results",
        "parent_entity_id",
        "evidenceentity",
        "commit(",
        "flush(",
        "rollback(",
        "new_entities_count",
        "max_new_entities",
        "candidate",
        "pivot",
    )

    lines = []
    for lineno, line in enumerate(source.splitlines(), 1):
        lower = line.lower()
        if any(token in lower for token in tokens):
            lines.append(
                {
                    "line": lineno,
                    "text": line.rstrip()[:500],
                }
            )

    result["interesting_lines"] = lines[:350]
    return result


def source_inventory() -> list[dict]:
    items = []

    for relative in SOURCE_PATHS:
        path = ROOT / relative
        items.append(
            {
                "path": relative,
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else None,
            }
        )

    return items


def build_bundle(report_path: Path) -> Path:
    bundle = OUT / "osint_05e1_persistence_pivot_bundle.zip"

    with zipfile.ZipFile(
        bundle,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.write(
            report_path,
            "persistence_pivot_contract.json",
        )

        for relative in SOURCE_PATHS:
            path = ROOT / relative
            if path.exists() and path.is_file():
                archive.write(
                    path,
                    relative,
                )

    return bundle


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    print(
        "OSINT Expansion 05E1 — Persistence / Entity / Pivot Contract Probe",
        flush=True,
    )
    print("=" * 74, flush=True)

    modules = []

    for index, module_name in enumerate(MODULES, 1):
        print(
            f"[{index}/{len(MODULES)}] {module_name}",
            flush=True,
        )

        item = describe_module(module_name)
        modules.append(item)

        print(
            "      "
            f"import_ok={item['import_ok']} "
            f"source={item.get('source_file')} "
            f"persist={item['mentions'].get('persist_execution', 0)} "
            f"entities_created={item['mentions'].get('entities_created', 0)} "
            f"budget={item['mentions'].get('NewEntityBudget', 0)} "
            f"request_limit={item['mentions'].get('request_limit', 0)}",
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
            "The bundle captures the exact current persistence/entity/pivot path after 04G2 and 05D3.",
        ],
    }

    report_path = OUT / "persistence_pivot_contract.json"
    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = build_bundle(report_path)

    print("", flush=True)
    print(f"JSON:   {report_path}", flush=True)
    print(f"BUNDLE: {bundle}", flush=True)
    print("", flush=True)
    print(
        "OSINT EXPANSION 05E1 PERSISTENCE/PIVOT CONTRACT PROBE: PASS",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

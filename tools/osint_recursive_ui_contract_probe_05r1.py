
"""
OSINT Expansion 05R1 — Recursive E2E + Desktop UI Wiring Contract Probe

Purpose:
Determine the exact current production path for recursive OSINT and whether the
desktop UI/application layer actually invokes it.

No network calls.
No DB writes.
No production changes.
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
import re
import traceback
import zipfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_05r1"

MODULES = (
    "app.application.osint_recursive_enrichment_service",
    "app.application.osint_enrichment_service",
    "app.osint.enrichment_execution",
    "app.osint.pivot_candidates",
    "app.osint.pivot_router",
    "app.osint.pivot_policy",
    "app.osint.pipeline",
    "app.osint.manager",
    "app.core.service_container",
    "app.application.service_container",
    "app.interface.service_container",
)

SEARCH_ROOTS = (
    ROOT / "app" / "interface",
    ROOT / "app" / "application",
    ROOT / "app" / "services",
    ROOT / "app",
)

TOKENS = (
    "OsintRecursiveEnrichmentService",
    "recursive_enrichment",
    ".enrich(",
    "enrich_target(",
    "start_investigation",
    "run_investigation",
    "start_osint",
    "run_osint",
    "osint",
    "investigation",
    "desktop",
    "button",
    "signal",
    "slot",
)


def safe_signature(obj: Any) -> str | None:
    try:
        return str(inspect.signature(obj))
    except Exception:
        return None


def relative(path: str | Path | None) -> str | None:
    if not path:
        return None
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def describe_module(module_name: str) -> dict[str, Any]:
    item = {
        "module": module_name,
        "import_ok": False,
        "source_file": None,
        "error": None,
        "classes": [],
        "functions": {},
        "mentions": {},
        "interesting_lines": [],
    }

    try:
        module = importlib.import_module(module_name)
    except Exception:
        item["error"] = traceback.format_exc(limit=10)
        return item

    item["import_ok"] = True
    item["source_file"] = relative(inspect.getsourcefile(module))

    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and obj.__module__ == module_name:
            methods = {}
            for method_name, member in inspect.getmembers(obj):
                if method_name.startswith("__"):
                    continue
                if inspect.isfunction(member) or inspect.ismethod(member):
                    methods[method_name] = safe_signature(member)

            item["classes"].append(
                {
                    "name": obj.__name__,
                    "signature": safe_signature(obj),
                    "methods": methods,
                }
            )

        elif inspect.isfunction(obj) and obj.__module__ == module_name:
            if not name.startswith("_"):
                item["functions"][name] = safe_signature(obj)

    try:
        source = inspect.getsource(module)
    except Exception:
        source = ""

    patterns = {
        "recursive_service": r"\bOsintRecursiveEnrichmentService\b",
        "recursive_enrich_call": r"\.enrich\s*\(",
        "enrich_target_call": r"\benrich_target\s*\(",
        "execute_defaults_call": r"\bexecute_defaults\s*\(",
        "service_container": r"\bServiceContainer\b",
        "ui": r"\b(button|signal|slot|window|widget|viewmodel|controller)\b",
    }

    item["mentions"] = {
        key: len(re.findall(pattern, source, flags=re.IGNORECASE))
        for key, pattern in patterns.items()
    }

    for lineno, line in enumerate(source.splitlines(), 1):
        lower = line.casefold()
        if any(token.casefold() in lower for token in TOKENS):
            item["interesting_lines"].append(
                {
                    "line": lineno,
                    "text": line.rstrip()[:600],
                }
            )

    item["interesting_lines"] = item["interesting_lines"][:300]
    return item


def iter_unique_python_files():
    seen = set()

    for base in SEARCH_ROOTS:
        if not base.exists():
            continue

        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue

            resolved = str(path.resolve()).casefold()
            if resolved in seen:
                continue

            seen.add(resolved)
            yield path


def score_source(path: Path, text: str) -> tuple[int, dict[str, int]]:
    lower = text.casefold()
    name = path.name.casefold()

    counts = {
        token: lower.count(token.casefold())
        for token in TOKENS
    }

    score = 0

    if "interface" in str(path).casefold():
        score += 20
    if any(part in name for part in ("osint", "investigation", "desktop", "main_window", "controller")):
        score += 30

    score += counts["OsintRecursiveEnrichmentService"] * 100
    score += counts["recursive_enrichment"] * 80
    score += counts[".enrich("] * 40
    score += counts["enrich_target("] * 25
    score += counts["start_investigation"] * 50
    score += counts["run_investigation"] * 50
    score += counts["start_osint"] * 50
    score += counts["run_osint"] * 50
    score += min(40, counts["osint"])
    score += min(30, counts["investigation"])

    return score, {
        key: value for key, value in counts.items() if value
    }


def source_scan() -> list[dict[str, Any]]:
    records = []

    for path in iter_unique_python_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        score, counts = score_source(path, text)

        if score < 20:
            continue

        interesting = []
        for lineno, line in enumerate(text.splitlines(), 1):
            lower = line.casefold()
            if any(token.casefold() in lower for token in TOKENS):
                interesting.append(
                    {
                        "line": lineno,
                        "text": line.rstrip()[:600],
                    }
                )

        records.append(
            {
                "path": relative(path),
                "score": score,
                "size": path.stat().st_size,
                "counts": counts,
                "interesting_lines": interesting[:300],
            }
        )

    records.sort(key=lambda x: (-x["score"], x["path"]))
    return records[:100]


def likely_ui_wiring(scan: list[dict[str, Any]]) -> dict[str, Any]:
    recursive_refs = []
    one_shot_refs = []
    ui_osint_refs = []

    for item in scan:
        path = item["path"]
        lower_path = path.casefold()

        for line in item["interesting_lines"]:
            text = line["text"]
            lower = text.casefold()

            record = {
                "path": path,
                "line": line["line"],
                "text": text,
            }

            if (
                "osintrecursiveenrichmentservice" in lower
                or "recursive_enrichment" in lower
            ):
                recursive_refs.append(record)

            if "enrich_target(" in lower or "execute_defaults(" in lower:
                one_shot_refs.append(record)

            if (
                "interface/" in lower_path
                and (
                    "osint" in lower
                    or "investigation" in lower
                    or "enrich" in lower
                )
            ):
                ui_osint_refs.append(record)

    return {
        "recursive_refs": recursive_refs[:100],
        "one_shot_refs": one_shot_refs[:100],
        "ui_osint_refs": ui_osint_refs[:150],
        "ui_probably_calls_recursive": any(
            "interface/" in item["path"].casefold()
            for item in recursive_refs
        ),
    }


def selected_paths(
    modules: list[dict[str, Any]],
    scan: list[dict[str, Any]],
) -> list[Path]:
    chosen: list[Path] = []

    for module in modules:
        source_file = module.get("source_file")
        if not source_file:
            continue
        path = ROOT / source_file
        if path.exists() and path.is_file():
            chosen.append(path)

    for item in scan[:50]:
        path = ROOT / item["path"]
        if path.exists() and path.is_file():
            chosen.append(path)

    explicit = (
        "app/application/osint_recursive_enrichment_service.py",
        "app/application/osint_enrichment_service.py",
        "app/osint/enrichment_execution.py",
        "app/osint/pivot_candidates.py",
        "app/osint/pivot_router.py",
        "app/osint/pivot_policy.py",
        "app/osint/pipeline.py",
        "app/osint/manager.py",
    )

    for relative_path in explicit:
        path = ROOT / relative_path
        if path.exists():
            chosen.append(path)

    unique = []
    seen = set()

    for path in chosen:
        key = str(path.resolve()).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)

    return unique[:70]


def build_bundle(
    report_path: Path,
    modules: list[dict[str, Any]],
    scan: list[dict[str, Any]],
) -> Path:
    bundle = OUT / "osint_05r1_recursive_ui_bundle.zip"

    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(report_path, "recursive_ui_contract.json")

        for path in selected_paths(modules, scan):
            archive.write(path, relative(path))

    return bundle


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    print(
        "OSINT Expansion 05R1 — Recursive E2E + Desktop UI Wiring Contract Probe",
        flush=True,
    )
    print("=" * 82, flush=True)

    modules = []

    for module_name in MODULES:
        item = describe_module(module_name)
        modules.append(item)

        print(
            f"{module_name:<52} "
            f"import_ok={item['import_ok']} "
            f"recursive={item['mentions'].get('recursive_service', 0)} "
            f"enrich_calls={item['mentions'].get('recursive_enrich_call', 0)} "
            f"source={item.get('source_file')}",
            flush=True,
        )

    print("", flush=True)
    print("Scanning application/interface wiring...", flush=True)

    scan = source_scan()
    wiring = likely_ui_wiring(scan)

    for item in scan[:25]:
        print(
            f"  score={item['score']:<4} {item['path']}",
            flush=True,
        )

    print("", flush=True)
    print(
        f"recursive_refs={len(wiring['recursive_refs'])}",
        flush=True,
    )
    print(
        f"ui_osint_refs={len(wiring['ui_osint_refs'])}",
        flush=True,
    )
    print(
        f"ui_probably_calls_recursive={wiring['ui_probably_calls_recursive']}",
        flush=True,
    )

    report = {
        "probe_version": 1,
        "modules": modules,
        "source_scan": scan,
        "wiring_summary": wiring,
        "next_gate_requirements": [
            "Use the real OsintRecursiveEnrichmentService production entry point.",
            "Run a benign live seed such as example.com.",
            "Wrap persistence in a temporary Case/transaction and rollback.",
            "Verify at least one second-level pivot is actually executed.",
            "Verify depth/entity/pivot budgets stay within policy.",
            "Verify whether desktop UI invokes the same recursive service.",
            "If UI is not wired, patch only the minimal application/controller boundary.",
        ],
        "notes": [
            "No network calls are made.",
            "No database writes are made.",
            "No production code is modified.",
        ],
    }

    report_path = OUT / "recursive_ui_contract.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    bundle = build_bundle(report_path, modules, scan)

    print("", flush=True)
    print(f"JSON:   {report_path}", flush=True)
    print(f"BUNDLE: {bundle}", flush=True)
    print("", flush=True)
    print(
        "OSINT EXPANSION 05R1 RECURSIVE/UI CONTRACT PROBE: PASS",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

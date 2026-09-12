
"""
OSINT Expansion 05F0A — Chat Participant Identity Contract Probe

Goal:
Capture the exact CURRENT Telegram/chat import and identity data model before
implementing participant identity resolution.

We need to know exactly which of these are already available and persisted:
- Telegram/user numeric IDs
- @username
- first_name / last_name / display name
- author/sender labels from exports
- local nicknames / participant labels
- account/entity/message links
- existing entity-resolution infrastructure

This probe:
- performs NO network calls;
- performs NO DB writes;
- modifies NO production code;
- inspects current Python source and ORM model metadata;
- bundles only the most relevant source/test files for the 05F0B patch.
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
OUT = ROOT / "storage" / "cache" / "osint_expansion_05f0a"

APP_ROOT = ROOT / "app"
TEST_ROOT = ROOT / "tests"

MODEL_MODULE_CANDIDATES = (
    "app.models.message",
    "app.models.entity",
    "app.models.account",
    "app.models.relationship",
    "app.models.source",
    "app.models.evidence",
    "app.models.document",
)

TELEGRAM_MODULE_CANDIDATES = (
    "app.importers.telegram_importer",
    "app.importers.telegram",
    "app.collection.telegram",
    "app.collection.collectors.telegram",
    "app.services.telegram_import_service",
    "app.application.telegram_import_service",
    "app.application.telegram_import",
)

IDENTITY_MODULE_CANDIDATES = (
    "app.entity_resolution.normalizer",
    "app.entity_resolution.duplicate_detector",
    "app.entity_resolution.service",
    "app.services.entity_service",
)

KEYWORDS = (
    "telegram",
    "message",
    "sender",
    "author",
    "from_id",
    "from_name",
    "username",
    "first_name",
    "last_name",
    "display_name",
    "participant",
    "peer_id",
    "user_id",
    "telegram_id",
    "account",
    "alias",
    "nickname",
    "entity_resolution",
    "normalize",
)

HIGH_VALUE_NAME_TOKENS = (
    "telegram",
    "message",
    "participant",
    "account",
    "entity",
    "relationship",
    "identity",
    "resolver",
    "resolution",
    "normalizer",
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


def mapper_description(cls: type) -> dict[str, Any]:
    mapper = getattr(cls, "__mapper__", None)

    if mapper is None:
        return {}

    columns = []

    for column in mapper.columns:
        columns.append(
            {
                "name": column.name,
                "key": column.key,
                "type": str(column.type),
                "nullable": bool(column.nullable),
                "primary_key": bool(column.primary_key),
                "foreign_keys": sorted(
                    fk.target_fullname
                    for fk in column.foreign_keys
                ),
            }
        )

    relationships = []

    for relationship in mapper.relationships:
        relationships.append(
            {
                "key": relationship.key,
                "target": (
                    f"{relationship.mapper.class_.__module__}."
                    f"{relationship.mapper.class_.__name__}"
                ),
                "uselist": bool(relationship.uselist),
            }
        )

    return {
        "table": mapper.local_table.name,
        "columns": columns,
        "relationships": relationships,
    }


def describe_module(module_name: str) -> dict[str, Any]:
    result = {
        "module": module_name,
        "import_ok": False,
        "source_file": None,
        "error": None,
        "classes": [],
        "functions": {},
    }

    try:
        module = importlib.import_module(module_name)
    except Exception:
        result["error"] = traceback.format_exc(limit=10)
        return result

    result["import_ok"] = True
    result["source_file"] = relative(
        inspect.getsourcefile(module)
    )

    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and obj.__module__ == module_name:
            methods = {}

            for method_name, member in inspect.getmembers(obj):
                if method_name.startswith("__"):
                    continue

                if inspect.isfunction(member) or inspect.ismethod(member):
                    methods[method_name] = safe_signature(member)

            result["classes"].append(
                {
                    "name": obj.__name__,
                    "signature": safe_signature(obj),
                    "methods": methods,
                    "mapper": mapper_description(obj),
                }
            )

        elif inspect.isfunction(obj) and obj.__module__ == module_name:
            if not name.startswith("_"):
                result["functions"][name] = safe_signature(obj)

    return result


def iter_python_files():
    for base in (APP_ROOT, TEST_ROOT):
        if not base.exists():
            continue

        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def score_file(path: Path, text: str) -> tuple[int, dict[str, int]]:
    lower_name = path.name.casefold()
    lower_text = text.casefold()

    counts = {
        keyword: lower_text.count(keyword.casefold())
        for keyword in KEYWORDS
    }

    score = 0

    for token in HIGH_VALUE_NAME_TOKENS:
        if token in lower_name:
            score += 35

    # Strongly prefer Telegram files and model/import/service code.
    if "telegram" in lower_text:
        score += 60

    if "from_id" in lower_text:
        score += 25

    if "username" in lower_text:
        score += 15

    if "sender" in lower_text or "author" in lower_text:
        score += 15

    if "participant" in lower_text:
        score += 20

    if "entity" in lower_text and "message" in lower_text:
        score += 10

    score += min(
        120,
        sum(counts.values()),
    )

    return score, counts


def interesting_lines(text: str) -> list[dict[str, Any]]:
    patterns = (
        "telegram",
        "sender",
        "author",
        "from_id",
        "from_name",
        "username",
        "first_name",
        "last_name",
        "display_name",
        "participant",
        "peer_id",
        "user_id",
        "telegram_id",
        "alias",
        "nickname",
        "entity",
        "account",
    )

    found = []

    for lineno, line in enumerate(text.splitlines(), 1):
        lower = line.casefold()

        if any(token in lower for token in patterns):
            found.append(
                {
                    "line": lineno,
                    "text": line.rstrip()[:600],
                }
            )

    return found[:400]


def source_scan() -> list[dict[str, Any]]:
    records = []

    for path in iter_python_files():
        try:
            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            continue

        score, counts = score_file(
            path,
            text,
        )

        if score < 25:
            continue

        records.append(
            {
                "path": relative(path),
                "score": score,
                "size": path.stat().st_size,
                "keyword_counts": {
                    key: value
                    for key, value in counts.items()
                    if value
                },
                "interesting_lines": interesting_lines(text),
            }
        )

    records.sort(
        key=lambda item: (
            -item["score"],
            item["path"],
        )
    )

    return records[:80]


def selected_bundle_paths(scan: list[dict[str, Any]]) -> list[Path]:
    chosen: list[Path] = []

    # First, high-scoring scanned files.
    for item in scan[:40]:
        path = ROOT / item["path"]

        if path.exists() and path.is_file():
            chosen.append(path)

    # Also capture exact likely files even if keyword scoring is low.
    explicit_candidates = (
        "app/importers/telegram_importer.py",
        "app/application/telegram_import_service.py",
        "app/services/telegram_import_service.py",
        "app/models/message.py",
        "app/models/entity.py",
        "app/models/account.py",
        "app/models/relationship.py",
        "app/entity_resolution/normalizer.py",
        "app/entity_resolution/duplicate_detector.py",
        "app/services/entity_service.py",
    )

    for relative_path in explicit_candidates:
        path = ROOT / relative_path

        if path.exists() and path.is_file():
            chosen.append(path)

    unique: list[Path] = []
    seen = set()

    for path in chosen:
        key = str(path.resolve()).casefold()

        if key in seen:
            continue

        seen.add(key)
        unique.append(path)

    return unique[:50]


def build_bundle(
    report_path: Path,
    scan: list[dict[str, Any]],
) -> Path:
    bundle = (
        OUT
        / "osint_05f0a_chat_identity_bundle.zip"
    )

    paths = selected_bundle_paths(
        scan
    )

    with zipfile.ZipFile(
        bundle,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.write(
            report_path,
            "chat_identity_contract.json",
        )

        for path in paths:
            archive.write(
                path,
                relative(path),
            )

    return bundle


def main() -> int:
    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "OSINT Expansion 05F0A — Chat Participant Identity Contract Probe",
        flush=True,
    )
    print(
        "=" * 78,
        flush=True,
    )

    modules = []

    candidates = (
        MODEL_MODULE_CANDIDATES
        + TELEGRAM_MODULE_CANDIDATES
        + IDENTITY_MODULE_CANDIDATES
    )

    seen_modules = set()

    for module_name in candidates:
        if module_name in seen_modules:
            continue

        seen_modules.add(module_name)

        item = describe_module(
            module_name
        )

        modules.append(
            item
        )

        print(
            f"{module_name:<48} "
            f"import_ok={item['import_ok']} "
            f"source={item.get('source_file')}",
            flush=True,
        )

    print(
        "",
        flush=True,
    )
    print(
        "Scanning current app/tests for Telegram participant identity fields...",
        flush=True,
    )

    scan = source_scan()

    for item in scan[:20]:
        counts_preview = ", ".join(
            f"{key}={value}"
            for key, value
            in list(
                item["keyword_counts"].items()
            )[:8]
        )

        print(
            f"  score={item['score']:<4} {item['path']}",
            flush=True,
        )

        if counts_preview:
            print(
                f"       {counts_preview}",
                flush=True,
            )

    report = {
        "probe_version": 1,
        "modules": modules,
        "source_scan": scan,
        "questions_for_05f0b": {
            "stable_numeric_identity_available": (
                "Detect whether Telegram/user IDs are already parsed and persisted."
            ),
            "username_available": (
                "Detect @username/current username storage and provenance."
            ),
            "display_name_available": (
                "Detect first/last/display name or export sender label storage."
            ),
            "local_label_available": (
                "Detect local chat/export nickname labels and whether they are "
                "distinguishable from account names."
            ),
            "message_author_link_available": (
                "Detect how Message rows point to participants/entities/accounts."
            ),
            "existing_resolution_reusable": (
                "Detect existing normalizer/duplicate/entity-resolution code that "
                "should be extended rather than duplicated."
            ),
        },
        "design_constraints": [
            "Stable platform/user IDs must dominate identity resolution when available.",
            "Username/name similarity alone must never silently merge two people.",
            "Ambiguous matches must remain separate hypotheses with confidence/provenance.",
            "Identity resolution should reuse existing Core/Application entity resolution.",
            "Telegram-specific parsing may live in Infrastructure/Importer, but identity logic belongs outside it.",
        ],
        "notes": [
            "No network calls are made.",
            "No database writes are made.",
            "No production code is modified.",
            "The bundle contains only current files relevant to chat participant identity.",
        ],
    }

    report_path = (
        OUT
        / "chat_identity_contract.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    bundle = build_bundle(
        report_path,
        scan,
    )

    print(
        "",
        flush=True,
    )
    print(
        f"JSON:   {report_path}",
        flush=True,
    )
    print(
        f"BUNDLE: {bundle}",
        flush=True,
    )
    print(
        "",
        flush=True,
    )
    print(
        "OSINT EXPANSION 05F0A CHAT IDENTITY CONTRACT PROBE: PASS",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

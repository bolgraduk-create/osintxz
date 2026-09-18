from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys


NEW_FILES = (
    "app/intelligence_sources/__init__.py",
    "app/intelligence_sources/contracts.py",
    "app/intelligence_sources/catalog.py",
    "app/intelligence_sources/policy.py",
    "tests/test_intelligence_source_federation.py",
)

SERVICE_IMPORT = (
    "from app.intelligence_sources.policy import IntelligenceDataSanitizer\n"
)
SERVICE_IMPORT_ANCHOR = (
    "from app.registry_intelligence.contracts import (\n"
)

SERVICE_PARAM_ANCHOR = (
    "        router: RegistryQueryRouter | None = None,\n"
)
SERVICE_PARAM_ADDITION = (
    "        data_sanitizer: IntelligenceDataSanitizer | None = None,\n"
)

SERVICE_INIT_ANCHOR = (
    "        self.router = router or RegistryQueryRouter()\n"
)
SERVICE_INIT_ADDITION = (
    "        self.data_sanitizer = data_sanitizer or IntelligenceDataSanitizer()\n"
)

SERVICE_RECORD_ANCHOR = (
    "                        replace(\n"
    "                            record,\n"
)
SERVICE_RECORD_REPLACEMENT = (
    "                        replace(\n"
    "                            self.data_sanitizer.sanitize(record).value,\n"
)

PERSIST_IMPORT = (
    "from app.intelligence_sources.policy import IntelligenceDataSanitizer\n"
)
PERSIST_IMPORT_ANCHOR = (
    "from app.models.entity import Entity, EntityType\n"
)

PERSIST_INIT_OLD = (
    "    def __init__(self, *, source_service, evidence_service, entity_service,\n"
    "                 evidence_link_service, search_indexing_service=None) -> None:\n"
    "        self.source_service = source_service\n"
)
PERSIST_INIT_NEW = (
    "    def __init__(self, *, source_service, evidence_service, entity_service,\n"
    "                 evidence_link_service, search_indexing_service=None,\n"
    "                 data_sanitizer: IntelligenceDataSanitizer | None = None) -> None:\n"
    "        self.data_sanitizer = data_sanitizer or IntelligenceDataSanitizer()\n"
    "        self.source_service = source_service\n"
)

PERSIST_LOOP_ANCHOR = (
    "        for record in result.records:\n"
)
PERSIST_LOOP_REPLACEMENT = (
    "        for record in result.records:\n"
    "            # Defense in depth: sanitize again at the persistence boundary so\n"
    "            # direct RegistryPersistenceService callers cannot store raw secrets.\n"
    "            record = self.data_sanitizer.sanitize(record).value\n"
)


def _backup(path: Path, label: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(f"{path.name}.before_{label}_{stamp}.bak")
    shutil.copy2(path, target)
    return target


def _insert_before_once(
    text: str,
    *,
    anchor: str,
    addition: str,
    already_present: str,
) -> str:
    if already_present in text:
        return text
    if text.count(anchor) != 1:
        raise RuntimeError(
            "Expected exactly one safe patch anchor; aborting instead of guessing."
        )
    return text.replace(anchor, addition + anchor, 1)


def _insert_after_once(
    text: str,
    *,
    anchor: str,
    addition: str,
    already_present: str,
) -> str:
    if already_present in text:
        return text
    if text.count(anchor) != 1:
        raise RuntimeError(
            "Expected exactly one safe patch anchor; aborting instead of guessing."
        )
    return text.replace(anchor, anchor + addition, 1)


def _replace_once(
    text: str,
    *,
    old: str,
    new: str,
    already_present: str,
) -> str:
    if already_present in text:
        return text
    if text.count(old) != 1:
        raise RuntimeError(
            "Expected exactly one safe replacement anchor; aborting instead of guessing."
        )
    return text.replace(old, new, 1)


def _patch_service(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = _insert_before_once(
        updated,
        anchor=SERVICE_IMPORT_ANCHOR,
        addition=SERVICE_IMPORT,
        already_present=SERVICE_IMPORT,
    )
    updated = _insert_after_once(
        updated,
        anchor=SERVICE_PARAM_ANCHOR,
        addition=SERVICE_PARAM_ADDITION,
        already_present="        data_sanitizer: IntelligenceDataSanitizer | None = None,\n",
    )
    updated = _insert_after_once(
        updated,
        anchor=SERVICE_INIT_ANCHOR,
        addition=SERVICE_INIT_ADDITION,
        already_present="        self.data_sanitizer = data_sanitizer or IntelligenceDataSanitizer()\n",
    )
    updated = _replace_once(
        updated,
        old=SERVICE_RECORD_ANCHOR,
        new=SERVICE_RECORD_REPLACEMENT,
        already_present=(
            "                        replace(\n"
            "                            self.data_sanitizer.sanitize(record).value,\n"
        ),
    )

    if updated == original:
        print(f"[OK] {path} already contains R13.5 changes")
        return

    backup = _backup(path, "source_federation")
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}")
    print(f"[OK] Backup: {backup}")


def _patch_persistence(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = _insert_before_once(
        updated,
        anchor=PERSIST_IMPORT_ANCHOR,
        addition=PERSIST_IMPORT,
        already_present=PERSIST_IMPORT,
    )
    updated = _replace_once(
        updated,
        old=PERSIST_INIT_OLD,
        new=PERSIST_INIT_NEW,
        already_present=(
            "                 data_sanitizer: IntelligenceDataSanitizer | None = None) -> None:\n"
        ),
    )
    updated = _replace_once(
        updated,
        old=PERSIST_LOOP_ANCHOR,
        new=PERSIST_LOOP_REPLACEMENT,
        already_present=(
            "            record = self.data_sanitizer.sanitize(record).value\n"
        ),
    )

    if updated == original:
        print(f"[OK] {path} already contains R13.5 changes")
        return

    backup = _backup(path, "source_federation")
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}")
    print(f"[OK] Backup: {backup}")


def _copy_payload(patch_root: Path, project_root: Path) -> None:
    for relative in NEW_FILES:
        source = patch_root / "payload" / relative
        destination = project_root / relative
        if not source.exists():
            raise FileNotFoundError(f"Patch payload missing: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        print(f"[OK] Installed {relative}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R13.5 Intelligence Source Federation Core."
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=r"C:\\osintxz",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
    )
    args = parser.parse_args()

    patch_root = Path(__file__).resolve().parent
    project_root = Path(args.project_root).resolve()

    service = project_root / "app/application/registry_intelligence_service.py"
    persistence = project_root / "app/application/registry_persistence_service.py"

    missing = [
        str(path)
        for path in (service, persistence)
        if not path.exists()
    ]
    if missing:
        print(
            "[ERROR] Invalid OSINTXZ project root; missing: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    _copy_payload(patch_root, project_root)
    _patch_service(service)
    _patch_persistence(persistence)

    print("[OK] R13.5 Intelligence Source Federation Core installed.")
    print("[INFO] No database migration or new dependency is required.")
    print(
        "[INFO] Raw passwords/tokens/cookies/private keys are now redacted "
        "before Registry search output and again before Registry persistence."
    )

    if args.run_tests:
        command = [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_intelligence_source_federation.py",
            "-q",
        ]
        print("[RUN]", " ".join(command))
        return subprocess.run(
            command,
            cwd=project_root,
            check=False,
        ).returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

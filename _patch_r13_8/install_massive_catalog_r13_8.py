from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

NEW_FILES = (
    "app/intelligence_sources/coverage.py",
    "app/intelligence_sources/builtin_sources.py",
    "tests/test_massive_remote_source_catalog.py",
)

IMPORT_LINE = (
    "from app.intelligence_sources.builtin_sources import "
    "register_massive_remote_sources\n"
)
IMPORT_ANCHOR = "from app.intelligence_sources.catalog import IntelligenceSourceCatalog\n"
INIT_ANCHOR = "        register_darkweb_sources(self.intelligence_source_catalog)\n"
INIT_LINE = (
    "        self.remote_source_coverage = register_massive_remote_sources(\n"
    "            self.intelligence_source_catalog\n"
    "        )\n"
)


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(f"{path.name}.before_massive_catalog_{stamp}.bak")
    shutil.copy2(path, target)
    return target


def _copy_payload(patch_root: Path, project_root: Path) -> None:
    for relative in NEW_FILES:
        source = patch_root / "payload" / relative
        destination = project_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        print(f"[OK] Installed {relative}")


def _patch_init(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original
    addition = (
        "\nfrom app.intelligence_sources.coverage import (\n"
        "    RemoteSourceCoverage,\n"
        "    SourceCoverageEntry,\n"
        "    SourceImplementationStatus,\n"
        ")\n"
        "from app.intelligence_sources.builtin_sources import (\n"
        "    MASSIVE_REMOTE_SOURCES,\n"
        "    register_massive_remote_sources,\n"
        ")\n"
    )
    if "register_massive_remote_sources" not in updated:
        updated = updated.rstrip() + addition + "\n"
    if updated != original:
        backup = _backup(path)
        path.write_text(updated, encoding="utf-8")
        print(f"[OK] Patched {path}")
        print(f"[OK] Backup: {backup}")
    else:
        print(f"[OK] {path} already contains R13.8 changes")


def _patch_service(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original
    if IMPORT_LINE not in updated:
        if updated.count(IMPORT_ANCHOR) != 1:
            raise RuntimeError("R13.6 catalog import anchor not found.")
        updated = updated.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_LINE, 1)
    if "self.remote_source_coverage = register_massive_remote_sources(" not in updated:
        if updated.count(INIT_ANCHOR) != 1:
            raise RuntimeError("R13.7 catalog initialization anchor not found.")
        updated = updated.replace(INIT_ANCHOR, INIT_ANCHOR + INIT_LINE, 1)
    if updated != original:
        backup = _backup(path)
        path.write_text(updated, encoding="utf-8")
        print(f"[OK] Patched {path}")
        print(f"[OK] Backup: {backup}")
    else:
        print(f"[OK] {path} already contains R13.8 changes")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.8 Massive Remote Source Catalog.")
    parser.add_argument("project_root", nargs="?", default=r"C:\\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    patch_root = Path(__file__).resolve().parent
    project_root = Path(args.project_root).resolve()
    service = project_root / "app/core/service_container.py"
    init = project_root / "app/intelligence_sources/__init__.py"
    required = [
        project_root / "app/intelligence_sources/contracts.py",
        project_root / "app/breach_intelligence/service.py",
        project_root / "app/darkweb_intelligence/service.py",
        service,
        init,
    ]
    missing = [str(item) for item in required if not item.exists()]
    if missing:
        print("[ERROR] R13.5-R13.7 are required; missing: " + ", ".join(missing), file=sys.stderr)
        return 2

    _copy_payload(patch_root, project_root)
    _patch_init(init)
    _patch_service(service)
    print("[OK] R13.8 Massive Remote Source Catalog installed.")
    print("[INFO] Catalog entries describe coverage/access only; cataloged sources are not falsely marked as implemented.")
    print("[INFO] No database migration or new dependency is required.")

    if args.run_tests:
        command=[sys.executable,"-m","pytest","tests/test_massive_remote_source_catalog.py","-q"]
        print("[RUN]", " ".join(command))
        return subprocess.run(command,cwd=project_root,check=False).returncode
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

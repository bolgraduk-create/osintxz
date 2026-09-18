from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys


NEW_FILES = (
    "app/intelligence_sources/adapters/__init__.py",
    "app/intelligence_sources/adapters/contracts.py",
    "app/intelligence_sources/adapters/base.py",
    "app/intelligence_sources/adapters/registry.py",
    "app/intelligence_sources/adapters/service.py",
    "app/intelligence_sources/adapters/common.py",
    "app/intelligence_sources/adapters/brreg.py",
    "app/intelligence_sources/adapters/ares.py",
    "app/intelligence_sources/adapters/crossref.py",
    "app/intelligence_sources/adapters/ror.py",
    "app/intelligence_sources/adapters/openalex.py",
    "tests/test_remote_adapter_pack_1.py",
)

IMPORTS = """from app.intelligence_sources.adapters.ares import CzechAresAdapter
from app.intelligence_sources.adapters.brreg import NorwayBrregAdapter
from app.intelligence_sources.adapters.crossref import CrossrefAdapter
from app.intelligence_sources.adapters.openalex import OpenAlexAdapter
from app.intelligence_sources.adapters.registry import RemoteSourceAdapterRegistry
from app.intelligence_sources.adapters.ror import RorAdapter
from app.intelligence_sources.adapters.service import RemoteSourceAdapterService
"""
IMPORT_ANCHOR = "from app.application.registry_intelligence_service import RegistryIntelligenceService\n"

INIT_ANCHOR = "        # M022 Registry Intelligence\n"
INIT_BLOCK = """        # R13.9 — Remote Adapter Pack 1.
        self.remote_source_adapter_registry = RemoteSourceAdapterRegistry()
        self.remote_source_adapter_registry.register(NorwayBrregAdapter())
        self.remote_source_adapter_registry.register(CzechAresAdapter())
        self.remote_source_adapter_registry.register(CrossrefAdapter())
        self.remote_source_adapter_registry.register(RorAdapter())
        self.remote_source_adapter_registry.register(
            OpenAlexAdapter(api_key=settings.openalex_api_key)
        )
        self.remote_source_adapter_service = RemoteSourceAdapterService(
            registry=self.remote_source_adapter_registry
        )

"""

CONFIG_FIELD = "    openalex_api_key: str | None = None\n"
CONFIG_ANCHORS = (
    "    intelligencex_api_key: str | None = None\n",
    "    haveibeenpwned_api_key: str | None = None\n",
)

ENV_BLOCK = "\n# OpenAlex free API key (recommended/required for production-scale API use)\nOPENALEX_API_KEY=\n"


def _backup(path: Path, label: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(f"{path.name}.before_{label}_{stamp}.bak")
    shutil.copy2(path, target)
    return target


def _patch_service(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original

    if "from app.intelligence_sources.adapters.service import RemoteSourceAdapterService\n" not in updated:
        if updated.count(IMPORT_ANCHOR) != 1:
            raise RuntimeError("Safe service-container import anchor not found.")
        updated = updated.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORTS, 1)

    if "self.remote_source_adapter_service = RemoteSourceAdapterService(" not in updated:
        if updated.count(INIT_ANCHOR) != 1:
            raise RuntimeError("M022 Registry Intelligence anchor not found.")
        updated = updated.replace(INIT_ANCHOR, INIT_BLOCK + INIT_ANCHOR, 1)

    if updated != original:
        backup = _backup(path, "remote_adapter_pack_1")
        path.write_text(updated, encoding="utf-8")
        print(f"[OK] Patched {path}")
        print(f"[OK] Backup: {backup}")
    else:
        print(f"[OK] {path} already contains Adapter Pack 1")


def _patch_config(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if "    openalex_api_key:" in original:
        print(f"[OK] {path} already contains OpenAlex setting")
        return
    updated = original
    for anchor in CONFIG_ANCHORS:
        if anchor in updated:
            updated = updated.replace(anchor, anchor + CONFIG_FIELD, 1)
            break
    else:
        raise RuntimeError("Safe OSINT API-key anchor not found in config.py.")
    backup = _backup(path, "openalex")
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}")
    print(f"[OK] Backup: {backup}")


def _patch_env(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if "OPENALEX_API_KEY=" in original:
        print(f"[OK] {path} already contains OpenAlex env setting")
        return
    backup = _backup(path, "openalex")
    path.write_text(original.rstrip() + ENV_BLOCK, encoding="utf-8")
    print(f"[OK] Patched {path}")
    print(f"[OK] Backup: {backup}")


def _patch_coverage(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original
    replacements = {
        'SourceCoverageEntry("no_brreg_entities", Status.CATALOGED, stage="europe")':
            'SourceCoverageEntry("no_brreg_entities", Status.ACTIVE, "NorwayBrregAdapter", "R13.9")',
        'SourceCoverageEntry("cz_ares", Status.CATALOGED, stage="europe")':
            'SourceCoverageEntry("cz_ares", Status.ACTIVE, "CzechAresAdapter", "R13.9 exact-ICO")',
        'SourceCoverageEntry("crossref", Status.CATALOGED, stage="research")':
            'SourceCoverageEntry("crossref", Status.ACTIVE, "CrossrefAdapter", "R13.9")',
        'SourceCoverageEntry("ror", Status.CATALOGED, stage="research")':
            'SourceCoverageEntry("ror", Status.ACTIVE, "RorAdapter", "R13.9")',
        'SourceCoverageEntry("openalex", Status.CATALOGED, stage="research")':
            'SourceCoverageEntry("openalex", Status.ACTIVE, "OpenAlexAdapter", "R13.9 credential-gated")',
    }
    changed = False
    for old, new in replacements.items():
        if new in updated:
            continue
        if old not in updated:
            raise RuntimeError(f"Expected R13.8 coverage entry missing: {old}")
        updated = updated.replace(old, new, 1)
        changed = True
    if changed:
        backup = _backup(path, "remote_adapter_pack_1")
        path.write_text(updated, encoding="utf-8")
        print(f"[OK] Patched {path}")
        print(f"[OK] Backup: {backup}")
    else:
        print(f"[OK] {path} already marks Adapter Pack 1 active")


def _copy_payload(patch_root: Path, project_root: Path) -> None:
    for relative in NEW_FILES:
        src = patch_root / "payload" / relative
        dst = project_root / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"[OK] Installed {relative}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.9 Remote Adapter Pack 1.")
    parser.add_argument("project_root", nargs="?", default=r"C:\\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    patch_root = Path(__file__).resolve().parent
    project = Path(args.project_root).resolve()

    required = [
        project / "app/intelligence_sources/policy.py",
        project / "app/intelligence_sources/builtin_sources.py",
        project / "app/core/service_container.py",
        project / "app/core/config.py",
        project / ".env.example",
    ]
    missing = [str(x) for x in required if not x.exists()]
    if missing:
        print("[ERROR] Missing required R13.5/R13.8 project files: " + ", ".join(missing), file=sys.stderr)
        return 2

    _copy_payload(patch_root, project)
    _patch_config(project / "app/core/config.py")
    _patch_env(project / ".env.example")
    _patch_coverage(project / "app/intelligence_sources/builtin_sources.py")
    _patch_service(project / "app/core/service_container.py")

    print("[OK] R13.9 Remote Adapter Pack 1 installed.")
    print("[INFO] ACTIVE adapters: Norway BRREG, Czech ARES exact ICO, Crossref, ROR, OpenAlex.")
    print("[INFO] OpenAlex is credential-gated by OPENALEX_API_KEY.")
    print("[INFO] No database migration and no new dependency.")

    if args.run_tests:
        cmd = [sys.executable, "-m", "pytest", "tests/test_remote_adapter_pack_1.py", "-q"]
        print("[RUN]", " ".join(cmd))
        return subprocess.run(cmd, cwd=project, check=False).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

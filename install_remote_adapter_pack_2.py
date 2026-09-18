from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys


FILES = (
    "app/intelligence_sources/adapters/common.py",
    "app/intelligence_sources/adapters/sec_edgar.py",
    "app/intelligence_sources/adapters/ted.py",
    "app/intelligence_sources/adapters/sam_gov.py",
    "app/intelligence_sources/adapters/csl.py",
    "tests/test_remote_adapter_pack_2.py",
)

IMPORT_ANCHOR = "from app.intelligence_sources.adapters.openalex import OpenAlexAdapter\n"
IMPORTS = """from app.intelligence_sources.adapters.csl import TradeCslAdapter
from app.intelligence_sources.adapters.sam_gov import SamGovEntityAdapter
from app.intelligence_sources.adapters.sec_edgar import SecEdgarAdapter
from app.intelligence_sources.adapters.ted import TedSearchAdapter
"""

REGISTRATION_ANCHOR = """        self.remote_source_adapter_service = RemoteSourceAdapterService(
            registry=self.remote_source_adapter_registry
        )
"""
REGISTRATION_BLOCK = """        self.remote_source_adapter_registry.register(
            SecEdgarAdapter(user_agent=settings.sec_edgar_user_agent)
        )
        self.remote_source_adapter_registry.register(TedSearchAdapter())
        self.remote_source_adapter_registry.register(
            SamGovEntityAdapter(api_key=settings.sam_gov_api_key)
        )
        self.remote_source_adapter_registry.register(
            TradeCslAdapter(api_key=settings.trade_gov_api_key)
        )

"""

CONFIG_FIELDS = (
    "    sam_gov_api_key: str | None = None\n",
    "    trade_gov_api_key: str | None = None\n",
    "    sec_edgar_user_agent: str | None = None\n",
)
CONFIG_ANCHORS = (
    "    openalex_api_key: str | None = None\n",
    "    intelligencex_api_key: str | None = None\n",
    "    haveibeenpwned_api_key: str | None = None\n",
)

ENV_BLOCK = """
# R13.10 Remote Adapter Pack 2
# SAM.gov public API key (free account key)
SAM_GOV_API_KEY=
# Trade.gov Data Services / CSL API key
TRADE_GOV_API_KEY=
# SEC requires an identifying User-Agent, e.g. OSINTXZ admin@example.com
SEC_EDGAR_USER_AGENT=
"""

COVERAGE_REPLACEMENTS = {
    'SourceCoverageEntry("us_sec_edgar", Status.CATALOGED, stage="next-wave")':
        'SourceCoverageEntry("us_sec_edgar", Status.ACTIVE, "SecEdgarAdapter", "R13.10 exact-CIK")',
    'SourceCoverageEntry("us_sam_entities", Status.CATALOGED, stage="next-wave")':
        'SourceCoverageEntry("us_sam_entities", Status.ACTIVE, "SamGovEntityAdapter", "R13.10 credential-gated")',
    'SourceCoverageEntry("us_trade_csl", Status.CATALOGED, stage="next-wave")':
        'SourceCoverageEntry("us_trade_csl", Status.ACTIVE, "TradeCslAdapter", "R13.10 credential-gated screening")',
    'SourceCoverageEntry("eu_ted_search", Status.CATALOGED, stage="next-wave")':
        'SourceCoverageEntry("eu_ted_search", Status.ACTIVE, "TedSearchAdapter", "R13.10 expert-query")',
}


def _backup(path: Path, label: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(f"{path.name}.before_{label}_{stamp}.bak")
    shutil.copy2(path, target)
    return target


def _copy_payload(patch_root: Path, project: Path) -> None:
    for relative in FILES:
        src = patch_root / "payload" / relative
        dst = project / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"[OK] Installed {relative}")


def _patch_config(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original
    missing = [field for field in CONFIG_FIELDS if field.strip().split(":", 1)[0].strip() not in updated]
    if not missing:
        print(f"[OK] {path} already contains R13.10 settings")
        return
    anchor = next((a for a in CONFIG_ANCHORS if a in updated), None)
    if anchor is None:
        raise RuntimeError("Safe OSINT settings anchor not found in config.py")
    addition = "".join(field for field in CONFIG_FIELDS if field.strip().split(":", 1)[0].strip() not in updated)
    updated = updated.replace(anchor, anchor + addition, 1)
    backup = _backup(path, "remote_adapter_pack_2")
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}\n[OK] Backup: {backup}")


def _patch_env(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if all(key in original for key in ("SAM_GOV_API_KEY=", "TRADE_GOV_API_KEY=", "SEC_EDGAR_USER_AGENT=")):
        print(f"[OK] {path} already contains R13.10 env settings")
        return
    backup = _backup(path, "remote_adapter_pack_2")
    path.write_text(original.rstrip() + "\n" + ENV_BLOCK.lstrip(), encoding="utf-8")
    print(f"[OK] Patched {path}\n[OK] Backup: {backup}")


def _patch_service(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original
    if "from app.intelligence_sources.adapters.sec_edgar import SecEdgarAdapter\n" not in updated:
        if updated.count(IMPORT_ANCHOR) != 1:
            raise RuntimeError("R13.9 OpenAlex import anchor not found in service_container.py")
        updated = updated.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORTS, 1)
    if "SecEdgarAdapter(user_agent=settings.sec_edgar_user_agent)" not in updated:
        if updated.count(REGISTRATION_ANCHOR) != 1:
            raise RuntimeError("R13.9 remote adapter service anchor not found in service_container.py")
        updated = updated.replace(REGISTRATION_ANCHOR, REGISTRATION_BLOCK + REGISTRATION_ANCHOR, 1)
    if updated == original:
        print(f"[OK] {path} already contains Adapter Pack 2")
        return
    backup = _backup(path, "remote_adapter_pack_2")
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}\n[OK] Backup: {backup}")


def _patch_coverage(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original
    changed = False
    for old, new in COVERAGE_REPLACEMENTS.items():
        if new in updated:
            continue
        if old not in updated:
            raise RuntimeError(f"Expected R13.8 coverage entry missing: {old}")
        updated = updated.replace(old, new, 1)
        changed = True
    if not changed:
        print(f"[OK] {path} already marks Adapter Pack 2 active")
        return
    backup = _backup(path, "remote_adapter_pack_2")
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}\n[OK] Backup: {backup}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.10 Remote Adapter Pack 2")
    parser.add_argument("project_root", nargs="?", default=r"C:\\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    patch_root = Path(__file__).resolve().parent
    project = Path(args.project_root).resolve()

    required = [
        project / "app/intelligence_sources/adapters/service.py",
        project / "app/intelligence_sources/adapters/openalex.py",
        project / "app/intelligence_sources/builtin_sources.py",
        project / "app/core/config.py",
        project / "app/core/service_container.py",
        project / ".env.example",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("[ERROR] R13.9 is required; missing: " + ", ".join(missing), file=sys.stderr)
        return 2

    _copy_payload(patch_root, project)
    _patch_config(project / "app/core/config.py")
    _patch_env(project / ".env.example")
    _patch_coverage(project / "app/intelligence_sources/builtin_sources.py")
    _patch_service(project / "app/core/service_container.py")

    print("[OK] R13.10 Remote Adapter Pack 2 installed.")
    print("[INFO] ACTIVE: SEC EDGAR exact CIK, TED expert search, SAM.gov Entities, Trade.gov CSL.")
    print("[INFO] SEC needs SEC_EDGAR_USER_AGENT; SAM/CSL need their free API keys.")
    print("[INFO] No database migration and no new dependency.")

    if args.run_tests:
        cmd = [sys.executable, "-m", "pytest", "tests/test_remote_adapter_pack_2.py", "-q"]
        print("[RUN]", " ".join(cmd))
        return subprocess.run(cmd, cwd=project, check=False).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

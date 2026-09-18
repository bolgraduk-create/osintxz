from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

FILES = (
    "app/intelligence_sources/adapters/france_enterprises.py",
    "app/intelligence_sources/adapters/australia_abn.py",
    "app/intelligence_sources/adapters/canada_corporations.py",
    "app/intelligence_sources/adapters/uk_charity.py",
    "app/intelligence_sources/adapters/poland_regon.py",
    "tests/test_remote_adapter_pack_3.py",
)

IMPORT_ANCHOR = "from app.intelligence_sources.adapters.ted import TedSearchAdapter\n"
IMPORTS = """from app.intelligence_sources.adapters.australia_abn import AustraliaAbnLookupAdapter
from app.intelligence_sources.adapters.canada_corporations import CanadaFederalCorporationsAdapter
from app.intelligence_sources.adapters.france_enterprises import FranceEnterpriseSearchAdapter
from app.intelligence_sources.adapters.poland_regon import PolandRegonBirAdapter
from app.intelligence_sources.adapters.uk_charity import UkCharityCommissionAdapter
"""

REGISTRATION_ANCHOR = """        self.remote_source_adapter_service = RemoteSourceAdapterService(
            registry=self.remote_source_adapter_registry
        )
"""
REGISTRATION_BLOCK = """        self.remote_source_adapter_registry.register(
            FranceEnterpriseSearchAdapter()
        )
        self.remote_source_adapter_registry.register(
            AustraliaAbnLookupAdapter(guid=settings.abn_lookup_guid)
        )
        self.remote_source_adapter_registry.register(
            CanadaFederalCorporationsAdapter(
                api_key=settings.canada_corporations_api_key
            )
        )
        self.remote_source_adapter_registry.register(
            UkCharityCommissionAdapter(
                api_key=settings.charity_commission_api_key
            )
        )
        self.remote_source_adapter_registry.register(
            PolandRegonBirAdapter(user_key=settings.regon_bir_user_key)
        )

"""

CONFIG_FIELDS = (
    "    abn_lookup_guid: str | None = None\n",
    "    canada_corporations_api_key: str | None = None\n",
    "    charity_commission_api_key: str | None = None\n",
    "    regon_bir_user_key: str | None = None\n",
)
CONFIG_ANCHORS = (
    "    sec_edgar_user_agent: str | None = None\n",
    "    openalex_api_key: str | None = None\n",
    "    intelligencex_api_key: str | None = None\n",
)

ENV_BLOCK = """
# R13.11 Remote Adapter Pack 3
# Australia ABN Lookup free web-services GUID
ABN_LOOKUP_GUID=
# Corporations Canada API subscription key
CANADA_CORPORATIONS_API_KEY=
# Charity Commission Register of Charities subscription key
CHARITY_COMMISSION_API_KEY=
# Poland REGON BIR production user key
REGON_BIR_USER_KEY=
"""

SOURCE_REPLACEMENTS = {
    '_source("fr_sirene", "France SIRENE / API Entreprise", categories={Category.REGISTRY}, capabilities={"siren", "siret", "organization", "establishment"}, access=Access.FREE_ACCOUNT, origin=Origin.OFFICIAL_API, countries={"FR"}, requires_credentials=True, documentation_url="https://entreprise.api.gouv.fr/"),':
        '_source("fr_sirene", "France Recherche Entreprises (SIRENE/RNE)", categories={Category.REGISTRY}, capabilities={"siren", "siret", "company_name", "name", "organization", "establishment"}, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, countries={"FR"}, requires_credentials=False, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://recherche-entreprises.api.gouv.fr/docs/"),',
}

COVERAGE_REPLACEMENTS = {
    'SourceCoverageEntry("fr_sirene", Status.CATALOGED, stage="europe")':
        'SourceCoverageEntry("fr_sirene", Status.ACTIVE, "FranceEnterpriseSearchAdapter", "R13.11 open SIRENE/RNE search")',
    'SourceCoverageEntry("au_abn_lookup", Status.CATALOGED, stage="apac")':
        'SourceCoverageEntry("au_abn_lookup", Status.ACTIVE, "AustraliaAbnLookupAdapter", "R13.11 credential-gated")',
    'SourceCoverageEntry("ca_federal_corporations", Status.CATALOGED, stage="americas")':
        'SourceCoverageEntry("ca_federal_corporations", Status.ACTIVE, "CanadaFederalCorporationsAdapter", "R13.11 exact-ID credential-gated")',
    'SourceCoverageEntry("uk_charity_commission", Status.CATALOGED, stage="next-wave")':
        'SourceCoverageEntry("uk_charity_commission", Status.ACTIVE, "UkCharityCommissionAdapter", "R13.11 credential-gated")',
    'SourceCoverageEntry("pl_regon", Status.CATALOGED, stage="europe")':
        'SourceCoverageEntry("pl_regon", Status.ACTIVE, "PolandRegonBirAdapter", "R13.11 REGON/NIP/KRS credential-gated")',
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
    names = [f.strip().split(":", 1)[0].strip() for f in CONFIG_FIELDS]
    missing = [f for f, name in zip(CONFIG_FIELDS, names) if name not in updated]
    if not missing:
        print(f"[OK] {path} already contains R13.11 settings")
        return
    anchor = next((a for a in CONFIG_ANCHORS if a in updated), None)
    if anchor is None:
        raise RuntimeError("Safe OSINT settings anchor not found in config.py")
    updated = updated.replace(anchor, anchor + "".join(missing), 1)
    backup = _backup(path, "remote_adapter_pack_3")
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}\n[OK] Backup: {backup}")


def _patch_env(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    keys = ("ABN_LOOKUP_GUID=", "CANADA_CORPORATIONS_API_KEY=", "CHARITY_COMMISSION_API_KEY=", "REGON_BIR_USER_KEY=")
    if all(k in original for k in keys):
        print(f"[OK] {path} already contains R13.11 env settings")
        return
    addition = ENV_BLOCK
    backup = _backup(path, "remote_adapter_pack_3")
    path.write_text(original.rstrip() + "\n" + addition.lstrip(), encoding="utf-8")
    print(f"[OK] Patched {path}\n[OK] Backup: {backup}")


def _patch_service(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original
    if "from app.intelligence_sources.adapters.france_enterprises import FranceEnterpriseSearchAdapter\n" not in updated:
        if updated.count(IMPORT_ANCHOR) != 1:
            raise RuntimeError("R13.10 TED import anchor not found in service_container.py")
        updated = updated.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORTS, 1)
    if "FranceEnterpriseSearchAdapter()" not in updated:
        if updated.count(REGISTRATION_ANCHOR) != 1:
            raise RuntimeError("Remote adapter service anchor not found in service_container.py")
        updated = updated.replace(REGISTRATION_ANCHOR, REGISTRATION_BLOCK + REGISTRATION_ANCHOR, 1)
    if updated == original:
        print(f"[OK] {path} already contains Adapter Pack 3")
        return
    backup = _backup(path, "remote_adapter_pack_3")
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}\n[OK] Backup: {backup}")


def _patch_catalog(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original
    changed = False
    for old, new in SOURCE_REPLACEMENTS.items():
        if new in updated:
            continue
        if old not in updated:
            raise RuntimeError(f"Expected source descriptor missing: {old[:80]}")
        updated = updated.replace(old, new, 1)
        changed = True
    for old, new in COVERAGE_REPLACEMENTS.items():
        if new in updated:
            continue
        if old not in updated:
            raise RuntimeError(f"Expected coverage entry missing: {old}")
        updated = updated.replace(old, new, 1)
        changed = True
    if not changed:
        print(f"[OK] {path} already marks Adapter Pack 3 active")
        return
    backup = _backup(path, "remote_adapter_pack_3")
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}\n[OK] Backup: {backup}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.11 Remote Adapter Pack 3")
    parser.add_argument("project_root", nargs="?", default=r"C:\\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    patch_root = Path(__file__).resolve().parent
    project = Path(args.project_root).resolve()

    required = [
        project / "app/intelligence_sources/adapters/service.py",
        project / "app/intelligence_sources/adapters/ted.py",
        project / "app/intelligence_sources/builtin_sources.py",
        project / "app/core/config.py",
        project / "app/core/service_container.py",
        project / ".env.example",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("[ERROR] R13.10 is required; missing: " + ", ".join(missing), file=sys.stderr)
        return 2

    _copy_payload(patch_root, project)
    _patch_config(project / "app/core/config.py")
    _patch_env(project / ".env.example")
    _patch_catalog(project / "app/intelligence_sources/builtin_sources.py")
    _patch_service(project / "app/core/service_container.py")

    print("[OK] R13.11 Remote Adapter Pack 3 installed.")
    print("[INFO] ACTIVE: France open search, Australia ABN, Canada Corporations, UK Charity Commission, Poland REGON BIR.")
    print("[INFO] France works without a key; Australia/Canada/UK/Poland are credential-gated.")
    print("[INFO] No database migration and no new dependency.")

    if args.run_tests:
        cmd = [sys.executable, "-m", "pytest", "tests/test_remote_adapter_pack_3.py", "-q"]
        print("[RUN]", " ".join(cmd))
        return subprocess.run(cmd, cwd=project, check=False).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

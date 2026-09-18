from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PATCH_DIR = Path(__file__).resolve().parent
PAYLOAD_DIR = PATCH_DIR / "payload"

NEW_FILES = (
    "app/intelligence_sources/adapters/free_public_common.py",
    "app/intelligence_sources/adapters/wikidata_search.py",
    "app/intelligence_sources/adapters/orcid_public.py",
    "app/intelligence_sources/adapters/nvd_cve.py",
    "app/intelligence_sources/adapters/openfda.py",
    "app/intelligence_sources/adapters/fec.py",
    "app/intelligence_sources/adapters/icij_offshore.py",
    "app/intelligence_sources/adapters/nppes_npi.py",
    "tests/test_r13_15_free_public_data_pack.py",
)

PATCH_FILES = (
    "app/intelligence_sources/builtin_sources.py",
    "app/core/config.py",
    "app/core/service_container.py",
    ".env.example",
)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Cannot patch {label}: expected one anchor, found {count}. "
            "R13.15 expects the successfully tested R13.14 baseline."
        )
    return text.replace(old, new, 1)


def patch_builtin(text: str) -> str:
    old_orcid = '''    _source("orcid_public", "ORCID Public API", categories={Category.ACADEMIC}, capabilities={"orcid", "researcher", "works", "affiliation"}, access=Access.FREE_ACCOUNT, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://info.orcid.org/documentation/integration-guide/"),\n'''
    new_orcid = '''    _source("orcid_public", "ORCID Anonymous/Public API", categories={Category.ACADEMIC, Category.OPEN_DATA}, capabilities={"orcid", "person", "researcher", "name"}, access=Access.NO_AUTH, origin=Origin.AGGREGATOR, global_scope=True, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://info.orcid.org/documentation/api-tutorials/api-tutorial-searching-the-orcid-registry/", notes="R13.15 uses the read-only anonymous/public expanded-search endpoint. Name matches remain candidates until independently resolved."),\n'''
    text = replace_once(text, old_orcid, new_orcid, "R13.15 ORCID descriptor")

    wikidata_anchor = '''    _source("wikidata_sparql", "Wikidata Query Service", categories={Category.OPEN_DATA, Category.WEB_OSINT}, capabilities={"person", "organization", "identifier", "relationship", "location", "name"}, transport=Transport.SPARQL, origin=Origin.COMMUNITY_INDEX, global_scope=True, documentation_url="https://query.wikidata.org/"),\n'''
    wikidata_new = wikidata_anchor + '''    _source("wikidata_search", "Wikidata Entity Search", categories={Category.OPEN_DATA, Category.WEB_OSINT}, capabilities={"person", "organization", "location", "name", "entity_search", "wikidata_id"}, transport=Transport.PUBLIC_HTTP, access=Access.NO_AUTH, origin=Origin.COMMUNITY_INDEX, global_scope=True, default_enabled=True, documentation_url="https://www.wikidata.org/wiki/Wikidata:Data_access", notes="R13.15 uses the official entity-search API for text discovery and exact QID fetches; fuzzy/name hits are candidate-only."),\n'''
    text = replace_once(text, wikidata_anchor, wikidata_new, "R13.15 Wikidata search descriptor")

    old_nvd = '''    _source("nvd_cve_api", "NIST NVD CVE API", categories={Category.THREAT_INTELLIGENCE, Category.OPEN_DATA}, capabilities={"cve", "cpe", "vulnerability", "product"}, origin=Origin.OFFICIAL_API, countries={"US"}, documentation_url="https://nvd.nist.gov/developers/vulnerabilities"),\n'''
    new_nvd = '''    _source("nvd_cve_api", "NIST NVD CVE API", categories={Category.THREAT_INTELLIGENCE, Category.OPEN_DATA}, capabilities={"cve", "cve_id", "vulnerability", "product", "vendor", "keyword"}, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, countries={"US"}, default_enabled=True, documentation_url="https://nvd.nist.gov/developers/vulnerabilities", notes="NVD API key is optional in R13.15 and can be supplied only to improve public API rate limits."),\n'''
    text = replace_once(text, old_nvd, new_nvd, "R13.15 NVD descriptor")

    old_fda = '''    _source("openfda", "openFDA", categories={Category.OPEN_DATA, Category.PROFESSIONAL}, capabilities={"manufacturer", "product", "device", "drug", "enforcement"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"US"}, requires_credentials=True, documentation_url="https://open.fda.gov/apis/"),\n'''
    new_fda = '''    _source("openfda", "openFDA", categories={Category.OPEN_DATA, Category.PROFESSIONAL}, capabilities={"manufacturer", "organization", "product", "device", "drug", "enforcement"}, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, countries={"US"}, default_enabled=True, documentation_url="https://open.fda.gov/apis/", notes="Works without an API key at public anonymous limits; optional free key raises quota."),\n'''
    text = replace_once(text, old_fda, new_fda, "R13.15 openFDA descriptor")

    old_fec = '''    _source("us_fec", "US Federal Election Commission API", categories={Category.PUBLIC_OFFICIAL, Category.OPEN_DATA}, capabilities={"candidate", "committee", "organization", "contribution"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"US"}, requires_credentials=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://api.open.fec.gov/developers/"),\n'''
    new_fec = '''    _source("us_fec", "US Federal Election Commission API", categories={Category.PUBLIC_OFFICIAL, Category.OPEN_DATA}, capabilities={"candidate", "committee", "organization", "contribution", "contributor", "name"}, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, countries={"US"}, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://api.open.fec.gov/developers/", notes="R13.15 falls back to the documented DEMO_KEY; a free user API key is optional. Street-address fields are not retained by the adapter."),\n'''
    text = replace_once(text, old_fec, new_fec, "R13.15 FEC descriptor")

    old_icij = '''    _source("icij_offshore_leaks", "ICIJ Offshore Leaks Database", categories={Category.OPEN_DATA, Category.REGISTRY}, capabilities={"person", "organization", "offshore_entity", "officer", "intermediary", "address"}, transport=Transport.PUBLIC_HTTP, access=Access.MANUAL_ASSISTED, origin=Origin.COMMUNITY_INDEX, global_scope=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://offshoreleaks.icij.org/"),\n'''
    new_icij = '''    _source("icij_offshore_leaks", "ICIJ Offshore Leaks Database", categories={Category.OPEN_DATA, Category.REGISTRY}, capabilities={"name", "person", "organization", "offshore_entity", "officer", "intermediary", "address"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.COMMUNITY_INDEX, global_scope=True, default_enabled=False, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://offshoreleaks.icij.org/docs/reconciliation", notes="R13.15 uses the official reconciliation API. Results are investigative candidates only and never automatic proof of identity or offshore involvement."),\n    _source("us_nppes_npi", "US NPPES / NPI Registry", categories={Category.PROFESSIONAL, Category.OPEN_DATA}, capabilities={"npi", "provider", "person", "organization", "name"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, countries={"US"}, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://npiregistry.cms.hhs.gov/api-page", notes="Public NPI directory. NPI issuance does not validate licensure or credentials; name matches remain candidates."),\n'''
    text = replace_once(text, old_icij, new_icij, "R13.15 ICIJ + NPI descriptors")

    replacements = {
        '''    SourceCoverageEntry("orcid_public", Status.CATALOGED, stage="research"),\n''':
        '''    SourceCoverageEntry("orcid_public", Status.ACTIVE, "OrcidPublicAdapter", "R13.15 anonymous/public search"),\n''',
        '''    SourceCoverageEntry("nvd_cve_api", Status.CATALOGED, stage="threat-intel"),\n''':
        '''    SourceCoverageEntry("nvd_cve_api", Status.ACTIVE, "NvdCveAdapter", "R13.15 no-key; optional free key"),\n''',
        '''    SourceCoverageEntry("openfda", Status.CATALOGED, stage="us-open-data"),\n''':
        '''    SourceCoverageEntry("openfda", Status.ACTIVE, "OpenFdaAdapter", "R13.15 anonymous public API"),\n''',
        '''    SourceCoverageEntry("us_fec", Status.CATALOGED, stage="us-open-data"),\n''':
        '''    SourceCoverageEntry("us_fec", Status.ACTIVE, "OpenFecAdapter", "R13.15 DEMO_KEY/free-key"),\n''',
        '''    SourceCoverageEntry("icij_offshore_leaks", Status.MANUAL_ASSISTED, stage="investigative-data"),\n''':
        '''    SourceCoverageEntry("icij_offshore_leaks", Status.ACTIVE, "IcijOffshoreLeaksAdapter", "R13.15 reconciliation candidates"),\n    SourceCoverageEntry("wikidata_search", Status.ACTIVE, "WikidataEntitySearchAdapter", "R13.15 public entity search"),\n    SourceCoverageEntry("us_nppes_npi", Status.ACTIVE, "NppesNpiAdapter", "R13.15 public NPI API v2.1"),\n''',
    }
    for old, new in replacements.items():
        text = replace_once(text, old, new, f"R13.15 coverage {old.strip()}")
    return text


def patch_config(text: str) -> str:
    old = '''    github_secret_scanning_token: str | None = None\n    openalex_api_key: str | None = None\n'''
    new = '''    github_secret_scanning_token: str | None = None\n\n    # R13.15 — optional free/public API keys. All adapters work without these\n    # values; keys only increase quota where the upstream service supports it.\n    nvd_api_key: str | None = None\n    openfda_api_key: str | None = None\n    fec_api_key: str | None = None\n\n    openalex_api_key: str | None = None\n'''
    return replace_once(text, old, new, "R13.15 optional free API settings")


def patch_env(text: str) -> str:
    old = '''GITHUB_SECRET_SCANNING_TOKEN=\n'''
    new = old + '''\n# R13.15 — optional free/public-data keys. Leave blank to use anonymous/\n# documented demo access; configure only if you want higher upstream quotas.\nNVD_API_KEY=\nOPENFDA_API_KEY=\nFEC_API_KEY=\n'''
    return replace_once(text, old, new, "R13.15 .env example")


def patch_container(text: str) -> str:
    import_anchor = '''from app.intelligence_sources.adapters.onion_discovery import TorOnionDiscoveryAdapter\n'''
    imports = import_anchor + '''from app.intelligence_sources.adapters.wikidata_search import WikidataEntitySearchAdapter\nfrom app.intelligence_sources.adapters.orcid_public import OrcidPublicAdapter\nfrom app.intelligence_sources.adapters.nvd_cve import NvdCveAdapter\nfrom app.intelligence_sources.adapters.openfda import OpenFdaAdapter\nfrom app.intelligence_sources.adapters.fec import OpenFecAdapter\nfrom app.intelligence_sources.adapters.icij_offshore import IcijOffshoreLeaksAdapter\nfrom app.intelligence_sources.adapters.nppes_npi import NppesNpiAdapter\n'''
    text = replace_once(text, import_anchor, imports, "R13.15 service-container imports")

    register_anchor = '''        self.remote_source_adapter_registry.register(\n            TorOnionDiscoveryAdapter(service=self.darkweb_discovery_service)\n        )\n\n        self.remote_source_adapter_service = RemoteSourceAdapterService(\n'''
    register_block = '''        self.remote_source_adapter_registry.register(\n            TorOnionDiscoveryAdapter(service=self.darkweb_discovery_service)\n        )\n\n        # R13.15 — Free Public Data Mega Pack 1.\n        self.remote_source_adapter_registry.register(WikidataEntitySearchAdapter())\n        self.remote_source_adapter_registry.register(OrcidPublicAdapter())\n        self.remote_source_adapter_registry.register(\n            NvdCveAdapter(api_key=settings.nvd_api_key)\n        )\n        self.remote_source_adapter_registry.register(\n            OpenFdaAdapter(api_key=settings.openfda_api_key)\n        )\n        self.remote_source_adapter_registry.register(\n            OpenFecAdapter(api_key=settings.fec_api_key)\n        )\n        self.remote_source_adapter_registry.register(IcijOffshoreLeaksAdapter())\n        self.remote_source_adapter_registry.register(NppesNpiAdapter())\n\n        self.remote_source_adapter_service = RemoteSourceAdapterService(\n'''
    return replace_once(text, register_anchor, register_block, "R13.15 adapter registration")


PATCHERS = {
    "app/intelligence_sources/builtin_sources.py": patch_builtin,
    "app/core/config.py": patch_config,
    "app/core/service_container.py": patch_container,
    ".env.example": patch_env,
}


def install(project_root: Path, run_tests: bool) -> None:
    project_root = project_root.resolve()
    if not (project_root / "app").is_dir():
        raise RuntimeError(f"Not an OSINTXZ project root: {project_root}")

    missing = [path for path in PATCH_FILES if not (project_root / path).exists()]
    if missing:
        raise RuntimeError("Missing R13.14 baseline files: " + ", ".join(missing))

    patched: dict[str, str] = {}
    for rel, patcher in PATCHERS.items():
        path = project_root / rel
        patched[rel] = patcher(path.read_text(encoding="utf-8"))

    for rel in NEW_FILES:
        if not (PAYLOAD_DIR / rel).exists():
            raise RuntimeError(f"Patch payload is missing {rel}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = project_root / "storage" / "patch_backups" / f"r13_15_{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    for rel in PATCH_FILES:
        src = project_root / rel
        dst = backup_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for rel in NEW_FILES:
        dst = project_root / rel
        if dst.exists():
            backup = backup_root / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, backup)

    for rel, content in patched.items():
        (project_root / rel).write_text(content, encoding="utf-8")

    for rel in NEW_FILES:
        src = PAYLOAD_DIR / rel
        dst = project_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    print(f"R13.15 installed. Backup: {backup_root}")

    if run_tests:
        tests = [
            "tests/test_r13_15_free_public_data_pack.py",
            "tests/test_r13_14_darkweb_discovery_indexing.py",
            "tests/test_r13_13_leak_paste_source_pack.py",
            "tests/test_r13_12_exposure_federation.py",
            "tests/test_breach_intelligence_hibp.py",
            "tests/test_darkweb_intelligence.py",
            "tests/test_intelligence_source_federation.py",
            "tests/test_remote_adapter_pack_1.py",
            "tests/test_remote_adapter_pack_2.py",
            "tests/test_remote_adapter_pack_3.py",
        ]
        command = [sys.executable, "-m", "pytest", "-q", *tests]
        print("Running:", " ".join(command))
        completed = subprocess.run(command, cwd=project_root)
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R13.15 Free Public Data Mega Pack 1"
    )
    parser.add_argument("project_root", nargs="?", default=r"C:\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    install(Path(args.project_root), args.run_tests)


if __name__ == "__main__":
    main()

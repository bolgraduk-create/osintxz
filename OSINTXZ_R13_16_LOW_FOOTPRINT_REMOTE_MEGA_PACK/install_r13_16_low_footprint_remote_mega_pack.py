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
    "app/intelligence_sources/adapters/github_public.py",
    "app/intelligence_sources/adapters/gitlab_public.py",
    "app/intelligence_sources/adapters/semantic_scholar.py",
    "app/intelligence_sources/adapters/europe_pmc.py",
    "app/intelligence_sources/adapters/library_of_congress.py",
    "app/intelligence_sources/adapters/fbi_wanted.py",
    "app/intelligence_sources/adapters/first_epss.py",
    "app/intelligence_sources/adapters/circl_hashlookup.py",
    "app/intelligence_sources/adapters/shodan_internetdb.py",
    "app/intelligence_sources/adapters/cisa_kev.py",
    "tests/test_r13_16_low_footprint_remote_pack.py",
)

PATCH_FILES = (
    "app/intelligence_sources/builtin_sources.py",
    "app/core/service_container.py",
)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Cannot patch {label}: expected one anchor, found {count}. "
            "R13.16 expects the successfully installed R13.15 baseline."
        )
    return text.replace(old, new, 1)


def patch_builtin(text: str) -> str:
    descriptor_anchor = '''    _source("us_nppes_npi", "US NPPES / NPI Registry", categories={Category.PROFESSIONAL, Category.OPEN_DATA}, capabilities={"npi", "provider", "person", "organization", "name"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, countries={"US"}, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://npiregistry.cms.hhs.gov/api-page", notes="Public NPI directory. NPI issuance does not validate licensure or credentials; name matches remain candidates."),\n'''
    descriptors = descriptor_anchor + '''    _source("github_public_user", "GitHub Public User API", categories={Category.WEB_OSINT, Category.OPEN_DATA}, capabilities={"username", "github_username"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, global_scope=True, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://docs.github.com/en/rest/users/users", notes="Exact public account lookup only. A platform account is not automatically resolved to a real-world person."),
    _source("gitlab_public_user", "GitLab Public Users API", categories={Category.WEB_OSINT, Category.OPEN_DATA}, capabilities={"username", "gitlab_username"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, global_scope=True, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://docs.gitlab.com/api/users/", notes="Exact public username lookup; account-to-person identity inference remains prohibited."),
    _source("semantic_scholar", "Semantic Scholar Academic Graph", categories={Category.ACADEMIC, Category.OPEN_DATA}, capabilities={"academic_author", "author", "paper", "publication"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.AGGREGATOR, global_scope=True, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://www.semanticscholar.org/product/api", notes="Public Academic Graph API; author name matches remain candidates."),
    _source("europe_pmc", "Europe PMC REST API", categories={Category.ACADEMIC, Category.OPEN_DATA}, capabilities={"publication", "author", "academic_author", "doi", "pmid"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.AGGREGATOR, global_scope=True, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://europepmc.org/RestfulWebService", notes="Public publication metadata API; no article files are downloaded by R13.16."),
    _source("library_of_congress", "Library of Congress JSON API", categories={Category.ARCHIVE, Category.OPEN_DATA}, capabilities={"archive_search", "historical_document", "historical_web"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, global_scope=True, default_enabled=True, documentation_url="https://www.loc.gov/apis/json-and-yaml/", notes="Metadata-only search. R13.16 never downloads media/resources from Library collections."),
    _source("fbi_wanted", "FBI Wanted Public API", categories={Category.OPEN_DATA}, capabilities={"wanted_person", "wanted_name"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, countries={"US"}, default_enabled=False, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://www.fbi.gov/wanted/api", notes="Public notice candidates only. Results are never treated as proof of identity, guilt, conviction or legal outcome."),
    _source("first_epss", "FIRST EPSS API", categories={Category.THREAT_INTELLIGENCE, Category.OPEN_DATA}, capabilities={"cve", "cve_id", "epss"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.COMMUNITY_INDEX, global_scope=True, default_enabled=True, documentation_url="https://api.first.org/epss/", notes="Exact CVE exploit-probability lookup with no local dataset download."),
    _source("circl_hashlookup", "CIRCL hashlookup", categories={Category.THREAT_INTELLIGENCE, Category.OPEN_DATA}, capabilities={"hash", "md5", "sha1", "sha256"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.COMMUNITY_INDEX, global_scope=True, default_enabled=True, documentation_url="https://circl.lu/services/hashlookup/", notes="Exact hash context lookup against public known-file datasets; a match is not itself a maliciousness verdict."),
    _source("shodan_internetdb", "Shodan InternetDB", categories={Category.THREAT_INTELLIGENCE, Category.WEB_OSINT}, capabilities={"ip", "ip_address", "open_ports", "vulnerability"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.AGGREGATOR, global_scope=True, default_enabled=True, documentation_url="https://internetdb.shodan.io/", notes="Free low-detail IP snapshot: ports, CPEs, hostnames, tags and vulnerability identifiers; no banners are returned."),
    _source("cisa_kev", "CISA Known Exploited Vulnerabilities", categories={Category.THREAT_INTELLIGENCE, Category.OPEN_DATA}, capabilities={"cve", "cve_id", "known_exploited"}, transport=Transport.PUBLIC_HTTP, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, global_scope=True, default_enabled=True, documentation_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog", notes="Exact CVE lookup. The small JSON catalog is read transiently in memory and is never persisted by R13.16."),
'''
    text = replace_once(text, descriptor_anchor, descriptors, "R13.16 descriptors")

    coverage_anchor = '''    SourceCoverageEntry("us_nppes_npi", Status.ACTIVE, "NppesNpiAdapter", "R13.15 public NPI API v2.1"),\n'''
    coverage = coverage_anchor + '''    SourceCoverageEntry("github_public_user", Status.ACTIVE, "GitHubPublicUserAdapter", "R13.16 low-footprint remote"),
    SourceCoverageEntry("gitlab_public_user", Status.ACTIVE, "GitLabPublicUserAdapter", "R13.16 low-footprint remote"),
    SourceCoverageEntry("semantic_scholar", Status.ACTIVE, "SemanticScholarAdapter", "R13.16 low-footprint remote"),
    SourceCoverageEntry("europe_pmc", Status.ACTIVE, "EuropePmcAdapter", "R13.16 low-footprint remote"),
    SourceCoverageEntry("library_of_congress", Status.ACTIVE, "LibraryOfCongressAdapter", "R13.16 metadata-only archive search"),
    SourceCoverageEntry("fbi_wanted", Status.ACTIVE, "FbiWantedAdapter", "R13.16 explicit public-notice search"),
    SourceCoverageEntry("first_epss", Status.ACTIVE, "FirstEpssAdapter", "R13.16 exact CVE"),
    SourceCoverageEntry("circl_hashlookup", Status.ACTIVE, "CirclHashlookupAdapter", "R13.16 exact hash"),
    SourceCoverageEntry("shodan_internetdb", Status.ACTIVE, "ShodanInternetDbAdapter", "R13.16 free IP snapshot"),
    SourceCoverageEntry("cisa_kev", Status.ACTIVE, "CisaKevAdapter", "R13.16 transient exact-CVE feed lookup"),
'''
    return replace_once(text, coverage_anchor, coverage, "R13.16 coverage")


def patch_container(text: str) -> str:
    import_anchor = '''from app.intelligence_sources.adapters.nppes_npi import NppesNpiAdapter\n'''
    imports = import_anchor + '''from app.intelligence_sources.adapters.github_public import GitHubPublicUserAdapter
from app.intelligence_sources.adapters.gitlab_public import GitLabPublicUserAdapter
from app.intelligence_sources.adapters.semantic_scholar import SemanticScholarAdapter
from app.intelligence_sources.adapters.europe_pmc import EuropePmcAdapter
from app.intelligence_sources.adapters.library_of_congress import LibraryOfCongressAdapter
from app.intelligence_sources.adapters.fbi_wanted import FbiWantedAdapter
from app.intelligence_sources.adapters.first_epss import FirstEpssAdapter
from app.intelligence_sources.adapters.circl_hashlookup import CirclHashlookupAdapter
from app.intelligence_sources.adapters.shodan_internetdb import ShodanInternetDbAdapter
from app.intelligence_sources.adapters.cisa_kev import CisaKevAdapter
'''
    text = replace_once(text, import_anchor, imports, "R13.16 service-container imports")

    register_anchor = '''        self.remote_source_adapter_registry.register(NppesNpiAdapter())\n\n        self.remote_source_adapter_service = RemoteSourceAdapterService(\n'''
    registrations = '''        self.remote_source_adapter_registry.register(NppesNpiAdapter())

        # R13.16 — Low-Footprint Remote Data Mega Pack.
        self.remote_source_adapter_registry.register(GitHubPublicUserAdapter())
        self.remote_source_adapter_registry.register(GitLabPublicUserAdapter())
        self.remote_source_adapter_registry.register(SemanticScholarAdapter())
        self.remote_source_adapter_registry.register(EuropePmcAdapter())
        self.remote_source_adapter_registry.register(LibraryOfCongressAdapter())
        self.remote_source_adapter_registry.register(FbiWantedAdapter())
        self.remote_source_adapter_registry.register(FirstEpssAdapter())
        self.remote_source_adapter_registry.register(CirclHashlookupAdapter())
        self.remote_source_adapter_registry.register(ShodanInternetDbAdapter())
        self.remote_source_adapter_registry.register(CisaKevAdapter())

        self.remote_source_adapter_service = RemoteSourceAdapterService(
'''
    return replace_once(text, register_anchor, registrations, "R13.16 adapter registration")


PATCHERS = {
    "app/intelligence_sources/builtin_sources.py": patch_builtin,
    "app/core/service_container.py": patch_container,
}


def install(project_root: Path, run_tests: bool) -> None:
    project_root = project_root.resolve()
    if not (project_root / "app").is_dir():
        raise RuntimeError(f"Not an OSINTXZ project root: {project_root}")

    missing = [path for path in PATCH_FILES if not (project_root / path).exists()]
    if missing:
        raise RuntimeError("Missing R13.15 baseline files: " + ", ".join(missing))

    patched: dict[str, str] = {}
    for rel, patcher in PATCHERS.items():
        path = project_root / rel
        patched[rel] = patcher(path.read_text(encoding="utf-8"))

    for rel in NEW_FILES:
        if not (PAYLOAD_DIR / rel).exists():
            raise RuntimeError(f"Patch payload is missing {rel}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_root = project_root / "storage" / "patch_backups" / f"r13_16_{timestamp}"
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

    print(f"R13.16 installed. Backup: {backup_root}")

    if run_tests:
        tests = [
            "tests/test_r13_16_low_footprint_remote_pack.py",
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
        description="Install OSINTXZ R13.16 Low-Footprint Remote Data Mega Pack"
    )
    parser.add_argument("project_root", nargs="?", default=r"C:\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    install(Path(args.project_root), args.run_tests)


if __name__ == "__main__":
    main()

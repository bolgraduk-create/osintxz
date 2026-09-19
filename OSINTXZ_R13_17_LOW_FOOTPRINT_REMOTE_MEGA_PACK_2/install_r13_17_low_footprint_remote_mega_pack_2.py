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
    "app/intelligence_sources/adapters/rdap_bootstrap.py",
    "app/intelligence_sources/adapters/ripestat.py",
    "app/intelligence_sources/adapters/peeringdb.py",
    "app/intelligence_sources/adapters/google_dns.py",
    "app/intelligence_sources/adapters/usaspending.py",
    "app/intelligence_sources/adapters/federal_register.py",
    "app/intelligence_sources/adapters/datacite.py",
    "app/intelligence_sources/adapters/zenodo_public.py",
    "app/intelligence_sources/adapters/internet_archive.py",
    "app/intelligence_sources/adapters/un_sanctions.py",
    "tests/test_r13_17_low_footprint_remote_pack_2.py",
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
            "R13.17 expects the successfully installed R13.16 baseline."
        )
    return text.replace(old, new, 1)


def patch_builtin(text: str) -> str:
    descriptor_anchor = '''    _source("cisa_kev", "CISA Known Exploited Vulnerabilities", categories={Category.THREAT_INTELLIGENCE, Category.OPEN_DATA}, capabilities={"cve", "cve_id", "known_exploited"}, transport=Transport.PUBLIC_HTTP, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, global_scope=True, default_enabled=True, documentation_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog", notes="Exact CVE lookup. The small JSON catalog is read transiently in memory and is never persisted by R13.16."),\n'''
    descriptors = descriptor_anchor + '''    _source("rdap_bootstrap", "RDAP.org Bootstrap", categories={Category.WEB_OSINT, Category.OPEN_DATA}, capabilities={"domain", "domain_rdap", "ip", "ip_address", "ip_rdap", "asn", "autonomous_system", "asn_rdap"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.AGGREGATOR, global_scope=True, default_enabled=True, documentation_url="https://about.rdap.org/", notes="Exact domain/IP/ASN RDAP lookup. Raw vCard/contact structures are not retained by the adapter."),
    _source("ripestat", "RIPEstat Data API", categories={Category.WEB_OSINT, Category.OPEN_DATA, Category.THREAT_INTELLIGENCE}, capabilities={"ip", "ip_address", "asn", "autonomous_system", "network_registration"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, global_scope=True, default_enabled=True, documentation_url="https://stat.ripe.net/docs/data-api/ripestat-data-api", notes="Exact IP/ASN network metadata; no local RIPE dataset replication."),
    _source("peeringdb_public", "PeeringDB Guest API", categories={Category.WEB_OSINT, Category.OPEN_DATA}, capabilities={"asn", "autonomous_system", "peering_network"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.COMMUNITY_INDEX, global_scope=True, default_enabled=True, documentation_url="https://docs.peeringdb.com/api_specs/", notes="Guest exact-ASN queries only; restricted contact data is not requested."),
    _source("google_public_dns", "Google Public DNS JSON API", categories={Category.WEB_OSINT, Category.OPEN_DATA}, capabilities={"domain", "dns", "domain_dns"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.AGGREGATOR, global_scope=True, default_enabled=True, documentation_url="https://developers.google.com/speed/public-dns/docs/doh/json", notes="Bounded DNS record lookup; no persistent DNS cache is created by R13.17."),
    _source("usaspending_recipients", "USAspending Recipient API", categories={Category.PROCUREMENT, Category.FINANCIAL, Category.OPEN_DATA}, capabilities={"recipient", "organization", "uei", "duns", "federal_award_recipient"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, countries={"US"}, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://api.usaspending.gov/docs/endpoints", notes="Public federal-award recipient search. Name matches are candidates until independently resolved."),
    _source("us_federal_register", "US Federal Register API", categories={Category.OPEN_DATA, Category.ARCHIVE, Category.PUBLIC_OFFICIAL}, capabilities={"federal_register", "regulatory_document", "regulation_search", "name", "organization", "keyword"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, countries={"US"}, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://www.federalregister.gov/developers/documentation/api/v1", notes="Document metadata/mention search only; linked PDFs are not downloaded."),
    _source("datacite_public", "DataCite Public API", categories={Category.ACADEMIC, Category.OPEN_DATA}, capabilities={"doi", "publication", "dataset", "research_output", "author"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.AGGREGATOR, global_scope=True, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://support.datacite.org/docs/rest-api", notes="Public DOI metadata retrieval; linked research files are not downloaded."),
    _source("zenodo_public", "Zenodo Public Records API", categories={Category.ACADEMIC, Category.OPEN_DATA, Category.ARCHIVE}, capabilities={"research_output", "publication", "dataset", "software", "doi", "author"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.AGGREGATOR, global_scope=True, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://developers.zenodo.org/", notes="Anonymous published-record metadata search; files are not downloaded."),
    _source("internet_archive_metadata", "Internet Archive Metadata Search", categories={Category.ARCHIVE, Category.OPEN_DATA}, capabilities={"archive_search", "internet_archive", "historical_document", "keyword", "name"}, transport=Transport.REST, access=Access.NO_AUTH, origin=Origin.COMMUNITY_INDEX, global_scope=True, default_enabled=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://archive.org/advancedsearch.php", notes="Advanced Search item metadata only; item content/media are not downloaded."),
    _source("un_sc_sanctions", "UN Security Council Consolidated Sanctions List", categories={Category.SANCTIONS, Category.PUBLIC_OFFICIAL}, capabilities={"sanctions_name", "sanctions_entity", "un_sanctions"}, transport=Transport.PUBLIC_HTTP, access=Access.NO_AUTH, origin=Origin.OFFICIAL_OPEN_DATA, global_scope=True, default_enabled=False, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list", notes="Explicit sanctions search only. Small official XML is processed transiently and not persisted; name matches are not identity confirmation or proof of guilt."),
'''
    text = replace_once(text, descriptor_anchor, descriptors, "R13.17 descriptors")

    coverage_anchor = '''    SourceCoverageEntry("cisa_kev", Status.ACTIVE, "CisaKevAdapter", "R13.16 transient exact-CVE feed lookup"),\n'''
    coverage = coverage_anchor + '''    SourceCoverageEntry("rdap_bootstrap", Status.ACTIVE, "RdapBootstrapAdapter", "R13.17 exact domain/IP/ASN"),
    SourceCoverageEntry("ripestat", Status.ACTIVE, "RipeStatAdapter", "R13.17 network metadata"),
    SourceCoverageEntry("peeringdb_public", Status.ACTIVE, "PeeringDbAdapter", "R13.17 guest exact-ASN"),
    SourceCoverageEntry("google_public_dns", Status.ACTIVE, "GooglePublicDnsAdapter", "R13.17 bounded DNS JSON"),
    SourceCoverageEntry("usaspending_recipients", Status.ACTIVE, "UsaSpendingRecipientAdapter", "R13.17 recipient candidates"),
    SourceCoverageEntry("us_federal_register", Status.ACTIVE, "FederalRegisterAdapter", "R13.17 document mentions"),
    SourceCoverageEntry("datacite_public", Status.ACTIVE, "DataCiteAdapter", "R13.17 DOI metadata"),
    SourceCoverageEntry("zenodo_public", Status.ACTIVE, "ZenodoPublicAdapter", "R13.17 public record metadata"),
    SourceCoverageEntry("internet_archive_metadata", Status.ACTIVE, "InternetArchiveMetadataAdapter", "R13.17 metadata-only archive search"),
    SourceCoverageEntry("un_sc_sanctions", Status.ACTIVE, "UnSecurityCouncilSanctionsAdapter", "R13.17 explicit transient sanctions search"),
'''
    return replace_once(text, coverage_anchor, coverage, "R13.17 coverage")


def patch_container(text: str) -> str:
    import_anchor = '''from app.intelligence_sources.adapters.cisa_kev import CisaKevAdapter\n'''
    imports = import_anchor + '''from app.intelligence_sources.adapters.rdap_bootstrap import RdapBootstrapAdapter
from app.intelligence_sources.adapters.ripestat import RipeStatAdapter
from app.intelligence_sources.adapters.peeringdb import PeeringDbAdapter
from app.intelligence_sources.adapters.google_dns import GooglePublicDnsAdapter
from app.intelligence_sources.adapters.usaspending import UsaSpendingRecipientAdapter
from app.intelligence_sources.adapters.federal_register import FederalRegisterAdapter
from app.intelligence_sources.adapters.datacite import DataCiteAdapter
from app.intelligence_sources.adapters.zenodo_public import ZenodoPublicAdapter
from app.intelligence_sources.adapters.internet_archive import InternetArchiveMetadataAdapter
from app.intelligence_sources.adapters.un_sanctions import UnSecurityCouncilSanctionsAdapter
'''
    text = replace_once(text, import_anchor, imports, "R13.17 service-container imports")

    register_anchor = '''        self.remote_source_adapter_registry.register(CisaKevAdapter())\n\n        self.remote_source_adapter_service = RemoteSourceAdapterService(\n'''
    registrations = '''        self.remote_source_adapter_registry.register(CisaKevAdapter())

        # R13.17 — Low-Footprint Remote Data Mega Pack 2.
        self.remote_source_adapter_registry.register(RdapBootstrapAdapter())
        self.remote_source_adapter_registry.register(RipeStatAdapter())
        self.remote_source_adapter_registry.register(PeeringDbAdapter())
        self.remote_source_adapter_registry.register(GooglePublicDnsAdapter())
        self.remote_source_adapter_registry.register(UsaSpendingRecipientAdapter())
        self.remote_source_adapter_registry.register(FederalRegisterAdapter())
        self.remote_source_adapter_registry.register(DataCiteAdapter())
        self.remote_source_adapter_registry.register(ZenodoPublicAdapter())
        self.remote_source_adapter_registry.register(InternetArchiveMetadataAdapter())
        self.remote_source_adapter_registry.register(UnSecurityCouncilSanctionsAdapter())

        self.remote_source_adapter_service = RemoteSourceAdapterService(
'''
    return replace_once(text, register_anchor, registrations, "R13.17 adapter registration")


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
        raise RuntimeError("Missing R13.16 baseline files: " + ", ".join(missing))

    patched: dict[str, str] = {}
    for rel, patcher in PATCHERS.items():
        path = project_root / rel
        patched[rel] = patcher(path.read_text(encoding="utf-8"))

    for rel in NEW_FILES:
        if not (PAYLOAD_DIR / rel).exists():
            raise RuntimeError(f"Patch payload is missing {rel}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_root = project_root / "storage" / "patch_backups" / f"r13_17_{timestamp}"
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

    print(f"R13.17 installed. Backup: {backup_root}")

    if run_tests:
        tests = [
            "tests/test_r13_17_low_footprint_remote_pack_2.py",
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
        description="Install OSINTXZ R13.17 Low-Footprint Remote Data Mega Pack 2"
    )
    parser.add_argument("project_root", nargs="?", default=r"C:\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    install(Path(args.project_root), args.run_tests)


if __name__ == "__main__":
    main()

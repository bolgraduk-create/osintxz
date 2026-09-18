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
    "app/intelligence_sources/adapters/hibp_extended.py",
    "app/intelligence_sources/adapters/github_secret_scanning.py",
    "tests/test_r13_13_leak_paste_source_pack.py",
)

REPLACE_FILES = (
    "app/exposure_intelligence/contracts.py",
    "app/exposure_intelligence/service.py",
)

PATCH_FILES = (
    "app/intelligence_sources/adapters/contracts.py",
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
            "R13.13 expects the successfully tested R13.12 baseline."
        )
    return text.replace(old, new, 1)


def patch_query_contract(text: str) -> str:
    old = '''    timeout: int = 30\n    sources: tuple[str, ...] = ()\n\n    def __post_init__(self) -> None:\n'''
    new = '''    timeout: int = 30\n    sources: tuple[str, ...] = ()\n    verified_scope: bool = False\n\n    def __post_init__(self) -> None:\n'''
    return replace_once(text, old, new, "RemoteSourceQuery.verified_scope")


def patch_builtin(text: str) -> str:
    old_source = '''    _source("intelligencex_search", "Intelligence X — Metadata Search", categories={Category.BREACH_INTELLIGENCE, Category.DARK_WEB, Category.WEB_OSINT}, capabilities={"email", "domain", "url", "ip", "phone", "crypto_address", "breach_lookup", "darkweb_index"}, transport=Transport.REST, access=Access.CONTRACT, cost=Cost.PAID, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, default_enabled=False, sensitivity=DataSensitivity.BREACH_METADATA, documentation_url="https://help.intelx.io/api/", terms_url="https://intelx.io/terms", notes="R13.12 metadata-only adapter. Underlying indexed document contents are not fetched, previewed, exported or persisted."),\n'''
    new_source = old_source + '''    _source("hibp_pastes", "Have I Been Pwned — Paste Metadata", categories={Category.BREACH_INTELLIGENCE}, capabilities={"email", "paste_exposure"}, access=Access.CONTRACT, cost=Cost.MIXED, origin=Origin.BREACH_PROVIDER, global_scope=True, requires_credentials=True, default_enabled=False, sensitivity=DataSensitivity.BREACH_METADATA, documentation_url="https://haveibeenpwned.com/API/v3", notes="Paste metadata only; paste bodies are not fetched by R13.13."),\n    _source("hibp_verified_domain", "Have I Been Pwned — Verified Domain Exposure", categories={Category.BREACH_INTELLIGENCE}, capabilities={"verified_domain_breach", "domain_exposure"}, access=Access.VERIFIED_SCOPE, cost=Cost.MIXED, origin=Origin.BREACH_PROVIDER, global_scope=True, requires_credentials=True, default_enabled=False, sensitivity=DataSensitivity.RESTRICTED, documentation_url="https://haveibeenpwned.com/API/v3", notes="Requires explicit verified_scope and server-side HIBP subscribed-domain verification."),\n    _source("hibp_stealer_logs_email", "Have I Been Pwned — Stealer Logs by Email", categories={Category.BREACH_INTELLIGENCE}, capabilities={"stealer_log_email"}, access=Access.VERIFIED_SCOPE, cost=Cost.PAID, origin=Origin.BREACH_PROVIDER, global_scope=True, requires_credentials=True, default_enabled=False, sensitivity=DataSensitivity.RESTRICTED, documentation_url="https://haveibeenpwned.com/API/v3", notes="Verified-domain scope only. HIBP returns affected website domains, not passwords."),\n    _source("hibp_stealer_logs_email_domain", "Have I Been Pwned — Stealer Logs by Email Domain", categories={Category.BREACH_INTELLIGENCE}, capabilities={"stealer_log_email_domain"}, access=Access.VERIFIED_SCOPE, cost=Cost.PAID, origin=Origin.BREACH_PROVIDER, global_scope=True, requires_credentials=True, default_enabled=False, sensitivity=DataSensitivity.RESTRICTED, documentation_url="https://haveibeenpwned.com/API/v3", notes="Verified-domain scope only; raw credentials are not returned or persisted."),\n    _source("hibp_stealer_logs_website_domain", "Have I Been Pwned — Stealer Logs by Website Domain", categories={Category.BREACH_INTELLIGENCE}, capabilities={"stealer_log_website_domain"}, access=Access.VERIFIED_SCOPE, cost=Cost.PAID, origin=Origin.BREACH_PROVIDER, global_scope=True, requires_credentials=True, default_enabled=False, sensitivity=DataSensitivity.RESTRICTED, documentation_url="https://haveibeenpwned.com/API/v3", notes="Verified website-domain scope only; raw credentials are not returned or persisted."),\n    _source("github_secret_scanning", "GitHub Secret Scanning — Authorized Repository Alerts", categories={Category.BREACH_INTELLIGENCE, Category.WEB_OSINT}, capabilities={"repository_secret_exposure"}, access=Access.VERIFIED_SCOPE, cost=Cost.MIXED, origin=Origin.OFFICIAL_API, global_scope=True, requires_credentials=True, default_enabled=False, sensitivity=DataSensitivity.RESTRICTED, documentation_url="https://docs.github.com/en/rest/secret-scanning/secret-scanning", notes="Authorized repository scope only. Requests hide_secret=true and discards any literal secret field defensively."),\n'''
    text = replace_once(text, old_source, new_source, "R13.13 source catalog entries")

    old_coverage = '''    SourceCoverageEntry("intelligencex_search", Status.ACTIVE, "IntelligenceXMetadataAdapter", "R13.12 metadata-only; credential-gated"),\n'''
    new_coverage = old_coverage + '''    SourceCoverageEntry("hibp_pastes", Status.ACTIVE, "HibpPasteAdapter", "R13.13 metadata-only; credential-gated"),\n    SourceCoverageEntry("hibp_verified_domain", Status.ACTIVE, "HibpVerifiedDomainAdapter", "R13.13 verified-scope"),\n    SourceCoverageEntry("hibp_stealer_logs_email", Status.ACTIVE, "HibpStealerLogEmailAdapter", "R13.13 verified-scope; Pro"),\n    SourceCoverageEntry("hibp_stealer_logs_email_domain", Status.ACTIVE, "HibpStealerLogEmailDomainAdapter", "R13.13 verified-scope; Pro"),\n    SourceCoverageEntry("hibp_stealer_logs_website_domain", Status.ACTIVE, "HibpStealerLogWebsiteDomainAdapter", "R13.13 verified-scope; Pro"),\n    SourceCoverageEntry("github_secret_scanning", Status.ACTIVE, "GitHubSecretScanningAdapter", "R13.13 authorized-repository; hide-secret"),\n'''
    return replace_once(text, old_coverage, new_coverage, "R13.13 coverage entries")


def patch_config(text: str) -> str:
    old = '''    intelligencex_api_url: str = "https://2.intelx.io"\n    openalex_api_key: str | None = None\n'''
    new = '''    intelligencex_api_url: str = "https://2.intelx.io"\n    # Optional token used only for repository-scoped GitHub Secret Scanning.\n    # The adapter always requests hide_secret=true and requires verified_scope.\n    github_secret_scanning_token: str | None = None\n    openalex_api_key: str | None = None\n'''
    return replace_once(text, old, new, "GitHub secret-scanning setting")


def patch_env(text: str) -> str:
    old = '''INTELLIGENCEX_API_URL=https://2.intelx.io\n'''
    new = old + '''\n# R13.13 — optional authorized GitHub repository secret scanning.\n# Fine-grained token needs Secret scanning alerts: read for the target repository.\nGITHUB_SECRET_SCANNING_TOKEN=\n'''
    return replace_once(text, old, new, ".env.example R13.13 setting")


def patch_container(text: str) -> str:
    import_anchor = '''from app.intelligence_sources.adapters.tor_public import TorPublicOnionAdapter\n'''
    imports = import_anchor + '''from app.intelligence_sources.adapters.hibp_extended import (\n    HibpExtendedClient,\n    HibpPasteAdapter,\n    HibpVerifiedDomainAdapter,\n    HibpStealerLogEmailAdapter,\n    HibpStealerLogEmailDomainAdapter,\n    HibpStealerLogWebsiteDomainAdapter,\n)\nfrom app.intelligence_sources.adapters.github_secret_scanning import (\n    GitHubSecretScanningAdapter,\n    GitHubSecretScanningClient,\n)\n'''
    text = replace_once(text, import_anchor, imports, "R13.13 service-container imports")

    client_anchor = '''        self.intelligencex_search_client = IntelligenceXSearchClient(\n            api_key=settings.intelligencex_api_key,\n            base_url=settings.intelligencex_api_url,\n        )\n\n        # R13.9 — Remote Adapter Pack 1.\n'''
    client_block = '''        self.intelligencex_search_client = IntelligenceXSearchClient(\n            api_key=settings.intelligencex_api_key,\n            base_url=settings.intelligencex_api_url,\n        )\n        self.hibp_extended_client = HibpExtendedClient(\n            api_key=settings.haveibeenpwned_api_key,\n        )\n        self.github_secret_scanning_client = GitHubSecretScanningClient(\n            token=settings.github_secret_scanning_token,\n        )\n\n        # R13.9 — Remote Adapter Pack 1.\n'''
    text = replace_once(text, client_anchor, client_block, "R13.13 client wiring")

    register_anchor = '''        self.remote_source_adapter_registry.register(\n            TorPublicOnionAdapter(service=self.darkweb_intelligence_service)\n        )\n\n        self.remote_source_adapter_service = RemoteSourceAdapterService(\n'''
    register_block = '''        self.remote_source_adapter_registry.register(\n            TorPublicOnionAdapter(service=self.darkweb_intelligence_service)\n        )\n\n        # R13.13 — leak/paste and verified-scope exposure adapters.\n        self.remote_source_adapter_registry.register(\n            HibpPasteAdapter(client=self.hibp_extended_client)\n        )\n        self.remote_source_adapter_registry.register(\n            HibpVerifiedDomainAdapter(client=self.hibp_extended_client)\n        )\n        self.remote_source_adapter_registry.register(\n            HibpStealerLogEmailAdapter(client=self.hibp_extended_client)\n        )\n        self.remote_source_adapter_registry.register(\n            HibpStealerLogEmailDomainAdapter(client=self.hibp_extended_client)\n        )\n        self.remote_source_adapter_registry.register(\n            HibpStealerLogWebsiteDomainAdapter(client=self.hibp_extended_client)\n        )\n        self.remote_source_adapter_registry.register(\n            GitHubSecretScanningAdapter(client=self.github_secret_scanning_client)\n        )\n\n        self.remote_source_adapter_service = RemoteSourceAdapterService(\n'''
    return replace_once(text, register_anchor, register_block, "R13.13 adapter registration")


PATCHERS = {
    "app/intelligence_sources/adapters/contracts.py": patch_query_contract,
    "app/intelligence_sources/builtin_sources.py": patch_builtin,
    "app/core/config.py": patch_config,
    "app/core/service_container.py": patch_container,
    ".env.example": patch_env,
}


def install(project_root: Path, run_tests: bool) -> None:
    project_root = project_root.resolve()
    if not (project_root / "app").is_dir():
        raise RuntimeError(f"Not an OSINTXZ project root: {project_root}")

    required = PATCH_FILES + REPLACE_FILES
    missing = [path for path in required if not (project_root / path).exists()]
    if missing:
        raise RuntimeError("Missing R13.12 baseline files: " + ", ".join(missing))

    # Preflight every anchor and every payload before modifying the project.
    patched: dict[str, str] = {}
    for rel, patcher in PATCHERS.items():
        path = project_root / rel
        patched[rel] = patcher(path.read_text(encoding="utf-8"))

    for rel in NEW_FILES + REPLACE_FILES:
        if not (PAYLOAD_DIR / rel).exists():
            raise RuntimeError(f"Patch payload is missing {rel}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = project_root / "storage" / "patch_backups" / f"r13_13_{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    for rel in required:
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

    for rel in REPLACE_FILES + NEW_FILES:
        src = PAYLOAD_DIR / rel
        dst = project_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    print(f"R13.13 installed. Backup: {backup_root}")

    if run_tests:
        tests = [
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
        description="Install OSINTXZ R13.13 Leak / Paste / Exposure Source Pack"
    )
    parser.add_argument("project_root", nargs="?", default=r"C:\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    install(Path(args.project_root), args.run_tests)


if __name__ == "__main__":
    main()

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
    "app/intelligence_sources/adapters/hibp_breach.py",
    "app/intelligence_sources/adapters/intelligencex.py",
    "app/intelligence_sources/adapters/tor_public.py",
    "app/exposure_intelligence/__init__.py",
    "app/exposure_intelligence/contracts.py",
    "app/exposure_intelligence/service.py",
    "app/exposure_intelligence/persistence.py",
    "tests/test_r13_12_exposure_federation.py",
)

PATCH_FILES = (
    "app/intelligence_sources/adapters/base.py",
    "app/intelligence_sources/adapters/registry.py",
    "app/intelligence_sources/adapters/service.py",
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
            "Your project may not match the R13.11 baseline."
        )
    return text.replace(old, new, 1)


def patch_base(text: str) -> str:
    old = '''    @property\n    def configured(self) -> bool:\n        return True\n\n    def supports(self, query: RemoteSourceQuery) -> bool:\n'''
    new = '''    @property\n    def configured(self) -> bool:\n        return True\n\n    @property\n    def automatic_enabled(self) -> bool:\n        """Whether an adapter may run in an unscoped generic federation query.\n\n        Contract, paid, privacy-sensitive, or side-effect-prone adapters can\n        return False and still be executed when explicitly named in\n        RemoteSourceQuery.sources.\n        """\n        return True\n\n    def supports(self, query: RemoteSourceQuery) -> bool:\n'''
    return replace_once(text, old, new, "RemoteSourceAdapter.automatic_enabled")


def patch_registry(text: str) -> str:
    old = '''        return tuple(\n            adapter\n            for adapter in self.all()\n            if adapter.supports(query)\n            and (not requested or adapter.source_code in requested)\n        )\n'''
    new = '''        return tuple(\n            adapter\n            for adapter in self.all()\n            if adapter.supports(query)\n            and (not requested or adapter.source_code in requested)\n            and (requested or adapter.automatic_enabled)\n        )\n'''
    return replace_once(text, old, new, "RemoteSourceAdapterRegistry.compatible")


def patch_service(text: str) -> str:
    old = '''            result = self.sanitizer.sanitize(result).value\n            out.provider_results.append(result)\n'''
    new = '''            sanitized = self.sanitizer.sanitize(result)\n            result = sanitized.value\n            result.metadata = dict(result.metadata)\n            if sanitized.redacted_count:\n                result.metadata["secret_fields_redacted"] = (\n                    int(result.metadata.get("secret_fields_redacted") or 0)\n                    + sanitized.redacted_count\n                )\n            result.metadata["raw_secret_values_stored"] = False\n            out.provider_results.append(result)\n'''
    return replace_once(text, old, new, "RemoteSourceAdapterService sanitizer metadata")


def patch_builtin(text: str) -> str:
    old_source = '''    _source("tor_public_onion_fetch", "Tor Public Onion Fetch", categories={Category.DARK_WEB}, capabilities={"onion_url", "email", "domain", "username", "crypto_address", "public_page_observation"}, transport=Transport.TOR_HTTP, origin=Origin.DARKWEB_PUBLICATION, global_scope=True, sensitivity=DataSensitivity.DARKWEB_PUBLIC, documentation_url="https://support.torproject.org/tor-browser/features/onion-services/"),\n'''
    new_source = old_source + '''    _source("intelligencex_search", "Intelligence X — Metadata Search", categories={Category.BREACH_INTELLIGENCE, Category.DARK_WEB, Category.WEB_OSINT}, capabilities={"email", "domain", "url", "ip", "phone", "crypto_address", "breach_lookup", "darkweb_index"}, transport=Transport.REST, access=Access.CONTRACT, cost=Cost.PAID, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, default_enabled=False, sensitivity=DataSensitivity.BREACH_METADATA, documentation_url="https://help.intelx.io/api/", terms_url="https://intelx.io/terms", notes="R13.12 metadata-only adapter. Underlying indexed document contents are not fetched, previewed, exported or persisted."),\n'''
    text = replace_once(text, old_source, new_source, "IntelX source catalog entry")

    old_coverage = '''    SourceCoverageEntry("tor_public_onion_fetch", Status.ACTIVE, "DarkWebIntelligenceService", "R13.7"),\n'''
    new_coverage = old_coverage + '''    SourceCoverageEntry("intelligencex_search", Status.ACTIVE, "IntelligenceXMetadataAdapter", "R13.12 metadata-only; credential-gated"),\n'''
    return replace_once(text, old_coverage, new_coverage, "IntelX coverage entry")


def patch_config(text: str) -> str:
    old = '''    intelligencex_api_key: str | None = None\n    openalex_api_key: str | None = None\n'''
    new = '''    intelligencex_api_key: str | None = None\n    # Use the API instance assigned to your Intelligence X account/license.\n    intelligencex_api_url: str = "https://2.intelx.io"\n    openalex_api_key: str | None = None\n'''
    return replace_once(text, old, new, "Intelligence X API URL setting")


def patch_env(text: str) -> str:
    marker = '''DARKWEB_TOR_SOCKS_PROXY=socks5h://127.0.0.1:9050\n'''
    addition = marker + '''\n# ==========================================\n# R13.12 Exposure Intelligence (optional)\n# ==========================================\n# HIBP breached-account lookup requires an API subscription key.\nHAVEIBEENPWNED_API_KEY=\n# Intelligence X requires an API key/license for third-party integrations.\nINTELLIGENCEX_API_KEY=\n# Set this to the official API instance assigned to your IntelX account.\nINTELLIGENCEX_API_URL=https://2.intelx.io\n'''
    return replace_once(text, marker, addition, ".env.example R13.12 settings")


def patch_container(text: str) -> str:
    import_anchor = '''from app.intelligence_sources.adapters.poland_regon import PolandRegonAdapter\n'''
    imports = import_anchor + '''from app.intelligence_sources.adapters.hibp_breach import HibpBreachAdapter\nfrom app.intelligence_sources.adapters.intelligencex import (\n    IntelligenceXMetadataAdapter,\n    IntelligenceXSearchClient,\n)\nfrom app.intelligence_sources.adapters.tor_public import TorPublicOnionAdapter\nfrom app.exposure_intelligence.service import ExposureFederationService\nfrom app.exposure_intelligence.persistence import ExposurePersistenceService\n'''
    text = replace_once(text, import_anchor, imports, "R13.12 service-container imports")

    breach_anchor = '''        self.breach_intelligence_service = BreachIntelligenceService(\n            hibp_client=self.hibp_http_client,\n            data_sanitizer=IntelligenceDataSanitizer(),\n        )\n\n        # R13.9 — Remote Adapter Pack 1.\n'''
    breach_block = '''        self.breach_intelligence_service = BreachIntelligenceService(\n            hibp_client=self.hibp_http_client,\n            data_sanitizer=IntelligenceDataSanitizer(),\n        )\n\n        # R13.12 — metadata-only Intelligence X search client.\n        self.intelligencex_search_client = IntelligenceXSearchClient(\n            api_key=settings.intelligencex_api_key,\n            base_url=settings.intelligencex_api_url,\n        )\n\n        # R13.9 — Remote Adapter Pack 1.\n'''
    text = replace_once(text, breach_anchor, breach_block, "IntelX client wiring")

    register_anchor = '''        self.remote_source_adapter_registry.register(\n            PolandRegonAdapter(user_key=settings.poland_regon_api_key)\n        )\n\n        self.remote_source_adapter_service = RemoteSourceAdapterService(\n'''
    register_block = '''        self.remote_source_adapter_registry.register(\n            PolandRegonAdapter(user_key=settings.poland_regon_api_key)\n        )\n\n        # R13.12 — Exposure Federation adapters. They are explicit-selection\n        # adapters, so generic federation queries do not consume contract APIs\n        # or fetch onion pages unexpectedly.\n        self.remote_source_adapter_registry.register(\n            HibpBreachAdapter(service=self.breach_intelligence_service)\n        )\n        self.remote_source_adapter_registry.register(\n            IntelligenceXMetadataAdapter(client=self.intelligencex_search_client)\n        )\n        self.remote_source_adapter_registry.register(\n            TorPublicOnionAdapter(service=self.darkweb_intelligence_service)\n        )\n\n        self.remote_source_adapter_service = RemoteSourceAdapterService(\n'''
    text = replace_once(text, register_anchor, register_block, "R13.12 adapter registration")

    service_anchor = '''        self.remote_source_adapter_service = RemoteSourceAdapterService(\n            registry=self.remote_source_adapter_registry\n        )\n\n        # M022 Registry Intelligence\n'''
    service_block = '''        self.remote_source_adapter_service = RemoteSourceAdapterService(\n            registry=self.remote_source_adapter_registry\n        )\n        self.exposure_intelligence_service = ExposureFederationService(\n            remote_service=self.remote_source_adapter_service\n        )\n        self.exposure_persistence_service = ExposurePersistenceService(\n            source_service=self.source_service,\n            evidence_service=self.evidence_service,\n            data_sanitizer=IntelligenceDataSanitizer(),\n        )\n\n        # M022 Registry Intelligence\n'''
    return replace_once(text, service_anchor, service_block, "Exposure service wiring")


PATCHERS = {
    "app/intelligence_sources/adapters/base.py": patch_base,
    "app/intelligence_sources/adapters/registry.py": patch_registry,
    "app/intelligence_sources/adapters/service.py": patch_service,
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
        raise RuntimeError("Missing baseline files: " + ", ".join(missing))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = project_root / "storage" / "patch_backups" / f"r13_12_{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    # Compute every patched text before changing the project. This makes an
    # anchor mismatch fail safely without leaving a half-installed patch.
    patched: dict[str, str] = {}
    for rel, patcher in PATCHERS.items():
        path = project_root / rel
        original = path.read_text(encoding="utf-8")
        patched[rel] = patcher(original)

    for rel in PATCH_FILES:
        src = project_root / rel
        dst = backup_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for rel, content in patched.items():
        (project_root / rel).write_text(content, encoding="utf-8")

    for rel in NEW_FILES:
        src = PAYLOAD_DIR / rel
        if not src.exists():
            raise RuntimeError(f"Patch payload is missing {rel}")
        dst = project_root / rel
        if dst.exists():
            backup = backup_root / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, backup)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    print(f"R13.12 installed. Backup: {backup_root}")

    if run_tests:
        tests = [
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
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.12 Exposure Federation Core")
    parser.add_argument("project_root", nargs="?", default=r"C:\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    install(Path(args.project_root), args.run_tests)


if __name__ == "__main__":
    main()

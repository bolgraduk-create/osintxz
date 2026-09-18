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
    "app/darkweb_intelligence/discovery_contracts.py",
    "app/darkweb_intelligence/ahmia.py",
    "app/darkweb_intelligence/discovery.py",
    "app/intelligence_sources/adapters/onion_discovery.py",
    "tests/test_r13_14_darkweb_discovery_indexing.py",
)

REPLACE_FILES = (
    "app/exposure_intelligence/contracts.py",
    "app/exposure_intelligence/service.py",
    "app/exposure_intelligence/persistence.py",
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
            "R13.14 expects the successfully tested R13.13 baseline."
        )
    return text.replace(old, new, 1)


def patch_builtin(text: str) -> str:
    old_source = '''    _source("tor_public_onion_fetch", "Tor Public Onion Fetch", categories={Category.DARK_WEB}, capabilities={"onion_url", "email", "domain", "username", "crypto_address", "public_page_observation"}, transport=Transport.TOR_HTTP, origin=Origin.DARKWEB_PUBLICATION, global_scope=True, sensitivity=DataSensitivity.DARKWEB_PUBLIC, documentation_url="https://support.torproject.org/tor-browser/features/onion-services/"),\n'''
    new_source = old_source + '''    _source("tor_onion_discovery", "Tor Public Onion Discovery", categories={Category.DARK_WEB}, capabilities={"darkweb_discovery", "onion_discovery", "email", "domain", "username", "crypto_address"}, transport=Transport.TOR_HTTP, access=Access.MANUAL_ASSISTED, origin=Origin.DARKWEB_PUBLICATION, global_scope=True, default_enabled=False, sensitivity=DataSensitivity.DARKWEB_PUBLIC, documentation_url="https://support.torproject.org/tor-browser/features/onion-services/", notes="R13.14 bounded public-v3-onion discovery. Ahmia safety blocklist is required by default; no login, POST, redirect following, file download or raw page storage."),\n'''
    text = replace_once(text, old_source, new_source, "R13.14 dark-web discovery source")

    old_coverage = '''    SourceCoverageEntry("tor_public_onion_fetch", Status.ACTIVE, "DarkWebIntelligenceService", "R13.7"),\n'''
    new_coverage = old_coverage + '''    SourceCoverageEntry("tor_onion_discovery", Status.ACTIVE, "DarkWebDiscoveryService", "R13.14 bounded crawl + Ahmia safety filter"),\n'''
    return replace_once(text, old_coverage, new_coverage, "R13.14 coverage entry")


def patch_container(text: str) -> str:
    import_anchor = '''from app.intelligence_sources.adapters.github_secret_scanning import (\n    GitHubSecretScanningAdapter,\n    GitHubSecretScanningClient,\n)\n'''
    imports = import_anchor + '''from app.darkweb_intelligence.ahmia import AhmiaDirectoryClient\nfrom app.darkweb_intelligence.discovery import DarkWebDiscoveryService\nfrom app.intelligence_sources.adapters.onion_discovery import TorOnionDiscoveryAdapter\n'''
    text = replace_once(text, import_anchor, imports, "R13.14 service-container imports")

    client_anchor = '''        self.github_secret_scanning_client = GitHubSecretScanningClient(\n            token=settings.github_secret_scanning_token,\n        )\n\n        # R13.9 — Remote Adapter Pack 1.\n'''
    client_block = '''        self.github_secret_scanning_client = GitHubSecretScanningClient(\n            token=settings.github_secret_scanning_token,\n        )\n\n        # R13.14 — bounded public onion discovery + Ahmia safety metadata.\n        self.ahmia_directory_client = AhmiaDirectoryClient()\n        self.darkweb_discovery_service = DarkWebDiscoveryService(\n            page_service=self.darkweb_intelligence_service,\n            ahmia_client=self.ahmia_directory_client,\n        )\n\n        # R13.9 — Remote Adapter Pack 1.\n'''
    text = replace_once(text, client_anchor, client_block, "R13.14 discovery service wiring")

    register_anchor = '''        self.remote_source_adapter_registry.register(\n            GitHubSecretScanningAdapter(client=self.github_secret_scanning_client)\n        )\n\n        self.remote_source_adapter_service = RemoteSourceAdapterService(\n'''
    register_block = '''        self.remote_source_adapter_registry.register(\n            GitHubSecretScanningAdapter(client=self.github_secret_scanning_client)\n        )\n        self.remote_source_adapter_registry.register(\n            TorOnionDiscoveryAdapter(service=self.darkweb_discovery_service)\n        )\n\n        self.remote_source_adapter_service = RemoteSourceAdapterService(\n'''
    return replace_once(text, register_anchor, register_block, "R13.14 adapter registration")


PATCHERS = {
    "app/intelligence_sources/builtin_sources.py": patch_builtin,
    "app/core/service_container.py": patch_container,
}


def install(project_root: Path, run_tests: bool) -> None:
    project_root = project_root.resolve()
    if not (project_root / "app").is_dir():
        raise RuntimeError(f"Not an OSINTXZ project root: {project_root}")

    required = PATCH_FILES + REPLACE_FILES
    missing = [path for path in required if not (project_root / path).exists()]
    if missing:
        raise RuntimeError("Missing R13.13 baseline files: " + ", ".join(missing))

    patched: dict[str, str] = {}
    for rel, patcher in PATCHERS.items():
        path = project_root / rel
        patched[rel] = patcher(path.read_text(encoding="utf-8"))

    for rel in NEW_FILES + REPLACE_FILES:
        if not (PAYLOAD_DIR / rel).exists():
            raise RuntimeError(f"Patch payload is missing {rel}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = project_root / "storage" / "patch_backups" / f"r13_14_{timestamp}"
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

    print(f"R13.14 installed. Backup: {backup_root}")

    if run_tests:
        tests = [
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
        description="Install OSINTXZ R13.14 Dark Web Discovery & Indexing"
    )
    parser.add_argument("project_root", nargs="?", default=r"C:\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    install(Path(args.project_root), args.run_tests)


if __name__ == "__main__":
    main()

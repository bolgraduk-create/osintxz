from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys


NEW_FILES = (
    "app/darkweb_intelligence/__init__.py",
    "app/darkweb_intelligence/contracts.py",
    "app/darkweb_intelligence/tor_client.py",
    "app/darkweb_intelligence/extractor.py",
    "app/darkweb_intelligence/catalog.py",
    "app/darkweb_intelligence/service.py",
    "tests/test_darkweb_intelligence.py",
)

SERVICE_IMPORTS = """from app.darkweb_intelligence.catalog import register_darkweb_sources
from app.darkweb_intelligence.service import DarkWebIntelligenceService
from app.darkweb_intelligence.tor_client import TorOnionHttpClient
"""
SERVICE_IMPORT_ANCHOR = "from app.breach_intelligence.catalog import register_hibp_sources\n"
SERVICE_INIT_ANCHOR = "        register_hibp_sources(self.intelligence_source_catalog)\n"
SERVICE_INIT_BLOCK = """
        register_darkweb_sources(self.intelligence_source_catalog)
        self.tor_onion_http_client = TorOnionHttpClient(
            proxy_url=settings.darkweb_tor_socks_proxy,
        )
        self.darkweb_intelligence_service = DarkWebIntelligenceService(
            client=self.tor_onion_http_client,
            data_sanitizer=IntelligenceDataSanitizer(),
        )
"""

CONFIG_ANCHOR = "    haveibeenpwned_api_key: str | None = None\n"
CONFIG_BLOCK = """

    # ======================================================
    # Dark Web / Tor
    # ======================================================

    # Local Tor SOCKS endpoint only. R13.7 never falls back to a direct
    # internet connection when a .onion request cannot be completed.
    darkweb_tor_socks_proxy: str = "socks5h://127.0.0.1:9050"
"""

ENV_BLOCK = """
# ==========================================
# Dark Web / Tor
# ==========================================
DARKWEB_TOR_SOCKS_PROXY=socks5h://127.0.0.1:9050
"""

PYPROJECT_ANCHOR = '    "httpx>=0.28.1",\n'
PYPROJECT_DEP = '    "socksio>=1.0.0,<2.0.0",\n'


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(f"{path.name}.before_darkweb_{stamp}.bak")
    shutil.copy2(path, target)
    return target


def _write_if_changed(path: Path, original: str, updated: str) -> None:
    if updated == original:
        print(f"[OK] {path} already contains R13.7 changes")
        return
    backup = _backup(path)
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}")
    print(f"[OK] Backup: {backup}")


def _patch_service(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original
    if "from app.darkweb_intelligence.service import DarkWebIntelligenceService\n" not in updated:
        if updated.count(SERVICE_IMPORT_ANCHOR) != 1:
            raise RuntimeError(
                "R13.6 import anchor not found; install R13.6 first."
            )
        updated = updated.replace(
            SERVICE_IMPORT_ANCHOR,
            SERVICE_IMPORT_ANCHOR + SERVICE_IMPORTS,
            1,
        )
    if "self.darkweb_intelligence_service = DarkWebIntelligenceService(" not in updated:
        if updated.count(SERVICE_INIT_ANCHOR) != 1:
            raise RuntimeError(
                "R13.6 catalog initialization anchor not found; aborting."
            )
        updated = updated.replace(
            SERVICE_INIT_ANCHOR,
            SERVICE_INIT_ANCHOR + SERVICE_INIT_BLOCK,
            1,
        )
    _write_if_changed(path, original, updated)


def _patch_config(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if "    darkweb_tor_socks_proxy:" in original:
        print(f"[OK] {path} already contains R13.7 changes")
        return
    if original.count(CONFIG_ANCHOR) != 1:
        raise RuntimeError("Safe config anchor not found.")
    updated = original.replace(
        CONFIG_ANCHOR,
        CONFIG_ANCHOR + CONFIG_BLOCK,
        1,
    )
    _write_if_changed(path, original, updated)


def _patch_env(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if "DARKWEB_TOR_SOCKS_PROXY=" in original:
        print(f"[OK] {path} already contains R13.7 changes")
        return
    updated = original.rstrip() + "\n\n" + ENV_BLOCK
    _write_if_changed(path, original, updated)


def _patch_pyproject(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if '"socksio>=1.0.0,<2.0.0"' in original:
        print(f"[OK] {path} already contains socksio dependency")
        return
    if original.count(PYPROJECT_ANCHOR) != 1:
        raise RuntimeError("Safe pyproject httpx dependency anchor not found.")
    updated = original.replace(
        PYPROJECT_ANCHOR,
        PYPROJECT_ANCHOR + PYPROJECT_DEP,
        1,
    )
    _write_if_changed(path, original, updated)


def _ensure_dependency() -> None:
    if importlib.util.find_spec("socksio") is not None:
        print("[OK] socksio already installed")
        return
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "socksio>=1.0.0,<2.0.0",
    ]
    print("[RUN]", " ".join(command))
    subprocess.run(command, check=True)


def _copy_payload(patch_root: Path, project_root: Path) -> None:
    for relative in NEW_FILES:
        source = patch_root / "payload" / relative
        destination = project_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        print(f"[OK] Installed {relative}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R13.7 Dark Web Intelligence."
    )
    parser.add_argument("project_root", nargs="?", default=r"C:\\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument(
        "--skip-dependency-install",
        action="store_true",
        help="Do not pip-install socksio (used for packaging/dry-run only).",
    )
    args = parser.parse_args()

    patch_root = Path(__file__).resolve().parent
    project_root = Path(args.project_root).resolve()
    service = project_root / "app/core/service_container.py"
    config = project_root / "app/core/config.py"
    env = project_root / ".env.example"
    pyproject = project_root / "pyproject.toml"
    federation = project_root / "app/intelligence_sources/policy.py"
    breach = project_root / "app/breach_intelligence/service.py"

    missing = [
        str(item)
        for item in (service, config, env, pyproject, federation, breach)
        if not item.exists()
    ]
    if missing:
        print(
            "[ERROR] R13.5 and R13.6 are required; missing: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    _copy_payload(patch_root, project_root)
    _patch_config(config)
    _patch_env(env)
    _patch_pyproject(pyproject)
    _patch_service(service)

    if not args.skip_dependency_install:
        _ensure_dependency()

    print("[OK] R13.7 Dark Web Intelligence installed.")
    print("[INFO] No database migration is required.")
    print("[INFO] Only explicit public v3 .onion GET requests are supported.")
    print("[INFO] Raw HTML/page text and file attachments are not persisted by this module.")

    if args.run_tests:
        command = [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_darkweb_intelligence.py",
            "-q",
        ]
        print("[RUN]", " ".join(command))
        return subprocess.run(command, cwd=project_root, check=False).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

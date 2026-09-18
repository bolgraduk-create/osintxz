from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys


NEW_FILES = (
    "app/infrastructure/registries/opencorporates_client.py",
    "app/registry_intelligence/providers/opencorporates.py",
    "tests/test_registry_opencorporates.py",
)

CLIENT_IMPORT = (
    "from app.infrastructure.registries.opencorporates_client import "
    "OpenCorporatesHttpClient\n"
)
CLIENT_IMPORT_ANCHOR = (
    "from app.infrastructure.registries.registry_api_client import "
    "RegistryApiHttpClient\n"
)

PROVIDER_IMPORT = (
    "from app.registry_intelligence.providers.opencorporates import "
    "OpenCorporatesRegistryProvider\n"
)
PROVIDER_IMPORT_ANCHOR = (
    "from app.registry_intelligence.providers.remote import "
    "RemoteRegistryProvider\n"
)

REGISTRY_SECTION_ANCHOR = (
    "        # Large national datasets are never synchronized by end-user desktops.\n"
)

REGISTRATION_BLOCK = """        # R5 — OpenCorporates aggregator (optional API token).
        opencorporates_token = (
            settings.opencorporates_api_token.get_secret_value()
            if settings.opencorporates_api_token is not None
            else None
        )
        self.opencorporates_http_client = OpenCorporatesHttpClient(
            api_token=opencorporates_token
        )
        self.opencorporates_registry_provider = OpenCorporatesRegistryProvider(
            client=self.opencorporates_http_client
        )
        self.registry_provider_registry.register(
            self.opencorporates_registry_provider
        )

"""

CONFIG_ANCHOR = "    registry_backend_port: int = 8011\n"
CONFIG_BLOCK = """
    # ======================================================
    # External Registry Credentials
    # ======================================================

    # Optional. OpenCorporates currently requires an API token.
    # If absent, the provider remains registered but is blocked by the
    # existing RegistryQueryRouter credential-access policy.
    opencorporates_api_token: SecretStr | None = None
"""

ENV_ANCHOR = """# ==========================================
# PostgreSQL
# ==========================================
"""
ENV_BLOCK = """# ==========================================
# External Registry Credentials (optional)
# ==========================================

# OpenCorporates REST API token. Leave empty to keep the provider disabled.
OPENCORPORATES_API_TOKEN=


"""


def backup(path: Path, label: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(f"{path.name}.before_{label}_{timestamp}.bak")
    shutil.copy2(path, target)
    return target


def insert_before_once(text: str, *, anchor: str, addition: str, already_present: str) -> str:
    if already_present in text:
        return text
    if text.count(anchor) != 1:
        raise RuntimeError(
            "Expected exactly one patch anchor but repository structure differs. "
            "Aborting instead of guessing."
        )
    return text.replace(anchor, addition + anchor, 1)


def insert_after_once(text: str, *, anchor: str, addition: str, already_present: str) -> str:
    if already_present in text:
        return text
    if text.count(anchor) != 1:
        raise RuntimeError(
            "Expected exactly one patch anchor but repository structure differs. "
            "Aborting instead of guessing."
        )
    return text.replace(anchor, anchor + addition, 1)


def patch_service_container(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = insert_before_once(
        original,
        anchor=CLIENT_IMPORT_ANCHOR,
        addition=CLIENT_IMPORT,
        already_present=CLIENT_IMPORT,
    )
    updated = insert_before_once(
        updated,
        anchor=PROVIDER_IMPORT_ANCHOR,
        addition=PROVIDER_IMPORT,
        already_present=PROVIDER_IMPORT,
    )
    updated = insert_before_once(
        updated,
        anchor=REGISTRY_SECTION_ANCHOR,
        addition=REGISTRATION_BLOCK,
        already_present="self.opencorporates_registry_provider = OpenCorporatesRegistryProvider(",
    )
    if updated != original:
        target = backup(path, "opencorporates")
        path.write_text(updated, encoding="utf-8")
        print(f"[OK] Patched {path}")
        print(f"[OK] Backup: {target}")
    else:
        print(f"[OK] {path} already contains OpenCorporates patch")


def patch_config(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = insert_after_once(
        original,
        anchor=CONFIG_ANCHOR,
        addition=CONFIG_BLOCK,
        already_present="    opencorporates_api_token:",
    )
    if updated != original:
        target = backup(path, "opencorporates")
        path.write_text(updated, encoding="utf-8")
        print(f"[OK] Patched {path}")
        print(f"[OK] Backup: {target}")
    else:
        print(f"[OK] {path} already contains OpenCorporates setting")


def patch_env_example(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = insert_before_once(
        original,
        anchor=ENV_ANCHOR,
        addition=ENV_BLOCK,
        already_present="OPENCORPORATES_API_TOKEN=",
    )
    if updated != original:
        target = backup(path, "opencorporates")
        path.write_text(updated, encoding="utf-8")
        print(f"[OK] Patched {path}")
        print(f"[OK] Backup: {target}")
    else:
        print(f"[OK] {path} already contains OpenCorporates example")


def copy_new_files(patch_root: Path, project_root: Path) -> None:
    for relative in NEW_FILES:
        source = patch_root / "payload" / relative
        destination = project_root / relative
        if not source.exists():
            raise FileNotFoundError(f"Patch payload missing: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        print(f"[OK] Installed {relative}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R5 OpenCorporates Registry patch."
    )
    parser.add_argument("project_root", nargs="?", default=r"C:\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    patch_root = Path(__file__).resolve().parent
    project_root = Path(args.project_root).resolve()

    service_container = project_root / "app/core/service_container.py"
    config = project_root / "app/core/config.py"
    env_example = project_root / ".env.example"

    required = (service_container, config, env_example)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print(
            "[ERROR] Project root is missing required files: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    copy_new_files(patch_root, project_root)
    patch_config(config)
    patch_env_example(env_example)
    patch_service_container(service_container)

    print("[OK] OpenCorporates provider installation complete.")
    print(
        "[INFO] No API key was added. Without OPENCORPORATES_API_TOKEN "
        "the existing RegistryQueryRouter keeps this provider blocked."
    )

    if args.run_tests:
        command = [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_registry_opencorporates.py",
            "-q",
        ]
        print("[RUN]", " ".join(command))
        return subprocess.run(command, cwd=project_root, check=False).returncode

    print("Run: python -m pytest tests/test_registry_opencorporates.py -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

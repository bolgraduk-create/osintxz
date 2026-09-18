from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys


NEW_FILES = (
    "app/infrastructure/registries/companies_house_client.py",
    "app/registry_intelligence/providers/companies_house.py",
    "tests/test_registry_companies_house.py",
)

CLIENT_IMPORT = (
    "from app.infrastructure.registries.companies_house_client import "
    "CompaniesHouseHttpClient\n"
)
CLIENT_IMPORT_ANCHOR = (
    "from app.infrastructure.registries.registry_api_client import "
    "RegistryApiHttpClient\n"
)

PROVIDER_IMPORT = (
    "from app.registry_intelligence.providers.companies_house import "
    "CompaniesHouseRegistryProvider\n"
)
PROVIDER_IMPORT_ANCHOR = (
    "from app.registry_intelligence.providers.remote import "
    "RemoteRegistryProvider\n"
)

REGISTRATION_ANCHOR = (
    "        # Large national datasets are never synchronized by end-user desktops.\n"
)

REGISTRATION_BLOCK = """        # R12 — UK Companies House official Public Data API.
        companies_house_api_key = (
            settings.companies_house_api_key.get_secret_value()
            if settings.companies_house_api_key is not None
            else None
        )
        self.companies_house_http_client = CompaniesHouseHttpClient(
            api_key=companies_house_api_key
        )
        self.companies_house_registry_provider = CompaniesHouseRegistryProvider(
            client=self.companies_house_http_client
        )
        self.registry_provider_registry.register(
            self.companies_house_registry_provider
        )

"""

CONFIG_ANCHOR = """    # ==========================================================
    # PostgreSQL
    # ==========================================================
"""
CONFIG_BLOCK = """    # ======================================================
    # UK Companies House
    # ======================================================

    # Optional official Companies House Public Data API key.
    # Without it, the provider remains registered but the existing
    # RegistryQueryRouter blocks automatic execution.
    companies_house_api_key: SecretStr | None = None

"""

ENV_ANCHOR = """# ==========================================
# PostgreSQL
# ==========================================
"""
ENV_BLOCK = """# ==========================================
# UK Companies House (optional)
# ==========================================

# Official Companies House Public Data API key.
COMPANIES_HOUSE_API_KEY=


"""


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(
        f"{path.name}.before_companies_house_{stamp}.bak"
    )
    shutil.copy2(path, target)
    return target


def _insert_before_once(
    text: str,
    *,
    anchor: str,
    addition: str,
    already_present: str,
) -> str:
    if already_present in text:
        return text
    if text.count(anchor) != 1:
        raise RuntimeError(
            "Expected exactly one patch anchor but repository structure "
            "differs. Aborting instead of guessing."
        )
    return text.replace(anchor, addition + anchor, 1)


def _patch_file(
    path: Path,
    transform,
) -> None:
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    if updated == original:
        print(f"[OK] {path} already contains R12 changes")
        return

    backup = _backup(path)
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}")
    print(f"[OK] Backup: {backup}")


def _patch_config(text: str) -> str:
    if "    companies_house_api_key:" in text:
        return text

    anchors = (
        "    courtlistener_api_token: SecretStr | None = None\n",
        "    opencorporates_api_token: SecretStr | None = None\n",
        "    registry_backend_port: int = 8011\n",
    )

    for anchor in anchors:
        if anchor in text:
            return text.replace(
                anchor,
                anchor + "\n" + CONFIG_BLOCK,
                1,
            )

    raise RuntimeError(
        "Could not locate a safe Registry configuration anchor in "
        "app/core/config.py. Aborting instead of guessing."
    )


def _patch_env(text: str) -> str:
    if "COMPANIES_HOUSE_API_KEY=" in text:
        return text

    anchors = (
        "COURTLISTENER_API_TOKEN=\n",
        "OPENCORPORATES_API_TOKEN=\n",
        "REGISTRY_API_TOKEN=\n",
    )

    for anchor in anchors:
        if anchor in text:
            return text.replace(
                anchor,
                anchor + "\n" + ENV_BLOCK,
                1,
            )

    return text.rstrip() + "\n\n" + ENV_BLOCK


def _patch_service_container(text: str) -> str:
    text = _insert_before_once(
        text,
        anchor=CLIENT_IMPORT_ANCHOR,
        addition=CLIENT_IMPORT,
        already_present=CLIENT_IMPORT,
    )
    text = _insert_before_once(
        text,
        anchor=PROVIDER_IMPORT_ANCHOR,
        addition=PROVIDER_IMPORT,
        already_present=PROVIDER_IMPORT,
    )

    if (
        "self.companies_house_registry_provider = "
        "CompaniesHouseRegistryProvider("
    ) in text:
        return text

    registration_anchors = (
        REGISTRATION_ANCHOR,
        "        registry_token = (\n",
    )
    for anchor in registration_anchors:
        if anchor in text:
            return text.replace(
                anchor,
                REGISTRATION_BLOCK + anchor,
                1,
            )

    raise RuntimeError(
        "Could not locate a safe Registry registration anchor in "
        "app/core/service_container.py. Aborting instead of guessing."
    )


def _copy_payload(patch_root: Path, project_root: Path) -> None:
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
        description="Install OSINTXZ R12 UK Companies House patch."
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=r"C:\osintxz",
        help=r"OSINTXZ root directory (default: C:\osintxz)",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Run the R12 Companies House pytest module.",
    )
    args = parser.parse_args()

    patch_root = Path(__file__).resolve().parent
    project_root = Path(args.project_root).resolve()

    service_container = project_root / "app/core/service_container.py"
    config = project_root / "app/core/config.py"
    env_example = project_root / ".env.example"

    missing = [
        str(path)
        for path in (service_container, config, env_example)
        if not path.exists()
    ]
    if missing:
        print(
            "[ERROR] Project root is missing required files: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    _copy_payload(patch_root, project_root)
    _patch_file(config, _patch_config)
    _patch_file(env_example, _patch_env)
    _patch_file(service_container, _patch_service_container)

    print("[OK] R12 UK Companies House installation complete.")
    print(
        "[INFO] No API key was added. Without COMPANIES_HOUSE_API_KEY "
        "the existing RegistryQueryRouter keeps the provider blocked."
    )

    if args.run_tests:
        command = [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_registry_companies_house.py",
            "-q",
        ]
        print("[RUN]", " ".join(command))
        completed = subprocess.run(
            command,
            cwd=project_root,
            check=False,
        )
        return completed.returncode

    print(
        "Run: python -m pytest "
        "tests/test_registry_companies_house.py -q"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

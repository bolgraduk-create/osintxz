from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys


NEW_FILES = (
    "app/infrastructure/registries/poland_krs_client.py",
    "app/registry_intelligence/providers/poland_krs.py",
    "tests/test_registry_poland_krs.py",
)

CLIENT_IMPORT = (
    "from app.infrastructure.registries.poland_krs_client import "
    "PolandKrsHttpClient\n"
)
PROVIDER_IMPORT = (
    "from app.registry_intelligence.providers.poland_krs import "
    "PolandKrsRegistryProvider\n"
)
CLIENT_IMPORT_ANCHOR = (
    "from app.infrastructure.registries.registry_api_client import "
    "RegistryApiHttpClient\n"
)
PROVIDER_IMPORT_ANCHOR = (
    "from app.registry_intelligence.providers.remote import "
    "RemoteRegistryProvider\n"
)

REGISTRATION_BLOCK = """        # R13 — Poland KRS official Open API.
        self.poland_krs_http_client = PolandKrsHttpClient()
        self.poland_krs_registry_provider = PolandKrsRegistryProvider(
            client=self.poland_krs_http_client
        )
        self.registry_provider_registry.register(
            self.poland_krs_registry_provider
        )

"""


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(
        f"{path.name}.before_poland_krs_{stamp}.bak"
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
            "Expected exactly one safe patch anchor. "
            "Aborting instead of guessing."
        )
    return text.replace(anchor, addition + anchor, 1)


def _patch_service_container(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original

    updated = _insert_before_once(
        updated,
        anchor=CLIENT_IMPORT_ANCHOR,
        addition=CLIENT_IMPORT,
        already_present=CLIENT_IMPORT,
    )
    updated = _insert_before_once(
        updated,
        anchor=PROVIDER_IMPORT_ANCHOR,
        addition=PROVIDER_IMPORT,
        already_present=PROVIDER_IMPORT,
    )

    marker = (
        "self.poland_krs_registry_provider = "
        "PolandKrsRegistryProvider("
    )
    if marker not in updated:
        anchors = (
            "        # Large national datasets are never synchronized by end-user desktops.\n",
            "        registry_token = (\n",
        )
        for anchor in anchors:
            if anchor in updated:
                updated = updated.replace(
                    anchor,
                    REGISTRATION_BLOCK + anchor,
                    1,
                )
                break
        else:
            raise RuntimeError(
                "Could not locate a safe Registry registration anchor."
            )

    if updated == original:
        print(f"[OK] {path} already contains R13 changes")
        return

    backup = _backup(path)
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}")
    print(f"[OK] Backup: {backup}")


def _copy_payload(patch_root: Path, project_root: Path) -> None:
    for relative in NEW_FILES:
        source = patch_root / "payload" / relative
        destination = project_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        print(f"[OK] Installed {relative}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R13 Poland KRS patch."
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=r"C:\osintxz",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
    )
    args = parser.parse_args()

    patch_root = Path(__file__).resolve().parent
    project_root = Path(args.project_root).resolve()
    service_container = project_root / "app/core/service_container.py"

    if not service_container.exists():
        print(
            "[ERROR] Invalid OSINTXZ project root.",
            file=sys.stderr,
        )
        return 2

    _copy_payload(patch_root, project_root)
    _patch_service_container(service_container)

    print("[OK] R13 Poland KRS installation complete.")
    print("[INFO] No API key or database migration is required.")

    if args.run_tests:
        command = [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_registry_poland_krs.py",
            "-q",
        ]
        print("[RUN]", " ".join(command))
        return subprocess.run(
            command,
            cwd=project_root,
            check=False,
        ).returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

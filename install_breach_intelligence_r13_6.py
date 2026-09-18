from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys


NEW_FILES = (
    "app/breach_intelligence/__init__.py",
    "app/breach_intelligence/contracts.py",
    "app/breach_intelligence/hibp_client.py",
    "app/breach_intelligence/catalog.py",
    "app/breach_intelligence/service.py",
    "tests/test_breach_intelligence_hibp.py",
)

IMPORTS = """from app.breach_intelligence.catalog import register_hibp_sources
from app.breach_intelligence.hibp_client import HibpHttpClient
from app.breach_intelligence.service import BreachIntelligenceService
from app.intelligence_sources.catalog import IntelligenceSourceCatalog
from app.intelligence_sources.policy import IntelligenceDataSanitizer
"""
IMPORT_ANCHOR = "from app.infrastructure.registries.gleif_client import GleifRegistryHttpClient\n"

INIT_ANCHOR = "        # M022 Registry Intelligence\n"
INIT_BLOCK = """        # R13.6 — Breach Intelligence / HIBP.
        self.intelligence_source_catalog = IntelligenceSourceCatalog()
        register_hibp_sources(self.intelligence_source_catalog)

        self.hibp_http_client = HibpHttpClient(
            api_key=settings.haveibeenpwned_api_key
        )
        self.breach_intelligence_service = BreachIntelligenceService(
            hibp_client=self.hibp_http_client,
            data_sanitizer=IntelligenceDataSanitizer(),
        )

"""


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(
        f"{path.name}.before_breach_intelligence_{stamp}.bak"
    )
    shutil.copy2(path, target)
    return target


def _patch_service_container(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = original

    if "from app.breach_intelligence.service import BreachIntelligenceService\n" not in updated:
        if updated.count(IMPORT_ANCHOR) != 1:
            raise RuntimeError(
                "Could not locate safe import anchor in service_container.py."
            )
        updated = updated.replace(
            IMPORT_ANCHOR,
            IMPORTS + IMPORT_ANCHOR,
            1,
        )

    if "self.breach_intelligence_service = BreachIntelligenceService(" not in updated:
        if updated.count(INIT_ANCHOR) != 1:
            raise RuntimeError(
                "Could not locate M022 Registry Intelligence anchor in "
                "service_container.py. Aborting instead of guessing."
            )
        updated = updated.replace(
            INIT_ANCHOR,
            INIT_BLOCK + INIT_ANCHOR,
            1,
        )

    if updated == original:
        print(f"[OK] {path} already contains R13.6 changes")
        return

    backup = _backup(path)
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}")
    print(f"[OK] Backup: {backup}")


def _copy_payload(patch_root: Path, project_root: Path) -> None:
    for relative in NEW_FILES:
        source = patch_root / "payload" / relative
        destination = project_root / relative
        if not source.exists():
            raise FileNotFoundError(f"Missing patch payload: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        print(f"[OK] Installed {relative}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R13.6 HIBP Breach Intelligence."
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=r"C:\\osintxz",
    )
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    patch_root = Path(__file__).resolve().parent
    project_root = Path(args.project_root).resolve()

    service_container = project_root / "app/core/service_container.py"
    federation_core = project_root / "app/intelligence_sources/policy.py"

    if not service_container.exists():
        print("[ERROR] Invalid OSINTXZ project root.", file=sys.stderr)
        return 2
    if not federation_core.exists():
        print(
            "[ERROR] R13.5 Intelligence Source Federation Core is required "
            "before R13.6.",
            file=sys.stderr,
        )
        return 3

    _copy_payload(patch_root, project_root)
    _patch_service_container(service_container)

    print("[OK] R13.6 HIBP Breach Intelligence installed.")
    print("[INFO] No database migration or new dependency is required.")
    print(
        "[INFO] HIBP email lookup uses existing HAVEIBEENPWNED_API_KEY "
        "when configured. Pwned Passwords requires no API key."
    )
    print(
        "[INFO] Plaintext passwords and complete password hashes are never "
        "returned by the service."
    )

    if args.run_tests:
        command = [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_breach_intelligence_hibp.py",
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

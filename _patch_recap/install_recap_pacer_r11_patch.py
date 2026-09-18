from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

NEW_FILES = (
    "app/infrastructure/registries/recap_client.py",
    "app/registry_intelligence/providers/recap.py",
    "tests/test_registry_recap_pacer.py",
)
CLIENT_IMPORT = "from app.infrastructure.registries.recap_client import (\n    CourtListenerRecapHttpClient,\n    PacerPaidFetchGuard,\n)\n"
CLIENT_ANCHOR = "from app.infrastructure.registries.registry_api_client import RegistryApiHttpClient\n"
PROVIDER_IMPORT = "from app.registry_intelligence.providers.recap import (\n    CourtListenerRecapRegistryProvider,\n)\n"
PROVIDER_ANCHOR = "from app.registry_intelligence.providers.remote import RemoteRegistryProvider\n"
REGISTRY_ANCHOR = "        # Large national datasets are never synchronized by end-user desktops.\n"
REGISTRATION = """        # R11 — free RECAP archive search + hard PACER purchase guard.\n        self.courtlistener_recap_http_client = CourtListenerRecapHttpClient(\n            api_token=courtlistener_token\n        )\n        self.courtlistener_recap_registry_provider = (\n            CourtListenerRecapRegistryProvider(\n                client=self.courtlistener_recap_http_client\n            )\n        )\n        self.registry_provider_registry.register(\n            self.courtlistener_recap_registry_provider\n        )\n        self.pacer_paid_fetch_guard = PacerPaidFetchGuard()\n\n"""


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(f"{path.name}.before_recap_r11_{stamp}.bak")
    shutil.copy2(path, target)
    return target


def _before(text: str, anchor: str, addition: str, marker: str) -> str:
    if marker in text:
        return text
    if text.count(anchor) != 1:
        raise RuntimeError("Patch anchor mismatch; aborting instead of guessing.")
    return text.replace(anchor, addition + anchor, 1)


def copy_files(patch_root: Path, project_root: Path) -> None:
    for relative in NEW_FILES:
        src = patch_root / "payload" / relative
        dst = project_root / relative
        if not src.exists():
            raise FileNotFoundError(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"[OK] Installed {relative}")


def patch_service_container(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    required = (
        "from app.infrastructure.registries.courtlistener_client import CourtListenerHttpClient",
        "self.courtlistener_registry_provider = CourtListenerRegistryProvider(",
        "courtlistener_token = (",
    )
    if any(marker not in original for marker in required):
        raise RuntimeError("R10 CourtListener prerequisite not found. Install/verify R10 before R11.")
    updated = _before(original, CLIENT_ANCHOR, CLIENT_IMPORT, "CourtListenerRecapHttpClient")
    updated = _before(updated, PROVIDER_ANCHOR, PROVIDER_IMPORT, "CourtListenerRecapRegistryProvider")
    updated = _before(updated, REGISTRY_ANCHOR, REGISTRATION, "self.courtlistener_recap_registry_provider = (")
    if updated != original:
        backup = _backup(path)
        path.write_text(updated, encoding="utf-8")
        print(f"[OK] Patched {path}")
        print(f"[OK] Backup: {backup}")
    else:
        print(f"[OK] {path} already contains R11 patch")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R11 RECAP/PACER safety patch.")
    parser.add_argument("project_root", nargs="?", default=r"C:\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    patch_root = Path(__file__).resolve().parent
    project_root = Path(args.project_root).resolve()
    service_container = project_root / "app/core/service_container.py"
    config = project_root / "app/core/config.py"
    if not service_container.exists() or not config.exists():
        print("[ERROR] Invalid OSINTXZ project root.", file=sys.stderr); return 2
    if "courtlistener_api_token:" not in config.read_text(encoding="utf-8"):
        print("[ERROR] R10 CourtListener setting not found; install R10 first.", file=sys.stderr); return 3
    copy_files(patch_root, project_root)
    patch_service_container(service_container)
    print("[OK] R11 RECAP archive provider installed.")
    print("[INFO] Paid PACER fetching remains hard-blocked; this patch cannot create PACER charges.")
    if args.run_tests:
        cmd = [sys.executable, "-m", "pytest", "tests/test_registry_recap_pacer.py", "-q"]
        print("[RUN]", " ".join(cmd))
        return subprocess.run(cmd, cwd=project_root, check=False).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

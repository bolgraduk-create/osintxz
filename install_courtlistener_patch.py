from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

NEW_FILES = (
    "app/infrastructure/registries/courtlistener_client.py",
    "app/registry_intelligence/providers/courtlistener.py",
    "tests/test_registry_courtlistener.py",
)

CLIENT_IMPORT = (
    "from app.infrastructure.registries.courtlistener_client import "
    "CourtListenerHttpClient\n"
)
CLIENT_ANCHOR = (
    "from app.infrastructure.registries.registry_api_client import "
    "RegistryApiHttpClient\n"
)
PROVIDER_IMPORT = (
    "from app.registry_intelligence.providers.courtlistener import "
    "CourtListenerRegistryProvider\n"
)
PROVIDER_ANCHOR = (
    "from app.registry_intelligence.providers.remote import "
    "RemoteRegistryProvider\n"
)
REGISTRY_ANCHOR = (
    "        # Large national datasets are never synchronized by end-user desktops.\n"
)
REGISTRATION = '''        # R10 — CourtListener US case law (API v4, token-gated).\n        courtlistener_token = (\n            settings.courtlistener_api_token.get_secret_value()\n            if settings.courtlistener_api_token is not None\n            else None\n        )\n        self.courtlistener_http_client = CourtListenerHttpClient(\n            api_token=courtlistener_token\n        )\n        self.courtlistener_registry_provider = CourtListenerRegistryProvider(\n            client=self.courtlistener_http_client\n        )\n        self.registry_provider_registry.register(\n            self.courtlistener_registry_provider\n        )\n\n'''


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_name(f"{path.name}.before_courtlistener_{stamp}.bak")
    shutil.copy2(path, target)
    return target


def _before(text: str, anchor: str, addition: str, marker: str) -> str:
    if marker in text:
        return text
    if text.count(anchor) != 1:
        raise RuntimeError("Patch anchor mismatch; aborting instead of guessing.")
    return text.replace(anchor, addition + anchor, 1)


def _after(text: str, anchor: str, addition: str, marker: str) -> str:
    if marker in text:
        return text
    if text.count(anchor) != 1:
        raise RuntimeError("Patch anchor mismatch; aborting instead of guessing.")
    return text.replace(anchor, anchor + addition, 1)


def patch_service_container(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = _before(original, CLIENT_ANCHOR, CLIENT_IMPORT, CLIENT_IMPORT)
    updated = _before(updated, PROVIDER_ANCHOR, PROVIDER_IMPORT, PROVIDER_IMPORT)
    updated = _before(
        updated,
        REGISTRY_ANCHOR,
        REGISTRATION,
        "self.courtlistener_registry_provider = CourtListenerRegistryProvider(",
    )
    if updated != original:
        backup = _backup(path)
        path.write_text(updated, encoding="utf-8")
        print(f"[OK] Patched {path}")
        print(f"[OK] Backup: {backup}")
    else:
        print(f"[OK] {path} already contains CourtListener patch")


def patch_config(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if "courtlistener_api_token:" in original:
        print(f"[OK] {path} already contains CourtListener setting")
        return

    if "    opencorporates_api_token: SecretStr | None = None\n" in original:
        updated = _after(
            original,
            "    opencorporates_api_token: SecretStr | None = None\n",
            "\n    # Optional token for CourtListener API v4 automatic access.\n"
            "    courtlistener_api_token: SecretStr | None = None\n",
            "courtlistener_api_token:",
        )
    else:
        anchor = "    registry_backend_port: int = 8011\n"
        addition = '''\n    # ======================================================\n    # External Registry Credentials\n    # ======================================================\n\n    # Optional token for CourtListener API v4 automatic access.\n    courtlistener_api_token: SecretStr | None = None\n'''
        updated = _after(
            original, anchor, addition, "courtlistener_api_token:"
        )

    backup = _backup(path)
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}")
    print(f"[OK] Backup: {backup}")


def patch_env(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if "COURTLISTENER_API_TOKEN=" in original:
        print(f"[OK] {path} already contains CourtListener example")
        return
    if "OPENCORPORATES_API_TOKEN=\n" in original:
        updated = _after(
            original,
            "OPENCORPORATES_API_TOKEN=\n",
            "\n# CourtListener API v4 token. Leave empty to keep automatic execution blocked.\n"
            "COURTLISTENER_API_TOKEN=\n",
            "COURTLISTENER_API_TOKEN=",
        )
    else:
        anchor = "# ==========================================\n# PostgreSQL\n# ==========================================\n"
        addition = '''# ==========================================\n# External Registry Credentials (optional)\n# ==========================================\n\n# CourtListener API v4 token. Leave empty to keep automatic execution blocked.\nCOURTLISTENER_API_TOKEN=\n\n\n'''
        updated = _before(
            original, anchor, addition, "COURTLISTENER_API_TOKEN="
        )
    backup = _backup(path)
    path.write_text(updated, encoding="utf-8")
    print(f"[OK] Patched {path}")
    print(f"[OK] Backup: {backup}")


def copy_files(patch_root: Path, project_root: Path) -> None:
    for relative in NEW_FILES:
        src = patch_root / "payload" / relative
        dst = project_root / relative
        if not src.exists():
            raise FileNotFoundError(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"[OK] Installed {relative}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", nargs="?", default=r"C:\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    patch_root = Path(__file__).resolve().parent
    project_root = Path(args.project_root).resolve()
    sc = project_root / "app/core/service_container.py"
    cfg = project_root / "app/core/config.py"
    env = project_root / ".env.example"
    if not all(p.exists() for p in (sc, cfg, env)):
        print("[ERROR] Invalid OSINTXZ project root.", file=sys.stderr)
        return 2
    copy_files(patch_root, project_root)
    patch_config(cfg)
    patch_env(env)
    patch_service_container(sc)
    print("[OK] CourtListener R10 installation complete.")
    print("[INFO] No token was added. Without COURTLISTENER_API_TOKEN the provider is blocked by the existing router policy.")
    if args.run_tests:
        cmd = [sys.executable, "-m", "pytest", "tests/test_registry_courtlistener.py", "-q"]
        print("[RUN]", " ".join(cmd))
        return subprocess.run(cmd, cwd=project_root, check=False).returncode
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

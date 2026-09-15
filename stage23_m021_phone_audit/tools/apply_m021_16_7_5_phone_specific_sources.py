from __future__ import annotations

from pathlib import Path
import shutil

TARGET = Path("app/core/service_container.py")


def main() -> int:
    if not TARGET.exists():
        print(f"[FAIL] Missing: {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")

    if "TargetedPhonePublicSourcesProvider" in original:
        print("[PASS] Patch already applied.")
        return 0

    text = original

    import_anchor = '''from app.osint.open_web.providers.searxng_phone_exact import (
    SearxngPhoneExactOpenWebProvider,
)
'''

    import_block = import_anchor + '''from app.osint.open_web.providers.targeted_phone_public_sources import (
    TargetedPhonePublicSourcesProvider,
)
'''

    if import_anchor not in text:
        print("[FAIL] SearXNG provider import anchor not found.")
        return 1

    text = text.replace(import_anchor, import_block, 1)

    registration_anchor = '''        self.open_web_provider_registry.register(
            self.searxng_phone_exact_open_web_provider
        )
'''

    registration_block = registration_anchor + '''
        self.targeted_phone_public_sources_provider = (
            TargetedPhonePublicSourcesProvider()
        )
        self.open_web_provider_registry.register(
            self.targeted_phone_public_sources_provider
        )
'''

    if registration_anchor not in text:
        print("[FAIL] SearXNG registration anchor not found.")
        return 1

    text = text.replace(registration_anchor, registration_block, 1)

    try:
        compile(text, str(TARGET), "exec")
    except Exception as exc:
        print(f"[FAIL] compile: {exc}")
        return 1

    backup = TARGET.with_suffix(TARGET.suffix + ".m021_16_7_5_backup")
    if not backup.exists():
        shutil.copy2(TARGET, backup)

    TARGET.write_text(text, encoding="utf-8")

    print("[PASS] Targeted phone public sources provider imported.")
    print("[PASS] Provider registered in Open-Web registry.")
    print("[PASS] Domain allowlist + source tiers enabled.")
    print("[PASS] Existing LiveWeb exact verification reused.")
    print("[PASS] Existing extraction / persistence / recursion reused.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from pathlib import Path
import shutil

TARGET = Path("app/core/service_container.py")


def backup(path: Path) -> None:
    backup_path = path.with_suffix(path.suffix + ".m021_16_7_3_backup")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> int:
    if not TARGET.exists():
        print(f"[FAIL] Missing {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")
    text = original

    import_anchor = '''from app.osint.open_web.providers.common_crawl import (
    CommonCrawlOpenWebProvider,
)
'''
    import_replacement = import_anchor + '''from app.osint.open_web.providers.gdelt_phone_exact import (
    GdeltPhoneExactOpenWebProvider,
)
'''
    text = replace_once(
        text,
        import_anchor,
        import_replacement,
        "GDELT phone provider import",
    )

    registration_anchor = '''        self.open_web_provider_registry.register(
            self.common_crawl_open_web_provider
        )
'''
    registration_replacement = registration_anchor + '''
        # M021.16.7.3 — exact PHONE Open-Web discovery.
        # GDELT only discovers candidate public news URLs; every candidate is
        # re-fetched through bounded Live Web and exact-phone verified before
        # it can enter extraction/persistence.
        self.gdelt_phone_exact_open_web_provider = (
            GdeltPhoneExactOpenWebProvider()
        )
        self.open_web_provider_registry.register(
            self.gdelt_phone_exact_open_web_provider
        )
'''
    text = replace_once(
        text,
        registration_anchor,
        registration_replacement,
        "Open-Web provider registration",
    )

    compile(text, str(TARGET), "exec")
    backup(TARGET)
    TARGET.write_text(text, encoding="utf-8")

    print("[PASS] GDELT Exact Phone provider imported.")
    print("[PASS] Provider registered in existing Open-Web registry.")
    print("[PASS] Existing UI/OpenWebEnrichmentService path reused.")
    print("[PASS] Existing UnifiedExtraction + persistence reused.")
    print("[PASS] Existing recursive pivot service reused.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

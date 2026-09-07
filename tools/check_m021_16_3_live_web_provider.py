from pathlib import Path


def main() -> int:
    provider = Path(
        "app/osint/open_web/providers/live_web.py"
    ).read_text(encoding="utf-8")
    container = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")
    enrichment = Path(
        "app/application/open_web_enrichment_service.py"
    ).read_text(encoding="utf-8")

    checks = [
        ("Live Web provider exists", "class LiveWebOpenWebProvider" in provider),
        ("URL-only provider", "OsintTargetType.URL" in provider),
        ("private network guard", "not ip.is_global" in provider),
        ("redirect validation", "self._validate_public_url(final_url)" in provider),
        ("bounded response", "max_response_bytes" in provider),
        ("no JS execution", '"javascript_executed": False' in provider),
        ("provider registered", "self.live_web_open_web_provider" in container),
        ("provider-aware hydration", "prehydrated_documents" in enrichment),
        ("Common Crawl hydration retained", '== "common_crawl"' in enrichment),
    ]

    print("=" * 72)
    print("M021.16.3 LIVE WEB PROVIDER AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

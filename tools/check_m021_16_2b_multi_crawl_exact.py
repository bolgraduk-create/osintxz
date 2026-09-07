from pathlib import Path


def main() -> int:
    http=Path("app/infrastructure/open_web/common_crawl_client.py").read_text(encoding="utf-8")
    meta=Path("app/infrastructure/open_web/common_crawl_metadata_client.py").read_text(encoding="utf-8")
    provider=Path("app/osint/open_web/providers/common_crawl.py").read_text(encoding="utf-8")

    checks=[
        ("HTTP recent indexes exists","def recent_indexes(" in http),
        ("HTTP recent indexes bounded","min(int(limit),8)" in http),
        ("metadata recent indexes exists","def recent_indexes(" in meta),
        ("provider asks max four crawls","recent_indexes(\n                limit=4" in provider),
        ("multi-crawl strategy metadata",'"bounded_exact_variants_multi_crawl"' in provider),
        ("provider does not add wildcard",'"broad_domain_query":False' in provider),
        ("exact HTTP query retained",'"matchType":"exact"' in http),
    ]

    print("="*72)
    print("M021.16.2B MULTI-CRAWL EXACT AUDIT")
    print("="*72)
    failed=False
    for label,ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok
    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__=="__main__":
    raise SystemExit(main())

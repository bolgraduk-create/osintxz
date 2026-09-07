from pathlib import Path


def main() -> int:
    worker = Path(
        "app/interface/desktop/workers/investigation_search_worker.py"
    ).read_text(encoding="utf-8")
    view = Path(
        "app/interface/desktop/views/workspace/investigation_search_view.py"
    ).read_text(encoding="utf-8")

    checks = [
        ("EMAIL OSINT route", "target_type is OsintTargetType.EMAIL" in worker),
        ("existing enrichment service", "osint_enrichment_service.enrich_target" in worker),
        ("Open-Web preserved", "open_web_enrichment_service.enrich" in worker),
        ("OSINT UI branch", 'payload.get("osint")' in view),
        ("connector statuses", "def _fill_osint_sources(" in view),
        ("errors visible", "connector_result.error" in view),
    ]

    print("=" * 72)
    print("M021.16.4 EMAIL INVESTIGATION SEARCH AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

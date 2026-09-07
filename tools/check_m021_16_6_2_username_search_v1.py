from pathlib import Path

def main() -> int:
    worker = Path(
        "app/interface/desktop/workers/investigation_search_worker.py"
    ).read_text(encoding="utf-8")
    view = Path(
        "app/interface/desktop/views/workspace/investigation_search_view.py"
    ).read_text(encoding="utf-8")

    checks = [
        ("USERNAME route", "M021.16.6.2 USERNAME OSINT routing" in worker),
        ("existing enrichment service", "osint_enrichment_service.enrich_target" in worker),
        ("email Open-Web isolated", "email_open_web_result = None" in worker),
        ("generic OSINT status", "M021.16.6.2 generic OSINT result status" in view),
    ]

    print("=" * 72)
    print("M021.16.6.2 USERNAME SEARCH V1 AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())

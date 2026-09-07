from pathlib import Path

SERVICE = Path("app/osint/open_web/service.py")
VIEW = Path(
    "app/interface/desktop/views/workspace/"
    "investigation_search_view.py"
)


def main() -> int:
    service = SERVICE.read_text(encoding="utf-8")
    view = VIEW.read_text(encoding="utf-8")

    checks = [
        (
            "429 handling marker",
            "M021.16.7.10 RATE LIMIT IS NOT PROVIDER FAILURE"
            in service,
        ),
        (
            "429 mapped to PARTIAL",
            "status=OpenWebStatus.PARTIAL" in service
            and '"rate_limited": True' in service
            and '"retryable": True' in service,
        ),
        (
            "old email-only UI label removed",
            '"exact_email_public_web"' not in view,
        ),
        (
            "generic Open-Web UI goal present",
            '"open_web_discovery"' in view,
        ),
    ]

    print("=" * 84)
    print("M021.16.7.10 OPEN-WEB STATUS + UI AUDIT")
    print("=" * 84)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print()
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

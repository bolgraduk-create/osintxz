from pathlib import Path


def main() -> int:
    provider = Path(
        "app/osint/open_web/providers/gdelt_exact_email.py"
    ).read_text(encoding="utf-8")

    container = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    worker = Path(
        "app/interface/desktop/workers/investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    checks = [
        (
            "EMAIL-only GDELT provider",
            "OsintTargetType.EMAIL" in provider,
        ),
        (
            "GDELT DOC API endpoint",
            "api.gdeltproject.org/api/v2/doc/doc" in provider,
        ),
        (
            "exact phrase query",
            '''"query": f'"{email}"',''' in provider,
        ),
        (
            "live verification reused",
            "self.live_web_provider.search" in provider,
        ),
        (
            "exact email verification",
            "_contains_exact_email" in provider,
        ),
        (
            "provider registered",
            "gdelt_exact_email_open_web_provider" in container,
        ),
        (
            "EMAIL runs Open-Web",
            "email_open_web_result" in worker,
        ),
    ]

    print("=" * 72)
    print("M021.16.5.2A GDELT EXACT EMAIL AUDIT")
    print("=" * 72)

    failed = False

    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

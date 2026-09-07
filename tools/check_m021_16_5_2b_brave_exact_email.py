from pathlib import Path


def main() -> int:
    config = Path(
        "app/core/config.py"
    ).read_text(encoding="utf-8")

    provider = Path(
        "app/osint/open_web/providers/brave_exact_email.py"
    ).read_text(encoding="utf-8")

    registry = Path(
        "app/osint/open_web/registry.py"
    ).read_text(encoding="utf-8")

    container = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    checks = [
        (
            "Brave key uses SecretStr",
            "brave_search_api_key: SecretStr | None = None"
            in config,
        ),
        (
            "official Brave endpoint",
            "api.search.brave.com/res/v1/web/search"
            in provider,
        ),
        (
            "X-Subscription-Token",
            "X-Subscription-Token" in provider,
        ),
        (
            "exact phrase search",
            '"q": f\'"{email}"\',' in provider,
        ),
        (
            "live verification",
            "self.live_web_provider.search" in provider,
        ),
        (
            "exact email gate",
            "_contains_exact_email" in provider,
        ),
        (
            "credential-aware registry",
            "M021.16.5.2B credential-aware"
            in registry,
        ),
        (
            "runtime registration",
            "brave_exact_email_open_web_provider"
            in container,
        ),
    ]

    print("=" * 72)
    print("M021.16.5.2B BRAVE EXACT EMAIL AUDIT")
    print("=" * 72)

    failed = False

    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

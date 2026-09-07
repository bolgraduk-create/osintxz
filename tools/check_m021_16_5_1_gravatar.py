from pathlib import Path


def main() -> int:
    connector = Path(
        "app/osint/connectors/gravatar_connector.py"
    ).read_text(encoding="utf-8")
    capabilities = Path(
        "app/osint/capabilities.py"
    ).read_text(encoding="utf-8")
    policy = Path(
        "app/osint/pivot_policy.py"
    ).read_text(encoding="utf-8")
    container = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    checks = [
        ("Gravatar connector exists", "class GravatarConnector" in connector),
        (
            "SHA256 normalization exists",
            "hashlib.sha256" in connector and ".casefold()" in connector,
        ),
        (
            "official v3 endpoint",
            "https://api.gravatar.com/v3" in connector,
        ),
        (
            "404 clean zero-result handling",
            "response.status_code == 404" in connector,
        ),
        (
            "verified account handling",
            "verified_accounts" in connector,
        ),
        (
            "new capability goal",
            "EMAIL_PROFILE_ENRICHMENT" in capabilities,
        ),
        (
            "Gravatar capability catalog entry",
            '"gravatar_connector"' in capabilities,
        ),
        (
            "EMAIL default goal added",
            "DiscoveryGoal.EMAIL_PROFILE_ENRICHMENT" in policy,
        ),
        (
            "runtime registration",
            "M021.16.5.1 Gravatar runtime registration" in container,
        ),
    ]

    print("=" * 72)
    print("M021.16.5.1 GRAVATAR EMAIL PROFILE AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

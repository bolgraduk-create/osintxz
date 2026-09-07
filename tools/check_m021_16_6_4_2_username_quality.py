from pathlib import Path


def main() -> int:
    quality = Path("app/osint/username_quality.py").read_text(encoding="utf-8")
    persistence = Path("app/osint/finding_persistence.py").read_text(encoding="utf-8")

    checks = [
        ("classifier", "class UsernameFindingQuality" in quality),
        ("service endpoint kind", "SERVICE_ENDPOINT" in quality),
        ("public profile kind", "PUBLIC_PROFILE" in quality),
        ("canonicalization", "canonicalize_url" in quality),
        ("persistence gate", "M021.16.6.4.2 username quality gate" in persistence),
        ("ACCOUNT suppression", "if entity_type is EntityType.ACCOUNT" in persistence),
        ("USERNAME scoped", "target_type is OsintTargetType.USERNAME" in persistence),
        ("ACCOUNT_DISCOVERY scoped", "goal is DiscoveryGoal.ACCOUNT_DISCOVERY" in persistence),
    ]

    print("=" * 72)
    print("M021.16.6.4.2 USERNAME QUALITY AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

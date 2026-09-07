from pathlib import Path


def main() -> int:
    connector = Path(
        "app/osint/connectors/user_scanner_connector.py"
    ).read_text(encoding="utf-8")

    capabilities = Path(
        "app/osint/capabilities.py"
    ).read_text(encoding="utf-8")

    checks = [
        ("USERNAME supported", "OsintTargetType.USERNAME" in connector),
        ("username flag", '"-u"' in connector),
        ("UTF-8 preserved", '"-X"' in connector and '"utf8"' in connector),
        ("ACCOUNT_DISCOVERY added", "DiscoveryGoal.ACCOUNT_DISCOVERY" in capabilities),
        (
            "both target types in catalog",
            "(OsintTargetType.EMAIL, OsintTargetType.USERNAME)" in capabilities,
        ),
        ("no loud execution", '"--allow-loud",' not in connector),
        ("no Hudson execution", '"--hudson",' not in connector),
    ]

    print("=" * 72)
    print("M021.16.6.3 USER SCANNER USERNAME AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

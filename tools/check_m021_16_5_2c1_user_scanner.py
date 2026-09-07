from pathlib import Path


def main() -> int:
    connector = Path(
        "app/osint/connectors/user_scanner_connector.py"
    ).read_text(encoding="utf-8")

    capabilities = Path(
        "app/osint/capabilities.py"
    ).read_text(encoding="utf-8")

    container = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    checks = [
        ("User Scanner connector", "class UserScannerConnector" in connector),
        ("EMAIL only", "OsintTargetType.EMAIL" in connector),
        ("JSON output", '"json"' in connector),
        ("NSFW disabled", '"--no-nsfw"' in connector),
        ("loud mode not executed", '"--allow-loud",' not in connector),
        ("Hudson not executed", '"--hudson",' not in connector),
        ("registered-result filter", "_is_registered" in connector),
        ("capability registered", '"user_scanner_connector"' in capabilities),
        ("runtime registered", "UserScannerConnector()" in container),
    ]

    print("=" * 72)
    print("M021.16.5.2C1 USER SCANNER AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

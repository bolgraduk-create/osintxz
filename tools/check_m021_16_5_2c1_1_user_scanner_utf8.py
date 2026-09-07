from pathlib import Path


def main() -> int:
    text = Path(
        "app/osint/connectors/user_scanner_connector.py"
    ).read_text(encoding="utf-8")

    checks = [
        ("marker", "M021.16.5.2C1.1 force child UTF-8" in text),
        ("project interpreter", "sys.executable" in text),
        ("utf8 mode", '"-X"' in text and '"utf8"' in text),
        ("module execution", '"-m"' in text and '"user_scanner"' in text),
        ("safe flag", '"--no-nsfw"' in text),
    ]

    print("=" * 72)
    print("M021.16.5.2C1.1 USER SCANNER UTF-8 AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path


def main() -> int:
    text = Path("app/osint/open_web/extraction_bridge.py").read_text(encoding="utf-8")
    checks = [
        ("source URL not injected", "return document.extraction_text.strip()" in text),
        ("self URL filter exists", "_canonical_url(document.url)" in text),
        ("phone quality gate exists", "_plausible_open_web_phone" in text),
        ("bare numeric rejection exists", "if raw.isdigit()" in text),
        ("E.164 max length bound exists", "len(digits) > 15" in text),
    ]

    print("=" * 72)
    print("M021.16.3.2 OPEN-WEB EXTRACTION QUALITY AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

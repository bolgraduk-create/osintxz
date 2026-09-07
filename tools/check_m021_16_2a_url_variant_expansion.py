from pathlib import Path


def main() -> int:
    path = Path("app/osint/open_web/providers/common_crawl.py")
    text = path.read_text(encoding="utf-8")

    checks = [
        ("URL variant helper exists", "_url_variants(value: str)" in text),
        ("bounded to eight probes", "return variants[:8]" in text),
        ("http/https variant logic", '"http" if scheme == "https" else "https"' in text),
        ("www/non-www logic", 'host.startswith("www.")' in text),
        ("slash variant logic", 'path.endswith("/")' in text),
    ]

    print("=" * 72)
    print("M021.16.2A URL VARIANT EXPANSION AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

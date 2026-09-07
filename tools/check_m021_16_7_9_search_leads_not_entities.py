from __future__ import annotations

from pathlib import Path


TARGET = Path("app/osint/finding_persistence.py")


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    compact = "".join(text.split())

    checks = [
        (
            "search_query entity guard present",
            'ifurlandcategory!="search_query":'
            in compact,
        ),
        (
            "URL entity mapping retained",
            '"url":EntityType.URL'
            in compact,
        ),
        (
            "public_url entity mapping retained",
            '"public_url":EntityType.URL'
            in compact,
        ),
        (
            "link entity mapping retained",
            '"link":EntityType.URL'
            in compact,
        ),
        (
            "search_query is not category-mapped to URL",
            '"search_query":EntityType.URL'
            not in compact,
        ),
    ]

    print("=" * 84)
    print("M021.16.7.9 SEARCH LEADS != ENTITIES AUDIT")
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

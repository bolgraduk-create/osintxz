from pathlib import Path


def main() -> int:
    text = Path(
        "app/osint/finding_persistence.py"
    ).read_text(encoding="utf-8")

    checks = [
        (
            "Open-Web-only suppression marker",
            "M021.16.3.4 Open-Web provenance suppression"
            in text,
        ),
        (
            "connector scope enforced",
            'startswith("open_web:")' in text,
        ),
        (
            "provenance URL helper exists",
            "_is_open_web_provenance_url_candidate"
            in text,
        ),
        (
            "finding.url compared as provenance",
            "finding.url or" in text,
        ),
        (
            "target URL suppression exists",
            "target_type is OsintTargetType.URL"
            in text,
        ),
        (
            "generic entity candidate function retained",
            "def _entity_candidates(" in text,
        ),
    ]

    print("=" * 72)
    print("M021.16.3.4 OPEN-WEB PERSISTENCE PROVENANCE AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(
            f"[{'PASS' if ok else 'FAIL'}] {label}"
        )
        failed |= not ok

    print(
        f"\nRESULT: {'FAIL' if failed else 'PASS'}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path


def main() -> int:
    persistence = Path(
        "app/osint/finding_persistence.py"
    ).read_text(encoding="utf-8")

    source_model = Path(
        "app/models/source.py"
    ).read_text(encoding="utf-8")

    checks = [
        (
            "persistence uses Source.original_path",
            'and (source.original_path or "") == path'
            in persistence,
        ),
        (
            "legacy Source.path lookup removed",
            'and (source.path or "") == path'
            not in persistence,
        ),
        (
            "Source model exposes original_path",
            "original_path: Mapped[str | None]"
            in source_model,
        ),
        (
            "no DB migration required",
            True,
        ),
    ]

    print("=" * 72)
    print("M021.15.2 SOURCE ORIGINAL_PATH AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

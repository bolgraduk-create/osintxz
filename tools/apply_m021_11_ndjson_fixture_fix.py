from pathlib import Path

PATH = Path(
    "tests/test_common_crawl_open_web_provider.py"
)


def main() -> int:
    if not PATH.is_file():
        print(f"[FAIL] Missing {PATH}")
        return 1

    original = PATH.read_text(
        encoding="utf-8"
    )

    old = (
        'text=json.dumps(rec("https://example.org/a")) '
        '+ "\\\\\\\\n")'
    )

    new = (
        'text=json.dumps(rec("https://example.org/a")) '
        '+ "\\\\n")'
    )

    if old not in original:
        if new in original:
            print(
                "[PASS] M021.11 NDJSON fixture "
                "is already fixed."
            )
            return 0

        print(
            "[FAIL] Expected NDJSON fixture "
            "line was not found."
        )
        return 1

    updated = original.replace(
        old,
        new,
        1,
    )

    compile(
        updated,
        str(PATH),
        "exec",
    )

    backup = PATH.with_suffix(
        ".py.m021_11_ndjson_backup"
    )

    if not backup.exists():
        backup.write_text(
            original,
            encoding="utf-8",
        )

    PATH.write_text(
        updated,
        encoding="utf-8",
    )

    print(
        "[PASS] M021.11 NDJSON test fixture fixed."
    )
    print(
        "[INFO] Production code unchanged."
    )
    print(
        f"[INFO] Backup: {backup}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path
import re

PATH = Path("tests/test_common_crawl_open_web_provider.py")


def main() -> int:
    if not PATH.is_file():
        print(f"[FAIL] Missing {PATH}")
        return 1

    original = PATH.read_text(encoding="utf-8")

    # Source currently contains:
    # json.dumps(...) + "\\n"
    # which produces literal backslash+n at runtime.
    pattern = re.compile(
        r'(json\.dumps\(rec\("https://example\.org/a"\)\)\s*\+\s*)'
        r'"\\\\n"'
    )

    updated, count = pattern.subn(
        r'\1"\\n"',
        original,
        count=1,
    )

    if count == 0:
        # Accept already-fixed source.
        if (
            'json.dumps(rec("https://example.org/a")) + "\\n"'
            in original
        ):
            print("[PASS] Fixture already contains a real newline escape.")
            return 0

        print("[FAIL] Target NDJSON fixture literal was not found.")
        print("[INFO] Production code was not modified.")
        return 1

    compile(updated, str(PATH), "exec")

    backup = PATH.with_suffix(
        ".py.m021_11_ndjson_v2_backup"
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

    reread = PATH.read_text(
        encoding="utf-8",
    )

    bad_literal = (
        'json.dumps(rec("https://example.org/a")) + "\\\\n"'
    )
    good_literal = (
        'json.dumps(rec("https://example.org/a")) + "\\n"'
    )

    if bad_literal in reread:
        print("[FAIL] Literal \\\\n is still present after write.")
        return 1

    if good_literal not in reread:
        print("[FAIL] Expected fixed newline escape was not found.")
        return 1

    print("[PASS] M021.11 NDJSON fixture fixed.")
    print("[PASS] Literal \\\\n removed.")
    print("[PASS] Real newline escape \\n installed.")
    print("[INFO] Production CommonCrawl client/provider unchanged.")
    print(f"[INFO] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

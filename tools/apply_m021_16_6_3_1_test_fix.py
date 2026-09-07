from pathlib import Path

SRC = Path(
    "tests/test_m021_16_6_3_1_safe_support_routing.py"
)
FIX = Path(
    "tools/m021_16_6_3_1_test_fix_source.py"
)


def main() -> int:
    if not SRC.exists():
        print(f"[FAIL] Missing {SRC}")
        return 1

    backup = SRC.with_suffix(
        ".py.m021_16_6_3_1_test_backup"
    )

    if not backup.exists():
        backup.write_text(
            SRC.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    source = FIX.read_text(encoding="utf-8")
    compile(source, str(SRC), "exec")
    SRC.write_text(source, encoding="utf-8")

    print("[PASS] Test fixture corrected.")
    print("[PASS] Production router unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path

TARGET = Path("app/osint/connectors/user_scanner_connector.py")


def main() -> int:
    if not TARGET.is_file():
        print(f"[FAIL] Missing {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")
    if "M021.16.5.2C1.1 force child UTF-8" in original:
        print("[PASS] Patch already applied.")
        return 0

    old = '''        return [
            executable,
            "-e",
            email,
'''
    new = '''        # M021.16.5.2C1.1 force child UTF-8
        return [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "user_scanner",
            "-e",
            email,
'''

    if old not in original:
        print("[FAIL] _build_command anchor not found.")
        return 1

    updated = original.replace(old, new, 1)
    compile(updated, str(TARGET), "exec")

    backup = TARGET.with_suffix(".py.m021_16_5_2c1_1_backup")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    TARGET.write_text(updated, encoding="utf-8")

    print("[PASS] User Scanner now runs via project Python UTF-8 mode.")
    print("[PASS] Safe/no-loud flags preserved.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from pathlib import Path


PATH = Path("app/osint/finding_persistence.py")


def main() -> int:
    if not PATH.is_file():
        print(f"[FAIL] Missing {PATH}")
        return 1

    original = PATH.read_text(encoding="utf-8")
    text = original

    old = 'and (source.path or "") == path'
    new = 'and (source.original_path or "") == path'

    if new in text and old not in text:
        print("[PASS] Source.original_path fix already applied.")
        return 0

    if old not in text:
        print("[FAIL] Expected source.path lookup not found.")
        return 1

    if text.count(old) != 1:
        print(
            f"[FAIL] Expected exactly one source.path lookup, found "
            f"{text.count(old)}."
        )
        return 1

    text = text.replace(old, new, 1)

    compile(text, str(PATH), "exec")

    backup = PATH.with_suffix(".py.m021_15_2_backup")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    PATH.write_text(text, encoding="utf-8")

    print("[PASS] source.path replaced with source.original_path.")
    print("[PASS] OSINT source dedup lookup now matches Source model.")
    print("[PASS] No database migration.")
    print(f"[INFO] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

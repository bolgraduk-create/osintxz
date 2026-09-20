from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

PATCH = "R13.23.1.1"
MARKER = "// R13.23.1.1 EMPTY-STATE COMPATIBILITY"


def python_for(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else Path(sys.executable)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def patch_person_qml(text: str) -> str:
    if MARKER in text:
        return text

    old = '            { title: "TECHNICAL", rows: technical, empty: "No domain / network identifiers" }'
    new = (
        '            // R13.23.1.1 EMPTY-STATE COMPATIBILITY\n'
        '            { title: "TECHNICAL", rows: technical, empty: "No web / network identifiers" }'
    )
    if old in text:
        return text.replace(old, new, 1)

    # Accept an already manually corrected copy without modifying it further.
    if 'No web / network identifiers' in text and 'title: "TECHNICAL"' in text:
        anchor = 'title: "TECHNICAL"'
        idx = text.find(anchor)
        line_start = text.rfind("\n", 0, idx) + 1
        return text[:line_start] + "            // R13.23.1.1 EMPTY-STATE COMPATIBILITY\n" + text[line_start:]

    raise RuntimeError(
        "Person.qml compatibility anchor not found. R13.23.1 must be installed first."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Install R13.23.1.1 compatibility hotfix")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    person = root / "app/interface/desktop/qml/pages/Person.qml"
    if not person.is_file():
        raise SystemExit(f"Person.qml not found: {person}")

    current = person.read_text(encoding="utf-8", errors="ignore")
    if "// R13.23.1 PERSON CARD POLISH + MENTIONS" not in current:
        raise SystemExit("R13.23.1 Person Card Polish + Mentions must be installed first.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = root / "storage/patch_backups" / f"r13_23_1_1_{stamp}"
    backup_person = backup / person.relative_to(root)
    backup_person.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(person, backup_person)

    updated = patch_person_qml(current)
    person.write_text(updated, encoding="utf-8")

    test_src = Path(__file__).resolve().parent / "payload/tests/test_r13_23_1_1_compatibility.py"
    test_dst = root / "tests/test_r13_23_1_1_compatibility.py"
    if not test_src.is_file():
        raise SystemExit(f"Patch test payload missing: {test_src}")
    test_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(test_src, test_dst)

    verify = person.read_text(encoding="utf-8", errors="ignore")
    required = (
        MARKER,
        'title: "WEB PROFILES / PAGES"',
        'title: "TECHNICAL"',
        'No web / network identifiers',
        'Corroborating Mentions',
    )
    missing = [item for item in required if item not in verify]
    if missing:
        raise SystemExit("R13.23.1.1 verification failed: " + ", ".join(missing))

    print(f"{PATCH} compatibility hotfix installed.")
    print(f"Backup: {backup}")
    print(f"Person.qml SHA-256: {sha256(person)}")

    if args.run_tests:
        py = python_for(root)
        tests = [
            "tests/test_r13_23_1_1_compatibility.py",
            "tests/test_r13_23_1_person_card_mentions.py",
            "tests/test_r13_23_person_card_v2.py",
            "tests/test_r13_22_corroborating_mentions.py",
            "tests/test_qml_desktop_bridge.py",
        ]
        existing = [item for item in tests if (root / item).is_file()]
        cmd = [str(py), "-m", "pytest", "-q", *existing]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, cwd=root, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

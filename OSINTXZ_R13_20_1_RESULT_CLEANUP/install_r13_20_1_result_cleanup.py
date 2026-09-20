from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

PATCH = "R13.20.1"
FILES = (
    "app/application/investigation_result_consolidation.py",
    "app/interface/desktop/workers/unified_investigation_search_worker.py",
    "app/interface/desktop/qml/pages/Search.qml",
    "tests/test_r13_20_1_result_cleanup.py",
)
REQUIRED_BASELINE = (
    "app/application/unified_investigation_search.py",
    "app/interface/desktop/workers/unified_investigation_search_worker.py",
    "app/interface/desktop/qml/pages/Search.qml",
)


def python_for(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else Path(sys.executable)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.20.1 result cleanup hotfix")
    parser.add_argument("root", help="OSINTXZ project root, e.g. C:\\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    payload = Path(__file__).resolve().parent / "payload"
    if not (root / "app").is_dir():
        raise SystemExit(f"Invalid OSINTXZ root: {root}")
    missing = [path for path in REQUIRED_BASELINE if not (root / path).is_file()]
    if missing:
        raise SystemExit(
            "R13.20 baseline is required before R13.20.1. Missing: " + ", ".join(missing)
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = root / "storage" / "patch_backups" / f"r13_20_1_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)

    for relative in FILES:
        src = payload / relative
        if not src.is_file():
            raise SystemExit(f"Patch payload missing: {src}")
        dst = root / relative
        if dst.exists():
            backup_dst = backup / relative
            backup_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, backup_dst)

    for relative in FILES:
        src = payload / relative
        dst = root / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    py = python_for(root)
    compile_targets = [
        str(root / "app/application/investigation_result_consolidation.py"),
        str(root / "app/interface/desktop/workers/unified_investigation_search_worker.py"),
    ]
    subprocess.run([str(py), "-m", "py_compile", *compile_targets], cwd=root, check=True)

    print(f"{PATCH} installed. Backup: {backup}")

    if args.run_tests:
        tests = [
            "tests/test_r13_20_1_result_cleanup.py",
            "tests/test_r13_20_unified_investigation_search.py",
            "tests/test_m021_qml_recursive_collection.py",
            "tests/test_qml_desktop_bridge.py",
        ]
        existing = [item for item in tests if (root / item).is_file()]
        cmd = [str(py), "-m", "pytest", "-q", *existing]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, cwd=root, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

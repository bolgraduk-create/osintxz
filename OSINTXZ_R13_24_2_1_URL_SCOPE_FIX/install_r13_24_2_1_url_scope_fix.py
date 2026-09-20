from __future__ import annotations
import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

PATCH = "R13.24.2.1"
COPY_FILES = (
    "app/application/adaptive_relevance.py",
    "tests/test_r13_24_2_1_url_scope_fix.py",
    "tests/test_r13_24_2_balanced_relevance.py",
)


def project_python(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else Path(sys.executable)


def verify_baseline(root: Path) -> None:
    required = (
        "app/application/adaptive_relevance.py",
        "app/application/investigation_result_consolidation.py",
        "tests/test_r13_24_2_balanced_relevance.py",
    )
    missing = [p for p in required if not (root / p).is_file()]
    if missing:
        raise SystemExit("R13.24.2 baseline required. Missing: " + ", ".join(missing))
    text = (root / "app/application/adaptive_relevance.py").read_text(encoding="utf-8", errors="ignore")
    if "_weak_exact_relation" not in text or "No meaningful relation to the searched exact identifier" not in text:
        raise SystemExit("Install R13.24.2 before R13.24.2.1.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.24.2.1 URL Scope Fix")
    parser.add_argument("root")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    payload = Path(__file__).resolve().parent / "payload"
    if not (root / "app").is_dir():
        raise SystemExit(f"Invalid OSINTXZ root: {root}")
    verify_baseline(root)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = root / "storage" / "patch_backups" / f"r13_24_2_1_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)

    for relative in COPY_FILES:
        dst = root / relative
        if dst.exists():
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, saved)
    for relative in COPY_FILES:
        src = payload / relative
        if not src.is_file():
            raise SystemExit(f"Patch payload missing: {src}")
        dst = root / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    py = project_python(root)
    subprocess.run([str(py), "-m", "py_compile", str(root / "app/application/adaptive_relevance.py")], cwd=root, check=True)

    text = (root / "app/application/adaptive_relevance.py").read_text(encoding="utf-8", errors="ignore")
    for marker in ("_same_url_scope", "Returned URL stays inside the searched URL scope"):
        if marker not in text:
            raise SystemExit(f"{PATCH} verification failed: missing {marker}")

    print(f"{PATCH} URL Scope Fix installed.")
    print(f"Backup: {backup}")
    print(f"Python: {py}")

    if args.run_tests:
        tests = [
            "tests/test_r13_24_2_1_url_scope_fix.py",
            "tests/test_r13_24_2_balanced_relevance.py",
            "tests/test_r13_24_1_username_recovery.py",
            "tests/test_r13_24_adaptive_relevance_connector_health.py",
            "tests/test_r13_23_1_person_card_mentions.py",
            "tests/test_r13_23_person_card_v2.py",
            "tests/test_r13_22_corroborating_mentions.py",
            "tests/test_r13_21_4_strict_url_candidate_quality.py",
            "tests/test_r13_21_3_account_identity_url_fix.py",
            "tests/test_r13_21_2_strict_identity_persistence.py",
            "tests/test_r13_21_1_contextual_relevance.py",
            "tests/test_r13_20_2_person_name_relevance.py",
            "tests/test_r13_20_1_result_cleanup.py",
            "tests/test_qml_desktop_bridge.py",
        ]
        existing = [p for p in tests if (root / p).is_file()]
        cmd = [str(py), "-m", "pytest", "-q", *existing]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, cwd=root, check=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

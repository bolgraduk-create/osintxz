from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

PATCH = "R13.24.1"
COPY_FILES = (
    "app/application/contextual_relevance.py",
    "app/interface/desktop/workers/unified_investigation_search_worker.py",
    "app/osint/connectors/sherlock_connector.py",
    "app/osint/connectors/maigret_connector.py",
    "app/osint/connectors/user_scanner_connector.py",
    "tests/test_r13_24_1_username_recovery.py",
)


def project_python(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else Path(sys.executable)


def verify_baseline(root: Path) -> None:
    required = (
        "app/application/adaptive_relevance.py",
        "app/application/connector_health.py",
        "app/application/investigation_result_consolidation.py",
        "app/application/contextual_relevance.py",
        "app/application/unified_persistence_relevance.py",
        "app/interface/desktop/workers/unified_investigation_search_worker.py",
        "app/interface/desktop/qml/pages/Search.qml",
        "app/osint/connectors/sherlock_connector.py",
        "app/osint/connectors/maigret_connector.py",
        "app/osint/connectors/user_scanner_connector.py",
    )
    missing = [path for path in required if not (root / path).is_file()]
    if missing:
        raise SystemExit("R13.24 baseline required. Missing: " + ", ".join(missing))
    qml = (root / "app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8", errors="ignore")
    adaptive = (root / "app/application/adaptive_relevance.py").read_text(encoding="utf-8", errors="ignore")
    if "R13.24 ADAPTIVE RELEVANCE" not in qml or "classify_suppressed_row" not in adaptive:
        raise SystemExit("R13.24 Adaptive Relevance must be installed before R13.24.1.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.24.1 Username Recovery Hotfix")
    parser.add_argument("root")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    payload = Path(__file__).resolve().parent / "payload"
    if not (root / "app").is_dir():
        raise SystemExit(f"Invalid OSINTXZ root: {root}")
    verify_baseline(root)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = root / "storage" / "patch_backups" / f"r13_24_1_{stamp}"
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
    compile_targets = [root / relative for relative in COPY_FILES if relative.endswith(".py") and not relative.startswith("tests/")]
    subprocess.run([str(py), "-m", "py_compile", *map(str, compile_targets)], cwd=root, check=True)

    worker = (root / "app/interface/desktop/workers/unified_investigation_search_worker.py").read_text(encoding="utf-8", errors="ignore")
    sherlock = (root / "app/osint/connectors/sherlock_connector.py").read_text(encoding="utf-8", errors="ignore")
    user_scanner = (root / "app/osint/connectors/user_scanner_connector.py").read_text(encoding="utf-8", errors="ignore")
    maigret = (root / "app/osint/connectors/maigret_connector.py").read_text(encoding="utf-8", errors="ignore")
    checks = (
        ('identifiers["username"] = target', worker),
        ('"findingMetadata": finding_metadata', worker),
        ("USERNAME_CLASSIC_TIMEOUT = 20", worker),
        ('"--local"', sherlock),
        ("partial_stdout_recovery", sherlock),
        ("USERNAME_CATEGORIES", user_scanner),
        ('"-c", category', user_scanner),
        ('"--top-sites", "300"', maigret),
    )
    for marker, content in checks:
        if marker not in content:
            raise SystemExit(f"R13.24.1 install verification failed: missing {marker}")

    print("R13.24.1 Username Recovery Hotfix installed.")
    print(f"Backup: {backup}")
    print(f"Python: {py}")

    if args.run_tests:
        tests = [
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
        existing = [path for path in tests if (root / path).is_file()]
        cmd = [str(py), "-m", "pytest", "-q", *existing]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, cwd=root, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

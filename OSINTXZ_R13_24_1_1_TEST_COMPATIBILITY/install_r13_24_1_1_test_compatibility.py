from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PATCH_NAME = "R13.24.1.1 Maigret regression compatibility fix"
FILES = {
    "tests/test_r13_24_adaptive_relevance_connector_health.py": "payload/tests/test_r13_24_adaptive_relevance_connector_health.py",
    "tests/test_r13_24_1_1_test_compatibility.py": "payload/tests/test_r13_24_1_1_test_compatibility.py",
}

TESTS = [
    "tests/test_r13_24_1_1_test_compatibility.py",
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


def project_python(root: Path) -> Path:
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def main() -> int:
    parser = argparse.ArgumentParser(description=PATCH_NAME)
    parser.add_argument("root", type=Path)
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    package = Path(__file__).resolve().parent

    required = root / "app" / "osint" / "connectors" / "maigret_connector.py"
    old_test = root / "tests" / "test_r13_24_adaptive_relevance_connector_health.py"
    recovery_test = root / "tests" / "test_r13_24_1_username_recovery.py"
    for path in (required, old_test, recovery_test):
        if not path.exists():
            raise SystemExit(f"R13.24.1 baseline is required; missing: {path}")

    maigret = required.read_text(encoding="utf-8")
    if '"--top-sites", "300"' not in maigret:
        raise SystemExit("R13.24.1 baseline not detected: Maigret 300-site fast-pass is missing.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = root / "storage" / "patch_backups" / f"r13_24_1_1_{stamp}"
    backup.mkdir(parents=True, exist_ok=False)

    for rel, payload_rel in FILES.items():
        destination = root / rel
        if destination.exists():
            backup_path = backup / rel
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup_path)
        source = package / payload_rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    print(f"{PATCH_NAME} installed.")
    print(f"Backup: {backup}")

    if args.run_tests:
        py = project_python(root)
        existing = [item for item in TESTS if (root / item).exists()]
        cmd = [str(py), "-m", "pytest", "-q", *existing]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, cwd=root, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

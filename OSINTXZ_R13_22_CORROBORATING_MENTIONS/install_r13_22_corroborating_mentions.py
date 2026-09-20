from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

PATCH = "R13.22"
FILES = (
    "app/application/investigation_result_consolidation.py",
    "app/interface/desktop/workers/unified_investigation_search_worker.py",
    "app/interface/desktop/qml/pages/Search.qml",
    "tests/test_r13_22_corroborating_mentions.py",
)

REQUIRED_BASELINE = (
    "app/application/contextual_relevance.py",
    "app/application/identity_resolution.py",
    "app/application/investigation_result_consolidation.py",
    "app/application/unified_persistence_relevance.py",
    "app/interface/desktop/workers/unified_investigation_search_worker.py",
    "app/interface/desktop/qml/pages/Search.qml",
)


def python_for(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else Path(sys.executable)


def verify_baseline(root: Path) -> None:
    missing = [path for path in REQUIRED_BASELINE if not (root / path).is_file()]
    if missing:
        raise SystemExit(
            "R13.21.4 baseline is required. Missing: " + ", ".join(missing)
        )

    qml = (root / "app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8", errors="ignore"
    )
    consolidation = (
        root / "app/application/investigation_result_consolidation.py"
    ).read_text(encoding="utf-8", errors="ignore")

    markers = (
        ('{ key: "accounts", label: "Accounts" }', qml),
        ("runData.relatedAccounts", qml),
        ("structuredPersonMatch", consolidation),
        ("Identity-review rows live in Identity only", consolidation),
    )
    absent = [marker for marker, content in markers if marker not in content]
    if absent:
        raise SystemExit(
            "R13.22 requires installed R13.21.4. Missing markers: "
            + ", ".join(absent)
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R13.22 Corroborating Mentions"
    )
    parser.add_argument("root", help=r"OSINTXZ project root, e.g. C:\osintxz")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    payload = Path(__file__).resolve().parent / "payload"
    if not (root / "app").is_dir():
        raise SystemExit(f"Invalid OSINTXZ root: {root}")

    verify_baseline(root)

    for relative in FILES:
        src = payload / relative
        if not src.is_file():
            raise SystemExit(f"Patch payload missing: {src}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = root / "storage" / "patch_backups" / f"r13_22_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)

    for relative in FILES:
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
    subprocess.run(
        [str(py), "-m", "py_compile", *compile_targets],
        cwd=root,
        check=True,
    )

    consolidation = (
        root / "app/application/investigation_result_consolidation.py"
    ).read_text(encoding="utf-8", errors="ignore")
    worker = (
        root / "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8", errors="ignore")
    qml = (root / "app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8", errors="ignore"
    )

    markers = (
        ("mention_rows", consolidation),
        ("_is_corroborating_mention", consolidation),
        ("mentionSignals", consolidation),
        ('"mentions": [', worker),
        ('"mentions": len(consolidation.mention_rows or [])', worker),
        ('{ key: "mentions", label: "Mentions" }', qml),
        ("runData.mentions", qml),
        ("CORROBORATING MENTION", qml),
    )
    absent = [marker for marker, content in markers if marker not in content]
    if absent:
        raise SystemExit(
            "R13.22 install verification failed: " + ", ".join(absent)
        )

    print(f"{PATCH} installed. Backup: {backup}")

    if args.run_tests:
        tests = [
            "tests/test_r13_22_corroborating_mentions.py",
            "tests/test_r13_21_4_strict_url_candidate_quality.py",
            "tests/test_r13_21_3_account_identity_url_fix.py",
            "tests/test_r13_21_2_strict_identity_persistence.py",
            "tests/test_r13_21_1_contextual_relevance.py",
            "tests/test_r13_21_identity_resolution.py",
            "tests/test_r13_20_2_person_name_relevance.py",
            "tests/test_r13_20_1_result_cleanup.py",
            "tests/test_r13_20_unified_investigation_search.py",
            "tests/test_common_crawl_domain_hardening.py",
            "tests/test_osint_finding_persistence.py",
            "tests/test_osint_recursive_enrichment.py",
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

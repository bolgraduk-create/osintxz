from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

PATCH = "R13.24"
COPY_FILES = (
    "app/application/adaptive_relevance.py",
    "app/application/connector_health.py",
    "app/application/investigation_result_consolidation.py",
    "app/interface/desktop/workers/unified_investigation_search_worker.py",
    "app/osint/connectors/sherlock_connector.py",
    "app/osint/connectors/maigret_connector.py",
    "app/osint/connectors/user_scanner_connector.py",
    "app/intelligence_sources/adapters/wikidata_search.py",
    "tests/test_r13_24_adaptive_relevance_connector_health.py",
)
SEARCH_MARKER = "R13.24 ADAPTIVE RELEVANCE"


def project_python(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else Path(sys.executable)


def replace_once(text: str, old: str, new: str, *, name: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"{name}: expected anchor not found")
    return text.replace(old, new, 1)


def patch_search_qml(text: str) -> str:
    if SEARCH_MARKER in text:
        return text
    text = text.replace('    property string resultViewMode: "clean"\n', '    property string resultViewMode: "clean"\n    // R13.24 ADAPTIVE RELEVANCE\n')
    text = replace_once(
        text,
        '        if (tab === "candidates") return (runData.candidates || []).length\n',
        '        if (tab === "candidates") return (runData.candidates || []).length\n        if (tab === "possible") return (runData.possibleResults || []).length\n',
        name="possible count",
    )
    text = replace_once(
        text,
        '        if (activeTab === "candidates") return runData.candidates || []\n',
        '        if (activeTab === "candidates") return runData.candidates || []\n        if (activeTab === "possible") return runData.possibleResults || []\n',
        name="possible rows",
    )
    text = replace_once(
        text,
        '        if (activeTab === "candidates") return String(row.title || "Review candidate")\n',
        '        if (activeTab === "candidates") return String(row.title || "Review candidate")\n        if (activeTab === "possible") return String(row.title || "Possible result")\n',
        name="possible title",
    )
    text = replace_once(
        text,
        '        if (activeTab === "candidates") return String(row.detail || "Candidate result kept for analyst review")\n',
        '        if (activeTab === "candidates") return String(row.detail || "Candidate result kept for analyst review")\n        if (activeTab === "possible") return String(row.detail || row.visibilityReason || "Potentially useful result; analyst review required")\n',
        name="possible detail",
    )
    text = replace_once(
        text,
        '        if (activeTab === "candidates") return "REVIEW"\n',
        '        if (activeTab === "candidates") return "REVIEW"\n        if (activeTab === "possible") return "POSSIBLE"\n',
        name="possible badge",
    )
    text = replace_once(
        text,
        '        if (activeTab === "candidates") return String(row.source || "") + (row.meta ? " · " + String(row.meta) : "")\n',
        '        if (activeTab === "candidates") return String(row.source || "") + (row.meta ? " · " + String(row.meta) : "")\n        if (activeTab === "possible") return String(row.source || "") + " · visibility " + Number(row.visibilityScore || row.contextRelevanceScore || 0).toFixed(0) + (row.visibilityReason ? " · " + String(row.visibilityReason) : "")\n',
        name="possible meta",
    )
    text = replace_once(
        text,
        '        if (activeTab === "providers") return String(row.lane || "") + " · " + String(row.detail || "")\n',
        '        if (activeTab === "providers") return String(row.lane || "") + " · " + String(row.detail || "") + (row.healthAction ? " · " + String(row.healthAction) : "")\n',
        name="health detail",
    )
    text = replace_once(
        text,
        '        if (activeTab === "providers") return String(row.status || "provider").replace(/_/g, " ").toUpperCase()\n',
        '        if (activeTab === "providers") return String(row.healthLabel || row.status || "provider").replace(/_/g, " ").toUpperCase()\n',
        name="health badge",
    )
    text = replace_once(
        text,
        '        if (activeTab === "providers") return String(row.records || 0) + " record(s) · D" + Number(row.depth || 0)\n',
        '        if (activeTab === "providers") return String(row.records || 0) + " record(s) · D" + Number(row.depth || 0) + (row.healthState ? " · " + String(row.healthState).replace(/_/g, " ") : "")\n',
        name="health meta",
    )
    text = replace_once(
        text,
        '                subtext: String(root.summary.evidenceCreated || 0) + " evidence saved"\n',
        '                subtext: String(root.summary.possible || 0) + " possible · " + String(root.summary.evidenceCreated || 0) + " evidence saved"\n',
        name="possible stat",
    )
    text = replace_once(
        text,
        '                                    ? (String(root.summary.results || 0) + " clean · " + String(root.summary.rawResults || root.summary.results || 0) + " raw · " + String(root.summary.duplicatesCollapsed || 0) + " merged · " + String(root.summary.lowValueSuppressed || 0) + " suppressed")\n',
        '                                    ? (String(root.summary.results || 0) + " relevant · " + String(root.summary.possible || 0) + " possible · " + String(root.summary.rawResults || root.summary.results || 0) + " raw · " + String(root.summary.lowValueSuppressed || 0) + " suppressed")\n',
        name="progress visibility",
    )
    text = replace_once(
        text,
        '                                    { key: "results", label: "Results" },\n                                    { key: "identity", label: "Identity" },\n',
        '                                    { key: "results", label: "Results" },\n                                    { key: "possible", label: "Possible" },\n                                    { key: "identity", label: "Identity" },\n',
        name="possible tab",
    )
    text = replace_once(
        text,
        '                                : root.activeTab === "identity"\n                                    ? "No person-like records contained enough structured identity signals to score."\n',
        '                                : root.activeTab === "possible"\n                                    ? "No medium-confidence results need review. Strict identifiers remain strict; weak noise stays in Raw."\n                                : root.activeTab === "identity"\n                                    ? "No person-like records contained enough structured identity signals to score."\n',
        name="possible empty state",
    )
    return text


def verify_baseline(root: Path) -> None:
    required = [
        "app/application/investigation_result_consolidation.py",
        "app/application/contextual_relevance.py",
        "app/application/unified_persistence_relevance.py",
        "app/interface/desktop/workers/unified_investigation_search_worker.py",
        "app/interface/desktop/qml/pages/Search.qml",
        "app/osint/connectors/sherlock_connector.py",
        "app/osint/connectors/maigret_connector.py",
        "app/osint/connectors/user_scanner_connector.py",
        "app/intelligence_sources/adapters/wikidata_search.py",
    ]
    missing = [p for p in required if not (root / p).is_file()]
    if missing:
        raise SystemExit("R13.22+ baseline required. Missing: " + ", ".join(missing))
    qml = (root / "app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8", errors="ignore")
    for marker in ('{ key: "mentions", label: "Mentions" }', "runData.mentions"):
        if marker not in qml:
            raise SystemExit(f"R13.24 requires R13.22 Mentions baseline. Missing marker: {marker}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.24 Adaptive Relevance + Connector Health")
    parser.add_argument("root")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--repair-tools", action="store_true", help="Install missing Sherlock/Maigret/User Scanner packages into project .venv")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    payload = Path(__file__).resolve().parent / "payload"
    if not (root / "app").is_dir():
        raise SystemExit(f"Invalid OSINTXZ root: {root}")
    verify_baseline(root)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = root / "storage" / "patch_backups" / f"r13_24_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)

    targets = list(COPY_FILES) + ["app/interface/desktop/qml/pages/Search.qml"]
    for relative in targets:
        dst = root / relative
        if dst.exists():
            b = backup / relative
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, b)

    for relative in COPY_FILES:
        src = payload / relative
        if not src.is_file():
            raise SystemExit(f"Patch payload missing: {src}")
        dst = root / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    search = root / "app/interface/desktop/qml/pages/Search.qml"
    patched = patch_search_qml(search.read_text(encoding="utf-8"))
    search.write_text(patched, encoding="utf-8")

    py = project_python(root)
    compile_targets = [
        root / "app/application/adaptive_relevance.py",
        root / "app/application/connector_health.py",
        root / "app/application/investigation_result_consolidation.py",
        root / "app/interface/desktop/workers/unified_investigation_search_worker.py",
        root / "app/osint/connectors/sherlock_connector.py",
        root / "app/osint/connectors/maigret_connector.py",
        root / "app/osint/connectors/user_scanner_connector.py",
        root / "app/intelligence_sources/adapters/wikidata_search.py",
    ]
    subprocess.run([str(py), "-m", "py_compile", *map(str, compile_targets)], cwd=root, check=True)

    if args.repair_tools:
        repair = Path(__file__).resolve().parent / "repair_r13_24_tools.py"
        subprocess.run([str(py), str(repair), str(root), "--install-missing"], cwd=root, check=True)

    qml = search.read_text(encoding="utf-8", errors="ignore")
    worker = (root / "app/interface/desktop/workers/unified_investigation_search_worker.py").read_text(encoding="utf-8", errors="ignore")
    for marker, content in (
        ('{ key: "possible", label: "Possible" }', qml),
        ("runData.possibleResults", qml),
        ("healthLabel", qml),
        ('"possibleResults"', worker),
        ('"healthSummary"', worker),
    ):
        if marker not in content:
            raise SystemExit(f"R13.24 install verification failed: missing {marker}")

    print(f"R13.24 Adaptive Relevance + Connector Health installed.")
    print(f"Backup: {backup}")
    print(f"Python: {py}")

    if args.run_tests:
        tests = [
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
        existing = [x for x in tests if (root / x).is_file()]
        cmd = [str(py), "-m", "pytest", "-q", *existing]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, cwd=root, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

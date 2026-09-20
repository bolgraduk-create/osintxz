from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

PATCH = "R13.21.2"
FILES = (
    "app/application/contextual_relevance.py",
    "app/application/identity_resolution.py",
    "app/application/person_name_relevance.py",
    "app/application/unified_investigation_search.py",
    "app/application/investigation_result_consolidation.py",
    "app/application/unified_persistence_relevance.py",
    "app/interface/desktop/workers/unified_investigation_search_worker.py",
    "app/interface/desktop/qml/pages/Search.qml",
    "tests/test_r13_20_1_result_cleanup.py",
    "tests/test_r13_20_2_person_name_relevance.py",
    "tests/test_r13_21_identity_resolution.py",
    "tests/test_r13_21_1_contextual_relevance.py",
    "tests/test_r13_21_2_strict_identity_persistence.py",
)
CORE_PATCH_FILE = "app/osint/finding_persistence.py"
REQUIRED_BASELINE = (
    "app/application/identity_resolution.py",
    "app/application/contextual_relevance.py",
    "app/application/investigation_result_consolidation.py",
    "app/interface/desktop/workers/unified_investigation_search_worker.py",
    "app/interface/desktop/qml/pages/Search.qml",
    CORE_PATCH_FILE,
)


def python_for(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else Path(sys.executable)


def verify_baseline(root: Path) -> None:
    missing = [path for path in REQUIRED_BASELINE if not (root / path).is_file()]
    if missing:
        raise SystemExit(
            "R13.21.1 unified-search baseline is required. Missing: "
            + ", ".join(missing)
        )

    worker = (root / "app/interface/desktop/workers/unified_investigation_search_worker.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    qml = (root / "app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8", errors="ignore"
    )
    relevance = (root / "app/application/contextual_relevance.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    markers = (
        ("search_profile=self.profile", worker),
        ("errors = self._group_error_rows(errors)", worker),
        ('{ key: "identity", label: "Identity" }', qml),
        ("needsExtraLine", qml),
        ("context_terms_from_profile", relevance),
    )
    absent = [marker for marker, content in markers if marker not in content]
    if absent:
        raise SystemExit(
            "R13.21.2 requires installed R13.21.1. Missing markers: "
            + ", ".join(absent)
        )


def patch_finding_persistence_text(text: str) -> str:
    marker = "R13.21.2 pre-persistence relevance gate"
    if marker in text:
        return text

    constructor_needle = "        self.evidence_link_service = evidence_link_service\n"
    constructor_replacement = (
        constructor_needle
        + "\n"
        + "        # R13.21.2 pre-persistence relevance gate. The attribute is\n"
        + "        # intentionally optional and defaults to historical behaviour.\n"
        + "        # Unified Investigation Search installs a thread-local/container-\n"
        + "        # local callable; other OSINT workflows leave it as None.\n"
        + "        self.finding_gate = None\n"
    )
    if constructor_needle not in text:
        raise RuntimeError("Unable to locate OsintFindingPersistenceService constructor marker.")
    text = text.replace(constructor_needle, constructor_replacement, 1)

    execution_needle = (
        "                if not self._is_persistable_finding(finding):\n"
        "                    result.skipped_findings += 1\n"
        "                    continue\n\n"
        "                persisted = self._persist_finding(\n"
    )
    execution_replacement = (
        "                if not self._is_persistable_finding(finding):\n"
        "                    result.skipped_findings += 1\n"
        "                    continue\n\n"
        "                if not self._passes_finding_gate(\n"
        "                    target_type=target_type,\n"
        "                    target_value=target_value,\n"
        "                    goal=goal,\n"
        "                    connector=connector_result.connector,\n"
        "                    finding=finding,\n"
        "                ):\n"
        "                    result.skipped_findings += 1\n"
        "                    continue\n\n"
        "                persisted = self._persist_finding(\n"
    )
    if execution_needle not in text:
        raise RuntimeError("Unable to locate connector persistence loop marker.")
    text = text.replace(execution_needle, execution_replacement, 1)

    generic_needle = (
        "            if not self._is_persistable_finding(finding):\n"
        "                result.skipped_findings += 1\n"
        "                continue\n\n"
        "            result.persisted.append(\n"
    )
    generic_replacement = (
        "            if not self._is_persistable_finding(finding):\n"
        "                result.skipped_findings += 1\n"
        "                continue\n\n"
        "            if not self._passes_finding_gate(\n"
        "                target_type=target_type,\n"
        "                target_value=target_value,\n"
        "                goal=goal,\n"
        "                connector=connector,\n"
        "                finding=finding,\n"
        "            ):\n"
        "                result.skipped_findings += 1\n"
        "                continue\n\n"
        "            result.persisted.append(\n"
    )
    if generic_needle not in text:
        raise RuntimeError("Unable to locate generic finding persistence loop marker.")
    text = text.replace(generic_needle, generic_replacement, 1)

    method_needle = "    @classmethod\n    def _build_username_profile_fusion"
    method = '''    def _passes_finding_gate(\n        self,\n        *,\n        target_type: OsintTargetType,\n        target_value: str,\n        goal: DiscoveryGoal,\n        connector: str,\n        finding: OsintFinding,\n    ) -> bool:\n        """Apply an optional caller-supplied relevance gate before persistence.\n\n        Gate failures are fail-closed for the current finding: the provider\n        result remains available to the caller/UI, but no Source/Evidence/Entity\n        is created from a finding the gate could not safely classify.\n        """\n        gate = getattr(self, "finding_gate", None)\n        if gate is None:\n            return True\n        try:\n            return bool(\n                gate(\n                    target_type=target_type,\n                    target_value=target_value,\n                    goal=goal,\n                    connector=connector,\n                    finding=finding,\n                )\n            )\n        except Exception:\n            return False\n\n\n'''
    if method_needle not in text:
        raise RuntimeError("Unable to locate insertion point for finding gate helper.")
    text = text.replace(method_needle, method + method_needle, 1)
    return text


def patch_core_file(root: Path) -> None:
    path = root / CORE_PATCH_FILE
    original = path.read_text(encoding="utf-8")
    patched = patch_finding_persistence_text(original)
    path.write_text(patched, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R13.21.2 strict identity and pre-persistence relevance gate"
    )
    parser.add_argument("root", help="OSINTXZ project root, e.g. C:\\osintxz")
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

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = root / "storage" / "patch_backups" / f"r13_21_2_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)

    touched = list(FILES) + [CORE_PATCH_FILE]
    for relative in touched:
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

    patch_core_file(root)

    py = python_for(root)
    compile_targets = [
        str(root / "app/application/contextual_relevance.py"),
        str(root / "app/application/identity_resolution.py"),
        str(root / "app/application/person_name_relevance.py"),
        str(root / "app/application/unified_investigation_search.py"),
        str(root / "app/application/investigation_result_consolidation.py"),
        str(root / "app/application/unified_persistence_relevance.py"),
        str(root / "app/interface/desktop/workers/unified_investigation_search_worker.py"),
        str(root / CORE_PATCH_FILE),
    ]
    subprocess.run([str(py), "-m", "py_compile", *compile_targets], cwd=root, check=True)

    live_qml = (root / "app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8", errors="ignore"
    )
    required_qml = (
        '{ key: "identity", label: "Identity" }',
        '{ key: "candidates", label: "Candidates" }',
        "needsExtraLine",
        "pre-persistence relevance gates protect Evidence/Entities",
    )
    absent_qml = [marker for marker in required_qml if marker not in live_qml]
    if absent_qml:
        raise SystemExit("Installed Search.qml is missing R13.21.2 markers: " + ", ".join(absent_qml))

    core_text = (root / CORE_PATCH_FILE).read_text(encoding="utf-8", errors="ignore")
    if "R13.21.2 pre-persistence relevance gate" not in core_text:
        raise SystemExit("Finding persistence gate was not installed.")

    print(f"{PATCH} installed. Backup: {backup}")

    if args.run_tests:
        tests = [
            "tests/test_r13_21_2_strict_identity_persistence.py",
            "tests/test_r13_21_1_contextual_relevance.py",
            "tests/test_r13_21_identity_resolution.py",
            "tests/test_r13_20_2_person_name_relevance.py",
            "tests/test_r13_20_1_result_cleanup.py",
            "tests/test_r13_20_unified_investigation_search.py",
            "tests/test_m021_qml_recursive_collection.py",
            "tests/test_osint_finding_persistence.py",
            "tests/test_osint_recursive_enrichment.py",
            "tests/test_qml_desktop_bridge.py",
        ]
        existing = [item for item in tests if (root / item).is_file()]
        cmd = [str(py), "-m", "pytest", "-q", *existing]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, cwd=root, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

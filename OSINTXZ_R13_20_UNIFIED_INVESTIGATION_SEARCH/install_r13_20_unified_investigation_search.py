from __future__ import annotations

import argparse
from datetime import datetime
import shutil
import subprocess
import sys
from pathlib import Path


PATCH_NAME = "r13_20"


def _replace_once(path: Path, old: str, new: str, *, marker: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return False
    if old not in text:
        raise RuntimeError(
            f"R13.20 preflight failed: expected anchor was not found in {path}. "
            "The project may not match the installed R13.19 baseline."
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def _preflight(project: Path) -> None:
    required = [
        project / "app/interface/desktop/desktop_app.py",
        project / "app/interface/desktop/bridges/__init__.py",
        project / "app/interface/desktop/bridges/registry_center_bridge.py",
        project / "app/interface/desktop/bridges/source_center_bridge.py",
        project / "app/interface/desktop/workers/__init__.py",
        project / "app/interface/desktop/qml/pages/Search.qml",
        project / "app/interface/desktop/qml/pages/Registry.qml",
        project / "app/interface/desktop/qml/pages/Sources.qml",
        project / "app/application/osint_recursive_enrichment_service.py",
        project / "app/application/open_web_recursive_pivot_service.py",
        project / "app/intelligence_sources/adapters/service.py",
        project / "app/registry_intelligence/source_center.py",
        project / "tests/test_r13_19_full_registry_ui.py",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(
            "R13.20 preflight failed; R13.19 baseline files are missing:\n"
            + "\n".join(missing)
        )

    desktop = (project / "app/interface/desktop/desktop_app.py").read_text(
        encoding="utf-8"
    )
    if "RegistryCenterBridge" not in desktop or '"registryBridge"' not in desktop:
        raise RuntimeError(
            "R13.20 requires the installed R13.19 Full Registry UI baseline."
        )


def _backup(project: Path, targets: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    root = project / "storage" / "patch_backups" / f"{PATCH_NAME}_{stamp}"
    for path in targets:
        if not path.exists():
            continue
        rel = path.relative_to(project)
        destination = root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    return root


def _copy_payload(package: Path, project: Path) -> None:
    payload = package / "payload"
    for source in payload.rglob("*"):
        if not source.is_file():
            continue
        rel = source.relative_to(payload)
        destination = project / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _patch_existing(project: Path) -> None:
    bridges = project / "app/interface/desktop/bridges/__init__.py"
    _replace_once(
        bridges,
        "from app.interface.desktop.bridges.desktop_bridge import DesktopBridge\n"
        "from app.interface.desktop.bridges.registry_center_bridge import RegistryCenterBridge\n",
        "from app.interface.desktop.bridges.desktop_bridge import DesktopBridge\n"
        "from app.interface.desktop.bridges.investigation_search_bridge import InvestigationSearchBridge\n"
        "from app.interface.desktop.bridges.registry_center_bridge import RegistryCenterBridge\n",
        marker="investigation_search_bridge import InvestigationSearchBridge",
    )
    _replace_once(
        bridges,
        '__all__ = ["DesktopBridge", "RegistryCenterBridge", "SourceCenterBridge"]',
        '__all__ = [\n'
        '    "DesktopBridge",\n'
        '    "InvestigationSearchBridge",\n'
        '    "RegistryCenterBridge",\n'
        '    "SourceCenterBridge",\n'
        ']',
        marker='"InvestigationSearchBridge",',
    )

    workers = project / "app/interface/desktop/workers/__init__.py"
    _replace_once(
        workers,
        "from app.interface.desktop.workers.federated_source_search_worker import (\n"
        "    FederatedSourceSearchWorker,\n"
        ")\n",
        "from app.interface.desktop.workers.federated_source_search_worker import (\n"
        "    FederatedSourceSearchWorker,\n"
        ")\n"
        "from app.interface.desktop.workers.unified_investigation_search_worker import (\n"
        "    UnifiedInvestigationSearchWorker,\n"
        ")\n",
        marker="unified_investigation_search_worker import",
    )
    _replace_once(
        workers,
        '    "RegistrySearchWorker",\n'
        ']',
        '    "RegistrySearchWorker",\n'
        '    "UnifiedInvestigationSearchWorker",\n'
        ']',
        marker='"UnifiedInvestigationSearchWorker",',
    )

    desktop = project / "app/interface/desktop/desktop_app.py"
    _replace_once(
        desktop,
        "from app.interface.desktop.bridges import (\n"
        "    DesktopBridge,\n"
        "    RegistryCenterBridge,\n"
        "    SourceCenterBridge,\n"
        ")",
        "from app.interface.desktop.bridges import (\n"
        "    DesktopBridge,\n"
        "    InvestigationSearchBridge,\n"
        "    RegistryCenterBridge,\n"
        "    SourceCenterBridge,\n"
        ")",
        marker="InvestigationSearchBridge,",
    )
    _replace_once(
        desktop,
        "        self.bridge = DesktopBridge(container=self.container)\n"
        "        self.source_bridge = SourceCenterBridge(container=self.container)\n"
        "        self.registry_bridge = RegistryCenterBridge(container=self.container)\n"
        "        self.engine = QQmlApplicationEngine()\n",
        "        self.bridge = DesktopBridge(container=self.container)\n"
        "        self.source_bridge = SourceCenterBridge(container=self.container)\n"
        "        self.registry_bridge = RegistryCenterBridge(container=self.container)\n"
        "        self.investigation_search_bridge = InvestigationSearchBridge(\n"
        "            container=self.container\n"
        "        )\n"
        "        self.engine = QQmlApplicationEngine()\n",
        marker="self.investigation_search_bridge = InvestigationSearchBridge",
    )
    _replace_once(
        desktop,
        "        self.engine.rootContext().setContextProperty(\n"
        "            \"registryBridge\",\n"
        "            self.registry_bridge,\n"
        "        )\n"
        "        self.engine.load(QUrl.fromLocalFile(str(qml_file)))",
        "        self.engine.rootContext().setContextProperty(\n"
        "            \"registryBridge\",\n"
        "            self.registry_bridge,\n"
        "        )\n"
        "        self.engine.rootContext().setContextProperty(\n"
        "            \"investigationSearchBridge\",\n"
        "            self.investigation_search_bridge,\n"
        "        )\n"
        "        self.engine.load(QUrl.fromLocalFile(str(qml_file)))",
        marker='"investigationSearchBridge",',
    )


def _run_tests(project: Path) -> None:
    tests = [
        "tests/test_r13_20_unified_investigation_search.py",
        "tests/test_r13_19_full_registry_ui.py",
        "tests/test_r13_18_source_center_ui.py",
        "tests/test_r13_17_low_footprint_remote_pack_2.py",
        "tests/test_r13_16_low_footprint_remote_pack.py",
        "tests/test_r13_15_free_public_data_pack.py",
        "tests/test_r13_14_darkweb_discovery_indexing.py",
        "tests/test_r13_13_leak_paste_source_pack.py",
        "tests/test_r13_12_exposure_federation.py",
        "tests/test_m021_qml_recursive_collection.py",
        "tests/test_m022_registry_ui.py",
        "tests/test_m022_1_registry_core_router.py",
        "tests/test_registry_search_ui.py",
        "tests/test_qml_desktop_bridge.py",
        "tests/test_osint_recursive_enrichment.py",
        "tests/test_open_web_extraction_bridge.py",
    ]
    existing = [item for item in tests if (project / item).is_file()]
    command = [sys.executable, "-m", "pytest", "-q", *existing]
    print("Running:", " ".join(command))
    subprocess.run(command, cwd=project, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R13.20 Unified Investigation Search"
    )
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    package = Path(__file__).resolve().parent
    project = args.project_root.resolve()
    _preflight(project)

    targets = [
        project / "app/interface/desktop/bridges/__init__.py",
        project / "app/interface/desktop/bridges/investigation_search_bridge.py",
        project / "app/interface/desktop/workers/__init__.py",
        project / "app/interface/desktop/workers/unified_investigation_search_worker.py",
        project / "app/interface/desktop/desktop_app.py",
        project / "app/interface/desktop/qml/pages/Search.qml",
        project / "app/application/unified_investigation_search.py",
        project / "tests/test_r13_20_unified_investigation_search.py",
    ]
    backup = _backup(project, targets)
    _copy_payload(package, project)
    _patch_existing(project)

    print(f"R13.20 installed. Backup: {backup}")
    if args.run_tests:
        _run_tests(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

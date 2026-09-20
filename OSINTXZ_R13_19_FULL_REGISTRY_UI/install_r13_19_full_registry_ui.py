from __future__ import annotations

import argparse
from datetime import datetime
import shutil
import subprocess
import sys
from pathlib import Path


PATCH_NAME = "r13_19"


def _replace_once(path: Path, old: str, new: str, *, marker: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return False
    if old not in text:
        raise RuntimeError(
            f"R13.19 preflight failed: expected anchor was not found in {path}. "
            "The project may not match the verified R13.18 baseline."
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def _preflight(project: Path) -> None:
    required = [
        project / "app/interface/desktop/desktop_app.py",
        project / "app/interface/desktop/bridges/__init__.py",
        project / "app/interface/desktop/workers/__init__.py",
        project / "app/interface/desktop/qml/pages/Registry.qml",
        project / "app/interface/desktop/qml/pages/Sources.qml",
        project / "app/interface/desktop/bridges/source_center_bridge.py",
        project / "app/registry_intelligence/router.py",
        project / "tests/test_m022_registry_ui.py",
        project / "tests/test_r13_18_source_center_ui.py",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(
            "R13.19 preflight failed; R13.18 baseline files are missing:\n"
            + "\n".join(missing)
        )

    desktop = (project / "app/interface/desktop/desktop_app.py").read_text(
        encoding="utf-8"
    )
    if "SourceCenterBridge" not in desktop or '"sourceBridge"' not in desktop:
        raise RuntimeError(
            "R13.19 requires the installed R13.18 Source Center baseline."
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
        "from app.interface.desktop.bridges.source_center_bridge import SourceCenterBridge\n\n",
        "from app.interface.desktop.bridges.registry_center_bridge import RegistryCenterBridge\n"
        "from app.interface.desktop.bridges.source_center_bridge import SourceCenterBridge\n\n",
        marker="registry_center_bridge import RegistryCenterBridge",
    )
    _replace_once(
        bridges,
        '__all__ = ["DesktopBridge", "SourceCenterBridge"]',
        '__all__ = ["DesktopBridge", "RegistryCenterBridge", "SourceCenterBridge"]',
        marker='"RegistryCenterBridge",',
    )

    workers = project / "app/interface/desktop/workers/__init__.py"
    _replace_once(
        workers,
        "from app.interface.desktop.workers.registry_search_worker import (\n"
        "    RegistrySearchWorker,\n"
        ")\n",
        "from app.interface.desktop.workers.registry_center_worker import (\n"
        "    RegistryCenterWorker,\n"
        ")\n"
        "from app.interface.desktop.workers.registry_search_worker import (\n"
        "    RegistrySearchWorker,\n"
        ")\n",
        marker="registry_center_worker import",
    )
    _replace_once(
        workers,
        '    "OsintCollectionWorker",\n'
        '    "RegistrySearchWorker",\n',
        '    "OsintCollectionWorker",\n'
        '    "RegistryCenterWorker",\n'
        '    "RegistrySearchWorker",\n',
        marker='"RegistryCenterWorker",',
    )

    desktop = project / "app/interface/desktop/desktop_app.py"
    _replace_once(
        desktop,
        "from app.interface.desktop.bridges import DesktopBridge, SourceCenterBridge",
        "from app.interface.desktop.bridges import (\n"
        "    DesktopBridge,\n"
        "    RegistryCenterBridge,\n"
        "    SourceCenterBridge,\n"
        ")",
        marker="RegistryCenterBridge,",
    )
    _replace_once(
        desktop,
        "        self.bridge = DesktopBridge(container=self.container)\n"
        "        self.source_bridge = SourceCenterBridge(container=self.container)\n"
        "        self.engine = QQmlApplicationEngine()\n",
        "        self.bridge = DesktopBridge(container=self.container)\n"
        "        self.source_bridge = SourceCenterBridge(container=self.container)\n"
        "        self.registry_bridge = RegistryCenterBridge(container=self.container)\n"
        "        self.engine = QQmlApplicationEngine()\n",
        marker="self.registry_bridge = RegistryCenterBridge",
    )
    _replace_once(
        desktop,
        "        self.engine.rootContext().setContextProperty(\n"
        "            \"sourceBridge\",\n"
        "            self.source_bridge,\n"
        "        )\n"
        "        self.engine.load(QUrl.fromLocalFile(str(qml_file)))",
        "        self.engine.rootContext().setContextProperty(\n"
        "            \"sourceBridge\",\n"
        "            self.source_bridge,\n"
        "        )\n"
        "        self.engine.rootContext().setContextProperty(\n"
        "            \"registryBridge\",\n"
        "            self.registry_bridge,\n"
        "        )\n"
        "        self.engine.load(QUrl.fromLocalFile(str(qml_file)))",
        marker='"registryBridge",',
    )

    legacy_test = project / "tests/test_m022_registry_ui.py"
    _replace_once(
        legacy_test,
        '    assert \'model: ["EDRPOU", "Company name", "FOP name", "Court case number"]\' in registry\n'
        '    assert "desktopBridge.registrySearch(modeBox.currentText, value)" in registry\n'
        '    assert "desktopBridge.registryPersistLast()" in registry\n'
        '    assert "A match never implies identity, guilt or conviction." in registry\n',
        '    assert "registryBridge.registryCenter" in registry\n'
        '    assert "registryBridge.search(" in registry\n'
        '    assert "AUTO · all safe compatible" in registry\n'
        '    assert "registryBridge.persistLast(desktopBridge.currentCaseId)" in registry\n'
        '    assert "does not establish identity, guilt, liability or conviction" in registry\n',
        marker="registryBridge.registryCenter",
    )


def _run_tests(project: Path) -> None:
    tests = [
        "tests/test_r13_19_full_registry_ui.py",
        "tests/test_r13_18_source_center_ui.py",
        "tests/test_r13_17_low_footprint_remote_pack_2.py",
        "tests/test_r13_16_low_footprint_remote_pack.py",
        "tests/test_r13_15_free_public_data_pack.py",
        "tests/test_r13_14_darkweb_discovery_indexing.py",
        "tests/test_r13_13_leak_paste_source_pack.py",
        "tests/test_r13_12_exposure_federation.py",
        "tests/test_m022_registry_ui.py",
        "tests/test_m022_1_registry_core_router.py",
        "tests/test_registry_search_ui.py",
        "tests/test_registry_companies_house.py",
        "tests/test_registry_courtlistener.py",
        "tests/test_registry_opencorporates.py",
        "tests/test_registry_poland_krs.py",
        "tests/test_registry_recap_pacer.py",
        "tests/test_registry_vies.py",
        "tests/test_registry_persistence_integration.py",
        "tests/test_m021_qml_recursive_collection.py",
        "tests/test_qml_desktop_bridge.py",
    ]
    existing = [item for item in tests if (project / item).is_file()]
    command = [sys.executable, "-m", "pytest", "-q", *existing]
    print("Running:", " ".join(command))
    subprocess.run(command, cwd=project, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R13.19 Full Registry Search UI"
    )
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    package = Path(__file__).resolve().parent
    project = args.project_root.resolve()
    _preflight(project)

    targets = [
        project / "app/registry_intelligence/router.py",
        project / "app/registry_intelligence/source_center.py",
        project / "app/interface/desktop/bridges/__init__.py",
        project / "app/interface/desktop/bridges/registry_center_bridge.py",
        project / "app/interface/desktop/workers/__init__.py",
        project / "app/interface/desktop/workers/registry_center_worker.py",
        project / "app/interface/desktop/desktop_app.py",
        project / "app/interface/desktop/qml/pages/Registry.qml",
        project / "tests/test_m022_registry_ui.py",
        project / "tests/test_r13_19_full_registry_ui.py",
    ]
    backup = _backup(project, targets)
    _copy_payload(package, project)
    _patch_existing(project)

    print(f"R13.19 installed. Backup: {backup}")
    if args.run_tests:
        _run_tests(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

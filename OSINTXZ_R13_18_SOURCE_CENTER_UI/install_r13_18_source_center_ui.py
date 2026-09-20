from __future__ import annotations

import argparse
from datetime import datetime
import shutil
import subprocess
import sys
from pathlib import Path


PATCH_NAME = "r13_18"


def _replace_once(path: Path, old: str, new: str, *, marker: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return False
    if old not in text:
        raise RuntimeError(
            f"R13.18 preflight failed: expected anchor was not found in {path}. "
            "The project may not match the verified R13.17 baseline."
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def _preflight(project: Path) -> None:
    required = [
        project / "app/interface/desktop/desktop_app.py",
        project / "app/interface/desktop/bridges/__init__.py",
        project / "app/interface/desktop/workers/__init__.py",
        project / "app/interface/desktop/qml/Main.qml",
        project / "app/interface/desktop/qml/components/Sidebar.qml",
        project / "app/intelligence_sources/adapters/service.py",
        project / "app/intelligence_sources/adapters/registry.py",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("R13.18 preflight failed; missing files:\n" + "\n".join(missing))

    checks = {
        project / "app/interface/desktop/desktop_app.py": [
            "from app.interface.desktop.bridges import DesktopBridge",
            '"desktopBridge",',
        ],
        project / "app/interface/desktop/qml/Main.qml": [
            'case "osint": return "pages/Osint.qml"',
            'sourceCount: "—"',
        ],
        project / "app/interface/desktop/qml/components/Sidebar.qml": [
            '{key:"osint", label:"OSINT", icon:"globe.svg"}',
        ],
    }
    for path, anchors in checks.items():
        text = path.read_text(encoding="utf-8")
        if "SourceCenterBridge" in text or 'case "sources": return "pages/Sources.qml"' in text:
            continue
        for anchor in anchors:
            if anchor not in text:
                raise RuntimeError(
                    f"R13.18 preflight failed: {anchor!r} was not found in {path}."
                )


def _backup(project: Path, targets: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
        'from app.interface.desktop.bridges.desktop_bridge import DesktopBridge\n\n__all__ = ["DesktopBridge"]',
        'from app.interface.desktop.bridges.desktop_bridge import DesktopBridge\n'
        'from app.interface.desktop.bridges.source_center_bridge import SourceCenterBridge\n\n'
        '__all__ = ["DesktopBridge", "SourceCenterBridge"]',
        marker="source_center_bridge import SourceCenterBridge",
    )

    workers = project / "app/interface/desktop/workers/__init__.py"
    _replace_once(
        workers,
        'from app.interface.desktop.workers.osint_collection_worker import (\n'
        '    OsintCollectionWorker,\n'
        ')\n',
        'from app.interface.desktop.workers.federated_source_search_worker import (\n'
        '    FederatedSourceSearchWorker,\n'
        ')\n'
        'from app.interface.desktop.workers.osint_collection_worker import (\n'
        '    OsintCollectionWorker,\n'
        ')\n',
        marker="FederatedSourceSearchWorker",
    )
    _replace_once(
        workers,
        '__all__ = ["OsintCollectionWorker", "RegistrySearchWorker"]',
        '__all__ = [\n'
        '    "FederatedSourceSearchWorker",\n'
        '    "OsintCollectionWorker",\n'
        '    "RegistrySearchWorker",\n'
        ']',
        marker='"FederatedSourceSearchWorker",',
    )

    desktop = project / "app/interface/desktop/desktop_app.py"
    _replace_once(
        desktop,
        'from app.interface.desktop.bridges import DesktopBridge',
        'from app.interface.desktop.bridges import DesktopBridge, SourceCenterBridge',
        marker="DesktopBridge, SourceCenterBridge",
    )
    _replace_once(
        desktop,
        '        self.bridge = DesktopBridge(container=self.container)\n'
        '        self.engine = QQmlApplicationEngine()\n',
        '        self.bridge = DesktopBridge(container=self.container)\n'
        '        self.source_bridge = SourceCenterBridge(container=self.container)\n'
        '        self.engine = QQmlApplicationEngine()\n',
        marker="self.source_bridge = SourceCenterBridge",
    )
    _replace_once(
        desktop,
        '        self.engine.rootContext().setContextProperty(\n'
        '            "desktopBridge",\n'
        '            self.bridge,\n'
        '        )\n'
        '        self.engine.load(QUrl.fromLocalFile(str(qml_file)))',
        '        self.engine.rootContext().setContextProperty(\n'
        '            "desktopBridge",\n'
        '            self.bridge,\n'
        '        )\n'
        '        self.engine.rootContext().setContextProperty(\n'
        '            "sourceBridge",\n'
        '            self.source_bridge,\n'
        '        )\n'
        '        self.engine.load(QUrl.fromLocalFile(str(qml_file)))',
        marker='"sourceBridge",',
    )

    main = project / "app/interface/desktop/qml/Main.qml"
    _replace_once(
        main,
        '        case "osint": return "pages/Osint.qml"\n',
        '        case "osint": return "pages/Osint.qml"\n'
        '        case "sources": return "pages/Sources.qml"\n',
        marker='case "sources": return "pages/Sources.qml"',
    )
    _replace_once(
        main,
        '        sourceCount: "—"\n'
        '        integrationCount: "—"\n'
        '        monitorCount: "—"\n',
        '        sourceCount: String((sourceBridge.sourceCenter.counts || {}).total || 0)\n'
        '        integrationCount: String((sourceBridge.sourceCenter.counts || {}).searchable || 0)\n'
        '        monitorCount: sourceBridge.busy ? "1" : "0"\n',
        marker="sourceBridge.sourceCenter.counts",
    )

    sidebar = project / "app/interface/desktop/qml/components/Sidebar.qml"
    _replace_once(
        sidebar,
        '                    {key:"osint", label:"OSINT", icon:"globe.svg"},\n'
        '                    {key:"evidence", label:"Evidence", icon:"document.svg"},',
        '                    {key:"osint", label:"OSINT", icon:"globe.svg"},\n'
        '                    {key:"sources", label:"Sources", icon:"database.svg"},\n'
        '                    {key:"evidence", label:"Evidence", icon:"document.svg"},',
        marker='{key:"sources", label:"Sources", icon:"database.svg"}',
    )


def _run_tests(project: Path) -> None:
    tests = [
        "tests/test_r13_18_source_center_ui.py",
        "tests/test_r13_17_low_footprint_remote_pack_2.py",
        "tests/test_r13_16_low_footprint_remote_pack.py",
        "tests/test_r13_15_free_public_data_pack.py",
        "tests/test_r13_14_darkweb_discovery_indexing.py",
        "tests/test_r13_13_leak_paste_source_pack.py",
        "tests/test_r13_12_exposure_federation.py",
        "tests/test_m021_qml_recursive_collection.py",
        "tests/test_m022_registry_ui.py",
        "tests/test_qml_desktop_bridge.py",
    ]
    command = [sys.executable, "-m", "pytest", "-q", *tests]
    print("Running:", " ".join(command))
    subprocess.run(command, cwd=project, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.18 Source Center UI")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    package = Path(__file__).resolve().parent
    project = args.project_root.resolve()
    _preflight(project)

    existing_targets = [
        project / "app/interface/desktop/bridges/__init__.py",
        project / "app/interface/desktop/workers/__init__.py",
        project / "app/interface/desktop/desktop_app.py",
        project / "app/interface/desktop/qml/Main.qml",
        project / "app/interface/desktop/qml/components/Sidebar.qml",
    ]
    new_targets = [
        project / "app/intelligence_sources/source_center.py",
        project / "app/interface/desktop/workers/federated_source_search_worker.py",
        project / "app/interface/desktop/bridges/source_center_bridge.py",
        project / "app/interface/desktop/qml/pages/Sources.qml",
        project / "tests/test_r13_18_source_center_ui.py",
    ]
    backup = _backup(project, existing_targets + new_targets)
    _copy_payload(package, project)
    _patch_existing(project)

    print(f"R13.18 installed. Backup: {backup}")
    if args.run_tests:
        _run_tests(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

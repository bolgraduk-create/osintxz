"""
Bootstrap architecture contract.

The desktop application must have one implementation only:

    main.py
        -> app.interface.desktop.desktop_app.DesktopApplication

Legacy module paths may remain importable, but they must only re-export
the canonical implementation and must never build their own QApplication
or ServiceContainer.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CORE_COMPAT = ROOT / "app" / "core" / "application.py"
DESKTOP_COMPAT = ROOT / "app" / "interface" / "desktop" / "app.py"
CANONICAL_DESKTOP = (
    ROOT / "app" / "interface" / "desktop" / "desktop_app.py"
)
MAIN = ROOT / "main.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _defined_classes(path: Path) -> set[str]:
    tree = ast.parse(_read(path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }


def test_canonical_desktop_application_exists() -> None:
    assert CANONICAL_DESKTOP.exists()
    assert "DesktopApplication" in _defined_classes(CANONICAL_DESKTOP)


def test_main_imports_canonical_desktop_application() -> None:
    tree = ast.parse(_read(MAIN))
    canonical_import = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue

        if node.module != "app.interface.desktop.desktop_app":
            continue

        if any(
            alias.name == "DesktopApplication"
            for alias in node.names
        ):
            canonical_import = True
            break

    assert canonical_import


def test_core_application_is_compatibility_module_only() -> None:
    source = _read(CORE_COMPAT)

    assert "QApplication(" not in source
    assert "ServiceContainer(" not in source
    assert "create_session(" not in source
    assert "init_database(" not in source
    assert "class Application" not in source


def test_legacy_desktop_app_is_compatibility_module_only() -> None:
    source = _read(DESKTOP_COMPAT)

    assert "QApplication(" not in source
    assert "ServiceContainer(" not in source
    assert "class DesktopApplication" not in source


def test_legacy_modules_point_to_canonical_implementation() -> None:
    from app.core.application import Application
    from app.interface.desktop.app import (
        DesktopApplication as LegacyDesktopApplication,
    )
    from app.interface.desktop.desktop_app import DesktopApplication

    assert Application is DesktopApplication
    assert LegacyDesktopApplication is DesktopApplication

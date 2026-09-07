"""
Final stabilization architecture contract.

This file intentionally performs only static/import-safe checks.
It does not access the network or database.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from app.application.investigation_analysis_runner import (
    InvestigationAnalysisRunner,
)
from app.interface.desktop.desktop_app import (
    DesktopApplication,
)
from app.services.telegram_import_service import (
    TelegramImportService,
)


ROOT = Path(__file__).resolve().parents[1]

SERVICE_CONTAINER = ROOT / "app" / "core" / "service_container.py"
CORE_APPLICATION = ROOT / "app" / "core" / "application.py"
LEGACY_DESKTOP_APP = ROOT / "app" / "interface" / "desktop" / "app.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _self_assignments(path: Path) -> set[str]:
    tree = ast.parse(_source(path))
    result: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                result.add(target.attr)

    return result


def test_service_container_exposes_modern_runner() -> None:
    assignments = _self_assignments(SERVICE_CONTAINER)

    assert "investigation_analysis_orchestrator" in assignments
    assert "investigation_analysis_runner" in assignments
    assert "evidence_processing_service" not in assignments


def test_telegram_import_has_no_legacy_processing_parameter() -> None:
    signature = inspect.signature(TelegramImportService.__init__)

    assert "processing_service" not in signature.parameters


def test_legacy_bootstrap_modules_are_compatibility_only() -> None:
    for path in (CORE_APPLICATION, LEGACY_DESKTOP_APP):
        source = _source(path)
        assert "QApplication(" not in source
        assert "ServiceContainer(" not in source


def test_modern_runtime_classes_are_importable() -> None:
    assert InvestigationAnalysisRunner.__name__ == "InvestigationAnalysisRunner"
    assert DesktopApplication.__name__ == "DesktopApplication"

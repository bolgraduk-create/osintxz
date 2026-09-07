"""
Architecture contract for Stabilization 07.

The modern production path must not compose or inject
EvidenceProcessingService into Telegram import.

Legacy modules may still exist on disk for compatibility.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from app.application.investigation_analysis_runner import (
    InvestigationAnalysisRunner,
)
from app.services.telegram_import_service import (
    TelegramImportService,
)


ROOT = Path(__file__).resolve().parents[1]

SERVICE_CONTAINER = (
    ROOT / "app" / "core" / "service_container.py"
)

TELEGRAM_IMPORT = (
    ROOT / "app" / "services" / "telegram_import_service.py"
)


def _tree(path: Path) -> ast.Module:

    return ast.parse(
        path.read_text(
            encoding="utf-8",
        )
    )


def _imports_module(
    path: Path,
    module_name: str,
) -> bool:

    tree = _tree(path)

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.ImportFrom,
        ):

            if node.module == module_name:
                return True

        elif isinstance(
            node,
            ast.Import,
        ):

            if any(
                alias.name == module_name
                for alias in node.names
            ):
                return True

    return False


def _self_assignment_names(
    path: Path,
) -> set[str]:

    tree = _tree(path)
    names: set[str] = set()

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        for target in node.targets:

            if (
                isinstance(
                    target,
                    ast.Attribute,
                )
                and isinstance(
                    target.value,
                    ast.Name,
                )
                and target.value.id == "self"
            ):

                names.add(
                    target.attr
                )

    return names


def test_telegram_import_no_longer_depends_on_evidence_processing_service() -> None:

    assert not _imports_module(
        TELEGRAM_IMPORT,
        "app.services.evidence_processing_service",
    )

    signature = inspect.signature(
        TelegramImportService.__init__
    )

    assert (
        "processing_service"
        not in signature.parameters
    )

    assert (
        "processing_service"
        not in _self_assignment_names(
            TELEGRAM_IMPORT
        )
    )


def test_service_container_no_longer_composes_evidence_processing_service() -> None:

    assert not _imports_module(
        SERVICE_CONTAINER,
        "app.services.evidence_processing_service",
    )

    assignments = _self_assignment_names(
        SERVICE_CONTAINER
    )

    assert (
        "evidence_processing_service"
        not in assignments
    )


def test_service_container_keeps_modern_analysis_runner() -> None:

    assignments = _self_assignment_names(
        SERVICE_CONTAINER
    )

    assert (
        "investigation_analysis_orchestrator"
        in assignments
    )

    assert (
        "investigation_analysis_runner"
        in assignments
    )


def test_legacy_service_file_may_remain_but_is_not_composed() -> None:

    legacy_file = (
        ROOT
        / "app"
        / "services"
        / "evidence_processing_service.py"
    )

    # Compatibility presence is allowed.
    # The important invariant is that the production composition root
    # no longer builds or injects it.
    if legacy_file.exists():
        assert legacy_file.is_file()


def test_modern_runner_class_is_available() -> None:

    assert (
        InvestigationAnalysisRunner.__name__
        ==
        "InvestigationAnalysisRunner"
    )

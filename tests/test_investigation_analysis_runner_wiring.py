"""
Composition-root contract for InvestigationAnalysisRunner wiring.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]

SERVICE_CONTAINER = (
    ROOT
    / "app"
    / "core"
    / "service_container.py"
)


def _tree() -> ast.Module:

    source = SERVICE_CONTAINER.read_text(
        encoding="utf-8",
    )

    return ast.parse(
        source
    )


def test_service_container_imports_modern_analysis_runner() -> None:

    tree = _tree()

    found = False

    for node in ast.walk(
        tree
    ):

        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        if (
            node.module
            !=
            "app.application.investigation_analysis_runner"
        ):
            continue

        if any(
            alias.name
            ==
            "InvestigationAnalysisRunner"
            for alias in node.names
        ):

            found = True
            break

    assert found


def test_service_container_creates_analysis_runner() -> None:

    tree = _tree()

    assignments = [
        node
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            ast.Assign,
        )
    ]

    found = False

    for node in assignments:

        if len(
            node.targets
        ) != 1:

            continue

        target = node.targets[0]

        if not (
            isinstance(
                target,
                ast.Attribute,
            )
            and isinstance(
                target.value,
                ast.Name,
            )
            and target.value.id == "self"
            and target.attr
            ==
            "investigation_analysis_runner"
        ):

            continue

        if not isinstance(
            node.value,
            ast.Call,
        ):

            continue

        if not (
            isinstance(
                node.value.func,
                ast.Name,
            )
            and node.value.func.id
            ==
            "InvestigationAnalysisRunner"
        ):

            continue

        found = True
        break

    assert found


def test_analysis_runner_reuses_container_orchestrator() -> None:

    tree = _tree()

    runner_call: ast.Call | None = None

    for node in ast.walk(
        tree
    ):

        if not isinstance(
            node,
            ast.Assign,
        ):

            continue

        if len(
            node.targets
        ) != 1:

            continue

        target = node.targets[0]

        if not (
            isinstance(
                target,
                ast.Attribute,
            )
            and isinstance(
                target.value,
                ast.Name,
            )
            and target.value.id == "self"
            and target.attr
            ==
            "investigation_analysis_runner"
        ):

            continue

        if isinstance(
            node.value,
            ast.Call,
        ):

            runner_call = (
                node.value
            )

            break

    assert runner_call is not None

    orchestrator_keyword = next(
        (
            keyword
            for keyword in runner_call.keywords
            if keyword.arg == "orchestrator"
        ),
        None,
    )

    assert orchestrator_keyword is not None

    value = (
        orchestrator_keyword.value
    )

    assert isinstance(
        value,
        ast.Attribute,
    )

    assert isinstance(
        value.value,
        ast.Name,
    )

    assert value.value.id == "self"

    assert (
        value.attr
        ==
        "investigation_analysis_orchestrator"
    )


def test_modern_runner_is_created_only_once() -> None:

    tree = _tree()

    count = 0

    for node in ast.walk(
        tree
    ):

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
                and target.attr
                ==
                "investigation_analysis_runner"
            ):

                count += 1

    assert count == 1

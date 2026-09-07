"""
Tests for the canonical InvestigationAnalysisRunner.
"""

from __future__ import annotations

import ast
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.application.investigation_analysis_contracts import (
    InvestigationAnalysisRequest,
    InvestigationAnalysisResult,
    InvestigationAnalysisStage,
    InvestigationAnalysisStatus,
)
from app.application.investigation_analysis_orchestrator import (
    InvestigationAnalysisOrchestrator,
)
from app.application.investigation_analysis_runner import (
    InvestigationAnalysisRunner,
)


def _fake_orchestrator() -> InvestigationAnalysisOrchestrator:
    """
    Build an instance without invoking the heavyweight constructor.

    The runner test is about delegation, not service wiring.
    """

    orchestrator = object.__new__(
        InvestigationAnalysisOrchestrator
    )

    orchestrator.analyze = Mock()

    return orchestrator


def _result() -> InvestigationAnalysisResult:

    return InvestigationAnalysisResult(
        case_id=uuid4(),
        status=(
            InvestigationAnalysisStatus.SUCCESS
        ),
        stage_results=(),
    )


def test_runner_requires_real_orchestrator_type() -> None:

    with pytest.raises(
        TypeError,
        match="InvestigationAnalysisOrchestrator",
    ):

        InvestigationAnalysisRunner(
            orchestrator=object(),
        )


def test_runner_builds_request_and_delegates() -> None:

    orchestrator = _fake_orchestrator()

    expected = _result()

    orchestrator.analyze.return_value = (
        expected
    )

    runner = InvestigationAnalysisRunner(
        orchestrator=orchestrator,
    )

    case_id = str(
        uuid4()
    )

    result = runner.run(
        case_id,
        question="  Who is central?  ",
        requested_stages=(
            InvestigationAnalysisStage.GRAPH,
        ),
        metadata={
            "source": "test",
        },
    )

    assert result is expected

    orchestrator.analyze.assert_called_once()

    call = (
        orchestrator
        .analyze
        .call_args
    )

    request = call.args[0]

    assert isinstance(
        request,
        InvestigationAnalysisRequest,
    )

    assert request.case_id == case_id
    assert request.question == "Who is central?"
    assert (
        request.requested_stages
        ==
        (
            InvestigationAnalysisStage.GRAPH,
        )
    )

    assert dict(
        request.metadata
        or {}
    ) == {
        "source": "test",
    }

    assert (
        call.kwargs["progress_callback"]
        is None
    )

    assert (
        call.kwargs["cancellation_token"]
        is None
    )


def test_runner_normalizes_blank_question_to_none() -> None:

    orchestrator = _fake_orchestrator()

    orchestrator.analyze.return_value = (
        _result()
    )

    runner = InvestigationAnalysisRunner(
        orchestrator=orchestrator,
    )

    runner.run(
        str(
            uuid4()
        ),
        question="   ",
    )

    request = (
        orchestrator
        .analyze
        .call_args
        .args[0]
    )

    assert request.question is None


def test_runner_rejects_empty_case_id() -> None:

    orchestrator = _fake_orchestrator()

    runner = InvestigationAnalysisRunner(
        orchestrator=orchestrator,
    )

    with pytest.raises(
        ValueError,
        match="case_id cannot be empty",
    ):

        runner.run(
            "   "
        )

    orchestrator.analyze.assert_not_called()


def test_runner_preserves_callbacks() -> None:

    orchestrator = _fake_orchestrator()

    orchestrator.analyze.return_value = (
        _result()
    )

    runner = InvestigationAnalysisRunner(
        orchestrator=orchestrator,
    )

    progress_callback = Mock()
    cancellation_token = Mock()

    runner.run(
        str(
            uuid4()
        ),
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
    )

    call = (
        orchestrator
        .analyze
        .call_args
    )

    assert (
        call.kwargs["progress_callback"]
        is progress_callback
    )

    assert (
        call.kwargs["cancellation_token"]
        is cancellation_token
    )


def test_runner_metadata_identifies_modern_engine() -> None:

    orchestrator = _fake_orchestrator()

    runner = InvestigationAnalysisRunner(
        orchestrator=orchestrator,
    )

    metadata: dict[str, Any] = (
        runner.metadata()
    )

    assert metadata["name"] == (
        "InvestigationAnalysisRunner"
    )

    assert metadata["version"] == "1"

    assert metadata["engine"] == (
        "InvestigationAnalysisOrchestrator"
    )


def test_runner_module_does_not_import_legacy_pipeline() -> None:

    from pathlib import Path
    import app.application.investigation_analysis_runner as module

    source = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    imported_modules: set[str] = set()

    for node in ast.walk(
        tree
    ):

        if isinstance(
            node,
            ast.ImportFrom,
        ):

            if node.module:

                imported_modules.add(
                    node.module
                )

        elif isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                imported_modules.add(
                    alias.name
                )

    forbidden_modules = {
        "app.pipelines.investigation_pipeline",
        "app.services.investigation_pipeline",
        "app.services.evidence_processing_service",
    }

    assert (
        imported_modules
        .isdisjoint(
            forbidden_modules
        )
    )

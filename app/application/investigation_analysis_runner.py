"""
Canonical application-level investigation analysis runner.

This is the small production-facing entry point for running the modern
Investigation Analysis Engine.

Architecture:

caller / controller / worker
        ↓
InvestigationAnalysisRunner
        ↓
InvestigationAnalysisOrchestrator
        ↓
analysis services

The runner does NOT:
- use EvidenceProcessingService
- use the legacy InvestigationPipeline
- access ORM repositories directly
- commit or roll back transactions
- contain Qt/UI logic
- implement analytical algorithms
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.application.investigation_analysis_contracts import (
    InvestigationAnalysisCancellationToken,
    InvestigationAnalysisProgressCallback,
    InvestigationAnalysisRequest,
    InvestigationAnalysisResult,
    InvestigationAnalysisStage,
)
from app.application.investigation_analysis_orchestrator import (
    InvestigationAnalysisOrchestrator,
)


class InvestigationAnalysisRunner:
    """
    Stable facade for one orchestrated investigation analysis run.
    """

    VERSION = "1"

    def __init__(
        self,
        *,
        orchestrator: InvestigationAnalysisOrchestrator,
    ) -> None:

        if not isinstance(
            orchestrator,
            InvestigationAnalysisOrchestrator,
        ):

            raise TypeError(
                "orchestrator must be "
                "InvestigationAnalysisOrchestrator."
            )

        self.orchestrator = orchestrator

    def run(
        self,
        case_id: str,
        *,
        question: str | None = None,
        requested_stages: (
            tuple[
                InvestigationAnalysisStage,
                ...,
            ]
            | None
        ) = None,
        metadata: (
            Mapping[
                str,
                Any,
            ]
            | None
        ) = None,
        progress_callback: (
            InvestigationAnalysisProgressCallback
            | None
        ) = None,
        cancellation_token: (
            InvestigationAnalysisCancellationToken
            | None
        ) = None,
    ) -> InvestigationAnalysisResult:
        """
        Run the modern Investigation Analysis Engine for one case.

        ``requested_stages=None`` delegates the standard full analysis
        plan to the orchestrator.

        Transaction control remains with the caller/composition root.
        """

        normalized_case_id = str(
            case_id
            or ""
        ).strip()

        if not normalized_case_id:

            raise ValueError(
                "case_id cannot be empty."
            )

        normalized_question: str | None

        if question is None:

            normalized_question = None

        else:

            normalized_question = str(
                question
            ).strip()

            if not normalized_question:
                normalized_question = None

        normalized_metadata = (
            dict(
                metadata
            )
            if metadata is not None
            else None
        )

        request = InvestigationAnalysisRequest(
            case_id=normalized_case_id,
            question=normalized_question,
            requested_stages=requested_stages,
            metadata=normalized_metadata,
        )

        return self.orchestrator.analyze(
            request,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token,
        )

    def metadata(
        self,
    ) -> dict[str, str]:
        """
        Return runner identity for diagnostics/UI metadata.
        """

        return {
            "name": self.__class__.__name__,
            "version": self.VERSION,
            "engine": (
                self.orchestrator
                .__class__
                .__name__
            ),
        }


__all__ = [
    "InvestigationAnalysisRunner",
]

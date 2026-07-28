"""
Analysis service.

Provides application-level access
to analytical workflows.

Business logic stays here,
analytical algorithms stay
inside analyzers and pipelines.
"""

from __future__ import annotations

from typing import Any

from app.analysis import (
    AnalysisPipeline,
)


class AnalysisService:
    """
    Service responsible for analysis execution.
    """


    def __init__(
        self,
        pipeline: AnalysisPipeline | None = None,
    ):
        """
        Initialize analysis service.
        """

        self.pipeline = (
            pipeline
            or AnalysisPipeline()
        )


    def analyze(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Run analysis pipeline.
        """

        return self.pipeline.analyze(
            data
        )
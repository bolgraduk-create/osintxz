"""
Investigation runner.

Single entry point for investigation execution.

Responsibilities:

- start investigation pipeline
- hide pipeline implementation
- provide unified execution interface

Does NOT:

- collect evidence
- analyze entities
- generate reports
"""

from __future__ import annotations

from uuid import UUID

from app.pipelines.investigation_pipeline import (
    InvestigationPipeline,
)


class InvestigationRunner:
    """
    Runs complete investigation.
    """

    def __init__(
        self,
        pipeline: InvestigationPipeline,
    ):
        self.pipeline = pipeline

    def run(
        self,
        case_id: UUID,
    ) -> None:
        """
        Execute investigation.
        """

        self.pipeline.run(
            case_id
        )
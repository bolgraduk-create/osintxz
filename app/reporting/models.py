"""
Reporting models.

Contains internal report structures.

Does not:
- generate reports
- export files
- access database
"""

from __future__ import annotations

from dataclasses import dataclass, field

from datetime import datetime, timezone

from typing import Any


@dataclass
class InvestigationReport:
    """
    Main investigation report model.
    """


    title: str


    summary: str = ""


    findings: list[dict[str, Any]] = field(
        default_factory=list
    )


    evidence: list[dict[str, Any]] = field(
        default_factory=list
    )


    ai_insights: list[dict[str, Any]] = field(
        default_factory=list
    )


    metadata: dict[str, Any] = field(
        default_factory=dict
    )


    created_at: datetime = field(
        default_factory=lambda:
            datetime.now(
                timezone.utc
            )
    )


    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert report to dictionary.
        """


        return {

            "title":
                self.title,


            "summary":
                self.summary,


            "findings":
                self.findings,


            "evidence":
                self.evidence,


            "ai_insights":
                self.ai_insights,


            "metadata":
                self.metadata,


            "created_at":
                self.created_at.isoformat(),

        }
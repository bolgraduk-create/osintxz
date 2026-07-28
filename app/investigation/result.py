"""
Investigation result.

Returned after successful
(or failed) investigation execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.investigation.state import (
    InvestigationState,
)


@dataclass(slots=True)
class InvestigationResult:
    """
    Final investigation result.
    """

    # ==========================================================
    # Identity
    # ==========================================================

    case_id: UUID | None = None

    # ==========================================================
    # Status
    # ==========================================================

    state: InvestigationState = (
        InvestigationState.CREATED
    )

    success: bool = True

    # ==========================================================
    # Statistics
    # ==========================================================

    collected_objects: int = 0

    processed_objects: int = 0

    evidence_count: int = 0

    entity_count: int = 0

    relationship_count: int = 0

    timeline_event_count: int = 0

    report_count: int = 0

    ai_result_count: int = 0

    # ==========================================================
    # Runtime
    # ==========================================================

    duration_seconds: float = 0.0

    warnings: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    # ==========================================================
    # Helpers
    # ==========================================================

    @property
    def has_errors(
        self,
    ) -> bool:
        """
        Whether execution contains errors.
        """

        return bool(self.errors)

    @property
    def has_warnings(
        self,
    ) -> bool:
        """
        Whether execution contains warnings.
        """

        return bool(self.warnings)
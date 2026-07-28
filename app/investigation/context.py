"""
Investigation execution context.

Shared runtime object used by the
investigation pipeline.

Responsibilities:

- store investigation state
- pass data between stages
- collect intermediate results

Does NOT:

- execute business logic
- access database
- perform analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class InvestigationContext:
    """
    Shared investigation context.
    """

    # ==========================================================
    # Case
    # ==========================================================

    case_id: UUID | None = None

    project_id: UUID | None = None

    # ==========================================================
    # Input
    # ==========================================================

    source_path: str | None = None

    input_data: dict[str, Any] = field(
        default_factory=dict
    )

    # ==========================================================
    # Collection
    # ==========================================================

    collected_objects: list[Any] = field(
        default_factory=list
    )

    # ==========================================================
    # Processing
    # ==========================================================

    processed_objects: list[Any] = field(
        default_factory=list
    )

    # ==========================================================
    # Investigation data
    # ==========================================================

    evidence: list[Any] = field(
        default_factory=list
    )

    entities: list[Any] = field(
        default_factory=list
    )

    relationships: list[Any] = field(
        default_factory=list
    )

    timeline_events: list[Any] = field(
        default_factory=list
    )

    search_indexes: list[Any] = field(
        default_factory=list
    )

    reports: list[Any] = field(
        default_factory=list
    )

    ai_results: list[Any] = field(
        default_factory=list
    )

    # ==========================================================
    # Runtime
    # ==========================================================

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    warnings: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    # ==========================================================
    # Helpers
    # ==========================================================

    def add_warning(
        self,
        message: str,
    ) -> None:
        """
        Store warning.
        """

        self.warnings.append(message)

    def add_error(
        self,
        message: str,
    ) -> None:
        """
        Store error.
        """

        self.errors.append(message)

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
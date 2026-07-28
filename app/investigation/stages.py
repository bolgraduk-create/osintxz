"""
Pipeline stages.

Defines the interface for every
investigation stage.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from app.investigation.context import (
    InvestigationContext,
)


class InvestigationStage(ABC):
    """
    Base investigation stage.
    """

    @property
    @abstractmethod
    def name(
        self,
    ) -> str:
        """
        Stage name.
        """

    @abstractmethod
    def run(
        self,
        context: InvestigationContext,
    ) -> InvestigationContext:
        """
        Execute stage.
        """


class CollectionStage(
    InvestigationStage,
):
    """
    Collect raw investigation data.
    """

    @property
    def name(
        self,
    ) -> str:

        return "collection"

    def run(
        self,
        context: InvestigationContext,
    ) -> InvestigationContext:

        return context


class ProcessingStage(
    InvestigationStage,
):
    """
    Process collected data.
    """

    @property
    def name(
        self,
    ) -> str:

        return "processing"

    def run(
        self,
        context: InvestigationContext,
    ) -> InvestigationContext:

        return context


class EntityResolutionStage(
    InvestigationStage,
):
    """
    Resolve duplicate entities.
    """

    @property
    def name(
        self,
    ) -> str:

        return "entity_resolution"

    def run(
        self,
        context: InvestigationContext,
    ) -> InvestigationContext:

        return context


class EvidenceStage(
    InvestigationStage,
):
    """
    Build evidence objects.
    """

    @property
    def name(
        self,
    ) -> str:

        return "evidence"

    def run(
        self,
        context: InvestigationContext,
    ) -> InvestigationContext:

        return context


class RelationshipStage(
    InvestigationStage,
):
    """
    Build relationships.
    """

    @property
    def name(
        self,
    ) -> str:

        return "relationships"

    def run(
        self,
        context: InvestigationContext,
    ) -> InvestigationContext:

        return context


class TimelineStage(
    InvestigationStage,
):
    """
    Build timeline.
    """

    @property
    def name(
        self,
    ) -> str:

        return "timeline"

    def run(
        self,
        context: InvestigationContext,
    ) -> InvestigationContext:

        return context


class SearchStage(
    InvestigationStage,
):
    """
    Build search indexes.
    """

    @property
    def name(
        self,
    ) -> str:

        return "search"

    def run(
        self,
        context: InvestigationContext,
    ) -> InvestigationContext:

        return context


class AIStage(
    InvestigationStage,
):
    """
    Execute AI analysis.
    """

    @property
    def name(
        self,
    ) -> str:

        return "ai"

    def run(
        self,
        context: InvestigationContext,
    ) -> InvestigationContext:

        return context


class ReportStage(
    InvestigationStage,
):
    """
    Generate reports.
    """

    @property
    def name(
        self,
    ) -> str:

        return "report"

    def run(
        self,
        context: InvestigationContext,
    ) -> InvestigationContext:

        return context
"""
Investigation execution state.

Defines lifecycle of an investigation.
"""

from __future__ import annotations

from enum import Enum


class InvestigationState(str, Enum):
    """
    Investigation execution state.
    """

    CREATED = "created"

    COLLECTING = "collecting"

    PROCESSING = "processing"

    ENTITY_RESOLUTION = "entity_resolution"

    EVIDENCE_BUILDING = "evidence_building"

    RELATIONSHIP_BUILDING = "relationship_building"

    TIMELINE_BUILDING = "timeline_building"

    SEARCH_INDEXING = "search_indexing"

    AI_ANALYSIS = "ai_analysis"

    REPORT_GENERATION = "report_generation"

    FINISHED = "finished"

    FAILED = "failed"
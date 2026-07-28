"""
Investigation Pipeline.

Coordinates the complete investigation flow.

Responsibilities:

- receive collected data
- create evidence
- create entities
- create relationships
- create timeline events

This service is the main orchestration layer between
Collectors and Analysis.
"""

from __future__ import annotations

from typing import Iterable


class InvestigationPipeline:
    """
    Main investigation pipeline.
    """

    def __init__(
        self,
        collection_service,
        evidence_service,
        entity_service,
        relationship_service,
        timeline_service,
    ):

        self.collection_service = collection_service

        self.evidence_service = evidence_service

        self.entity_service = entity_service

        self.relationship_service = relationship_service

        self.timeline_service = timeline_service

    def process(
        self,
        case_id,
        collected_items: Iterable,
    ):
        """
        Process collected items.

        Future workflow:

        Collector
            ↓
        Evidence
            ↓
        Entities
            ↓
        Relationships
            ↓
        Timeline
        """

        evidence = self.evidence_service.create_from_collection(
            case_id=case_id,
            collected_items=collected_items,
        )

        entities = self.entity_service.extract(
            case_id=case_id,
            evidence=evidence,
        )

        relationships = self.relationship_service.build(
            case_id=case_id,
            entities=entities,
            evidence=evidence,
        )

        self.timeline_service.build(
            case_id=case_id,
            evidence=evidence,
            relationships=relationships,
        )

        return {
            "evidence": evidence,
            "entities": entities,
            "relationships": relationships,
        }
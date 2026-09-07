"""Structured Entity/Evidence retrieval for Unified Investigation Search."""

from __future__ import annotations

from app.investigation.search_query import InvestigationSearchQuery, SearchMethod
from app.investigation.search_result import (
    InvestigationSearchHit,
    SearchMatchReason,
    SearchScores,
)
from app.models.entity import Entity, EntityType
from app.models.evidence import Evidence, EvidenceType
from app.repositories.entity_repository import EntityRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.services.search_retriever import SearchRetriever, SearchRetrieverInfo


class StructuredSearchRetriever(SearchRetriever):
    """Retrieve typed Entity/Evidence rows through explicit database filters."""

    SUPPORTED_OBJECT_TYPES = frozenset({"entity", "evidence"})

    def __init__(
        self,
        *,
        entity_repository: EntityRepository,
        evidence_repository: EvidenceRepository,
    ) -> None:
        self.entity_repository = entity_repository
        self.evidence_repository = evidence_repository
        self._info = SearchRetrieverInfo(
            name="structured",
            method=SearchMethod.STRUCTURED,
            description="Typed database retrieval for Entity and Evidence objects.",
            enabled=True,
            priority=50,
        )

    @property
    def info(self) -> SearchRetrieverInfo:
        return self._info

    def can_handle(self, query: InvestigationSearchQuery) -> bool:
        if query.case_id is None:
            return False

        requested = self._requested_object_types(query)
        if not requested:
            return False

        # AUTO text search must not silently turn into "return every entity".
        # Structured retrieval participates automatically only when the caller
        # supplies explicit structured input. An explicit STRUCTURED method may
        # request a broad typed listing such as object_types=("entity",).
        explicitly_structured = (
            SearchMethod.STRUCTURED in query.methods
            and SearchMethod.AUTO not in query.methods
        )

        return query.has_structured_input or explicitly_structured

    def retrieve(self, query: InvestigationSearchQuery) -> list[InvestigationSearchHit]:
        if not self.can_handle(query):
            return []

        requested = self._requested_object_types(query)
        filters = query.structured_filters
        hits: list[InvestigationSearchHit] = []

        if "entity" in requested:
            entity_types = self._entity_types(filters.entity_types)
            entities = self.entity_repository.search_case_structured(
                query.case_id,
                entity_types=entity_types,
                object_ids=query.object_ids,
                values=filters.values,
                normalized_values=filters.normalized_values,
                include_deleted=query.include_deleted,
                limit=query.candidate_limit,
            )
            hits.extend(self._entity_hit(entity, query) for entity in entities)

        if "evidence" in requested:
            evidence_types = self._evidence_types(filters.evidence_types)
            evidences = self.evidence_repository.search_case_structured(
                query.case_id,
                evidence_types=evidence_types,
                object_ids=query.object_ids,
                source_ids=filters.source_ids,
                values=filters.values,
                include_deleted=query.include_deleted,
                limit=query.candidate_limit,
            )
            hits.extend(self._evidence_hit(evidence, query) for evidence in evidences)

        # Repository ordering is deterministic per object type. A final stable
        # identity sort removes dependence on which repository was queried first
        # when both types participate and then enforces the retriever budget.
        hits.sort(
            key=lambda hit: (
                str(getattr(hit.source, "created_at", "")),
                hit.object_type,
                str(hit.object_id),
            ),
            reverse=True,
        )

        return hits[: query.candidate_limit]

    def _requested_object_types(self, query: InvestigationSearchQuery) -> set[str]:
        if query.object_types:
            return self.SUPPORTED_OBJECT_TYPES.intersection(query.object_types)

        filters = query.structured_filters
        requested: set[str] = set()
        if filters.entity_types or filters.normalized_values:
            requested.add("entity")
        if filters.evidence_types or filters.source_ids:
            requested.add("evidence")
        if filters.values or query.object_ids:
            requested.update(self.SUPPORTED_OBJECT_TYPES)
        return requested

    @staticmethod
    def _entity_types(values: tuple[str, ...]) -> tuple[EntityType, ...]:
        if not values:
            return ()
        try:
            return tuple(EntityType(value) for value in values)
        except ValueError as error:
            raise ValueError(f"Unknown structured entity type: {error}") from error

    @staticmethod
    def _evidence_types(values: tuple[str, ...]) -> tuple[EvidenceType, ...]:
        if not values:
            return ()
        try:
            return tuple(EvidenceType(value) for value in values)
        except ValueError as error:
            raise ValueError(f"Unknown structured evidence type: {error}") from error

    @staticmethod
    def _entity_hit(entity: Entity, query: InvestigationSearchQuery) -> InvestigationSearchHit:
        score = 1.0
        entity_type = entity.entity_type.value
        reason = SearchMatchReason(
            reason=f"Matched structured Entity filter ({entity_type}).",
            method=SearchMethod.STRUCTURED,
            score=score,
            details={
                "entity_type": entity_type,
                "normalized_value": entity.normalized_value,
            },
        )
        return InvestigationSearchHit(
            object_id=entity.id,
            object_type="entity",
            case_id=entity.case_id,
            title=f"{entity_type}: {entity.value}",
            snippet=entity.value,
            scores=SearchScores(structured=score, final=score),
            matched_methods=[SearchMethod.STRUCTURED],
            reasons=[reason],
            source=entity,
            metadata={
                "entity_type": entity_type,
                "value": entity.value,
                "normalized_value": entity.normalized_value,
                "confidence": entity.confidence,
                "structured_filters": {
                    "entity_types": list(query.structured_filters.entity_types),
                },
            },
        )

    @staticmethod
    def _evidence_hit(evidence: Evidence, query: InvestigationSearchQuery) -> InvestigationSearchHit:
        score = 1.0
        evidence_type = evidence.evidence_type.value
        snippet = evidence.value or evidence.file_path or evidence.title
        reason = SearchMatchReason(
            reason=f"Matched structured Evidence filter ({evidence_type}).",
            method=SearchMethod.STRUCTURED,
            score=score,
            details={
                "evidence_type": evidence_type,
                "source_id": str(evidence.source_id),
            },
        )
        return InvestigationSearchHit(
            object_id=evidence.id,
            object_type="evidence",
            case_id=evidence.case_id,
            title=evidence.title,
            snippet=snippet,
            scores=SearchScores(structured=score, final=score),
            matched_methods=[SearchMethod.STRUCTURED],
            reasons=[reason],
            source=evidence,
            metadata={
                "evidence_type": evidence_type,
                "value": evidence.value,
                "source_id": str(evidence.source_id),
                "sha256": evidence.sha256,
                "structured_filters": {
                    "evidence_types": list(query.structured_filters.evidence_types),
                },
            },
        )

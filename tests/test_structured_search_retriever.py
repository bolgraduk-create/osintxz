"""Block 10.10 regression tests for typed Structured Retrieval."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.investigation.search_query import (
    InvestigationSearchQuery,
    SearchMethod,
    StructuredSearchFilters,
)
from app.investigation.search_result import InvestigationSearchHit, SearchScores
from app.models.entity import EntityType
from app.models.evidence import EvidenceType
from app.services.search_retriever import SearchRetriever, SearchRetrieverInfo
from app.services.structured_search_retriever import StructuredSearchRetriever
from app.services.unified_search_service import UnifiedSearchService


class FakeEntityRepository:
    def __init__(self, entities=()):
        self.entities = list(entities)
        self.calls = []

    def search_case_structured(self, case_id, **kwargs):
        self.calls.append((case_id, kwargs))
        result = [item for item in self.entities if item.case_id == case_id]
        types = kwargs.get("entity_types") or ()
        ids = kwargs.get("object_ids") or ()
        values = kwargs.get("values") or ()
        normalized = kwargs.get("normalized_values") or ()
        if types:
            result = [item for item in result if item.entity_type in types]
        if ids:
            result = [item for item in result if item.id in ids]
        if values:
            result = [item for item in result if item.value in values]
        if normalized:
            result = [item for item in result if item.normalized_value in normalized]
        return result[: kwargs.get("limit", 200)]


class FakeEvidenceRepository:
    def __init__(self, evidences=()):
        self.evidences = list(evidences)
        self.calls = []

    def search_case_structured(self, case_id, **kwargs):
        self.calls.append((case_id, kwargs))
        result = [item for item in self.evidences if item.case_id == case_id]
        types = kwargs.get("evidence_types") or ()
        ids = kwargs.get("object_ids") or ()
        source_ids = kwargs.get("source_ids") or ()
        values = kwargs.get("values") or ()
        if types:
            result = [item for item in result if item.evidence_type in types]
        if ids:
            result = [item for item in result if item.id in ids]
        if source_ids:
            result = [item for item in result if item.source_id in source_ids]
        if values:
            result = [item for item in result if item.value in values]
        return result[: kwargs.get("limit", 200)]


def _entity(case_id, entity_type, value, normalized=None):
    return SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=entity_type,
        value=value,
        normalized_value=normalized or value,
        confidence=0.95,
        created_at="2026-08-30T10:00:00",
        deleted_at=None,
    )


def _evidence(case_id, source_id, evidence_type, value):
    return SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        source_id=source_id,
        evidence_type=evidence_type,
        title=f"Evidence {evidence_type.value}",
        value=value,
        file_path=None,
        sha256=None,
        created_at="2026-08-30T10:00:00",
        deleted_at=None,
    )


def _retriever(entities=(), evidences=()):
    return StructuredSearchRetriever(
        entity_repository=FakeEntityRepository(entities),
        evidence_repository=FakeEvidenceRepository(evidences),
    )


def test_structured_filters_are_normalized_and_make_empty_text_query_usable():
    query = InvestigationSearchQuery(
        case_id=uuid4(),
        object_types=(" ENTITY ",),
        methods=(SearchMethod.STRUCTURED,),
        structured_filters=StructuredSearchFilters(
            entity_types=("BANK_CARD", " bank_card "),
        ),
    )

    assert query.object_types == ("entity",)
    assert query.structured_filters.entity_types == ("bank_card",)
    assert query.has_structured_input is True
    assert query.is_empty is False


def test_structured_entity_type_filter_returns_only_bank_card_entities():
    case_id = uuid4()
    phone = _entity(case_id, EntityType.PHONE, "+380671234567", "380671234567")
    card = _entity(case_id, EntityType.BANK_CARD, "1234 5678 9012 3452", "1234567890123452")
    retriever = _retriever((phone, card))

    query = InvestigationSearchQuery(
        case_id=case_id,
        object_types=("entity",),
        methods=(SearchMethod.STRUCTURED,),
        structured_filters=StructuredSearchFilters(entity_types=("bank_card",)),
    )

    hits = retriever.retrieve(query)

    assert len(hits) == 1
    hit = hits[0]
    assert hit.object_id == card.id
    assert hit.object_type == "entity"
    assert hit.scores.structured == 1.0
    assert hit.matched_methods == [SearchMethod.STRUCTURED]
    assert hit.metadata["entity_type"] == "bank_card"
    assert hit.source is card


def test_structured_evidence_filters_use_type_and_source_scope():
    case_id = uuid4()
    source_a = uuid4()
    source_b = uuid4()
    first = _evidence(case_id, source_a, EvidenceType.MESSAGE, "message A")
    second = _evidence(case_id, source_b, EvidenceType.MESSAGE, "message B")
    retriever = _retriever(evidences=(first, second))

    query = InvestigationSearchQuery(
        case_id=case_id,
        object_types=("evidence",),
        methods=(SearchMethod.STRUCTURED,),
        structured_filters=StructuredSearchFilters(
            evidence_types=("message",),
            source_ids=(source_a,),
        ),
    )

    hits = retriever.retrieve(query)

    assert [hit.object_id for hit in hits] == [first.id]
    assert hits[0].metadata["source_id"] == str(source_a)


def test_auto_text_query_does_not_dump_all_entities_without_structured_input():
    retriever = _retriever()
    query = InvestigationSearchQuery(
        query="show bank cards",
        case_id=uuid4(),
        methods=(SearchMethod.AUTO,),
    )

    assert retriever.can_handle(query) is False
    assert retriever.supports(query) is False


def test_explicit_structured_object_listing_can_run_without_text():
    case_id = uuid4()
    phone = _entity(case_id, EntityType.PHONE, "+380671234567", "380671234567")
    retriever = _retriever((phone,))
    query = InvestigationSearchQuery(
        case_id=case_id,
        object_types=("entity",),
        methods=(SearchMethod.STRUCTURED,),
    )

    assert retriever.supports(query) is True
    assert [hit.object_id for hit in retriever.retrieve(query)] == [phone.id]


class DuplicateLexicalRetriever(SearchRetriever):
    def __init__(self, hit):
        self.hit = hit
        self._info = SearchRetrieverInfo(
            name="test_lexical",
            method=SearchMethod.LEXICAL,
            priority=100,
        )

    @property
    def info(self):
        return self._info

    def can_handle(self, query):
        return query.has_text_query

    def retrieve(self, query):
        return [self.hit]


def test_unified_search_fuses_structured_and_lexical_identity():
    case_id = uuid4()
    card = _entity(case_id, EntityType.BANK_CARD, "1234 5678 9012 3452", "1234567890123452")
    structured = _retriever((card,))
    lexical_hit = InvestigationSearchHit(
        object_id=card.id,
        object_type="entity",
        case_id=case_id,
        title="indexed card",
        snippet=card.value,
        scores=SearchScores(lexical=0.9, final=0.9),
        matched_methods=[SearchMethod.LEXICAL],
        source=SimpleNamespace(content=card.value, title="indexed card"),
    )

    service = UnifiedSearchService(
        retrievers=[structured, DuplicateLexicalRetriever(lexical_hit)]
    )
    query = InvestigationSearchQuery(
        query="1234 5678 9012 3452",
        case_id=case_id,
        object_types=("entity",),
        structured_filters=StructuredSearchFilters(entity_types=("bank_card",)),
        enable_query_expansion=False,
        enable_reranking=False,
        enable_neural_reranking=False,
    )

    response = service.search(query)

    assert len(response.hits) == 1
    hit = response.hits[0]
    assert set(hit.matched_methods) == {SearchMethod.STRUCTURED, SearchMethod.LEXICAL}
    assert hit.scores.structured == 1.0
    assert hit.scores.lexical == 0.9
    assert hit.scores.fusion == 1.0


def test_unknown_structured_entity_type_fails_fast_at_retriever_boundary():
    retriever = _retriever()
    query = InvestigationSearchQuery(
        case_id=uuid4(),
        object_types=("entity",),
        methods=(SearchMethod.STRUCTURED,),
        structured_filters=StructuredSearchFilters(entity_types=("not_a_real_type",)),
    )

    try:
        retriever.retrieve(query)
    except ValueError as error:
        assert "Unknown structured entity type" in str(error)
    else:
        raise AssertionError("Unknown structured entity type must be rejected")

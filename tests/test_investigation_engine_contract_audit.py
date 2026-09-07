from __future__ import annotations

from uuid import uuid4

from app.application.investigation_analysis_contracts import (
    CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER,
    INVESTIGATION_ANALYSIS_STAGE_DEPENDENCIES,
)
from app.investigation.search_query import InvestigationSearchQuery, SearchMethod
from app.investigation.search_result import (
    InvestigationSearchHit,
    InvestigationSearchResponse,
    SearchMatchReason,
    SearchScores,
)
from app.models.search_index import SearchObjectType
from app.services.investigation_rag_retrieval_service import InvestigationRAGRetrievalService


class FakeUnifiedSearchService:
    def __init__(self, response: InvestigationSearchResponse):
        self.response = response
        self.received_query = None

    def search(self, query: InvestigationSearchQuery) -> InvestigationSearchResponse:
        self.received_query = query
        return self.response


def test_analysis_stage_order_is_unique_and_dependencies_precede_consumers():
    order = CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER
    assert len(order) == len(set(order))
    positions = {stage: index for index, stage in enumerate(order)}
    for stage, dependencies in INVESTIGATION_ANALYSIS_STAGE_DEPENDENCIES.items():
        assert stage in positions
        for dependency in dependencies:
            assert dependency in positions
            assert positions[dependency] < positions[stage]


def test_search_method_contract_contains_structured_retrieval_slot():
    assert {item.value for item in SearchMethod} == {
        "auto", "structured", "lexical", "fuzzy", "semantic", "image"
    }


def test_search_object_types_match_persisted_search_index_vocabulary():
    assert {item.value for item in SearchObjectType} == {
        "message", "document", "evidence", "entity", "artifact", "report", "note"
    }


def test_search_hit_identity_is_case_type_object_and_normalized():
    case_id = uuid4()
    object_id = uuid4()
    hit = InvestigationSearchHit(
        object_id=object_id,
        object_type="ENTITY",
        case_id=case_id,
        scores=SearchScores(structured=1.0, final=1.0),
    )
    assert hit.object_type == "entity"
    assert hit.identity_key == (case_id, "entity", object_id)


def test_search_response_preserves_original_query_contract():
    query = InvestigationSearchQuery(
        query="bank cards",
        case_id=uuid4(),
        object_types=("entity",),
        methods=(SearchMethod.STRUCTURED,),
    )
    response = InvestigationSearchResponse(query=query)
    assert response.query is query
    assert response.query.object_types == ("entity",)
    assert response.query.methods == (SearchMethod.STRUCTURED,)


def test_rag_bridge_preserves_search_identity_source_and_provenance():
    case_id = uuid4()
    object_id = uuid4()
    opaque_source = object()
    query = InvestigationSearchQuery(query="phone", case_id=case_id)
    hit = InvestigationSearchHit(
        object_id=object_id,
        object_type="ENTITY",
        case_id=case_id,
        title="PHONE",
        snippet="+380671234567",
        scores=SearchScores(lexical=0.8, final=0.9),
        matched_methods=[SearchMethod.LEXICAL],
        reasons=[SearchMatchReason(reason="exact value", method=SearchMethod.LEXICAL, score=0.8)],
        source=opaque_source,
        metadata={"entity_type": "phone"},
    )
    response = InvestigationSearchResponse(
        query=query,
        hits=[hit],
        candidate_count=1,
        total_matches=1,
    )
    fake = FakeUnifiedSearchService(response)
    service = InvestigationRAGRetrievalService(unified_search_service=fake)  # type: ignore[arg-type]
    result = service.retrieve_query(query)

    assert fake.received_query is query
    assert result.source_count == 1
    source = result.sources[0]
    assert source.reference_id == "R1"
    assert source.object_id == object_id
    assert source.object_type == "entity"
    assert source.case_id == case_id
    assert source.source is opaque_source
    assert source.metadata == {"entity_type": "phone"}
    assert source.matched_methods == ("lexical",)
    assert source.reasons[0].reason == "exact value"


def test_scores_reject_values_outside_normalized_contract():
    try:
        SearchScores(final=1.01)
    except ValueError:
        pass
    else:
        raise AssertionError("SearchScores accepted a value above 1.0")

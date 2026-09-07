from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from app.investigation.search_query import InvestigationSearchQuery, SearchMethod
from app.investigation.search_result import InvestigationSearchHit, SearchMatchReason, SearchScores
from app.services.search_confidence_service import SearchConfidenceService
from app.services.search_explanation_service import SearchExplanationService
from app.services.search_retriever import SearchRetriever, SearchRetrieverInfo
from app.services.unified_search_service import UnifiedSearchService


@dataclass
class SourceStub:
    confidence: float | None = None
    source_id: UUID | None = None
    sha256: str | None = None
    checksum: str | None = None


class StubRetriever(SearchRetriever):
    def __init__(self, hit: InvestigationSearchHit) -> None:
        self.hit = hit
        self._info = SearchRetrieverInfo(
            name="confidence-test",
            method=SearchMethod.LEXICAL,
            description="confidence/explanation test retriever",
            enabled=True,
            priority=10,
        )

    @property
    def info(self) -> SearchRetrieverInfo:
        return self._info

    def can_handle(self, query: InvestigationSearchQuery) -> bool:
        return query.case_id is not None and query.has_text_query

    def retrieve(self, query: InvestigationSearchQuery) -> list[InvestigationSearchHit]:
        return [self.hit]


class FailingConfidenceService:
    def annotate(self, hits):
        raise RuntimeError("confidence boom")


class FailingExplanationService:
    def annotate(self, hits):
        raise RuntimeError("explanation boom")


class PassthroughAnnotationService:
    """Control service used to isolate annotation effects from search ranking."""

    def annotate(self, hits):
        return hits


def make_hit(
    *,
    score: float = 0.8,
    source: object | None = None,
    metadata: dict | None = None,
) -> InvestigationSearchHit:
    case_id = uuid4()
    return InvestigationSearchHit(
        object_id=uuid4(),
        object_type="evidence",
        case_id=case_id,
        title="Evidence",
        snippet="example",
        scores=SearchScores(lexical=score, fusion=0.7, rerank=0.6, final=0.6),
        matched_methods=[SearchMethod.LEXICAL],
        reasons=[
            SearchMatchReason(
                reason="Exact token match",
                method=SearchMethod.LEXICAL,
                score=score,
                details={"field": "value"},
            )
        ],
        source=source,
        metadata=dict(metadata or {}),
    )


def make_query(case_id: UUID) -> InvestigationSearchQuery:
    return InvestigationSearchQuery(
        query="example",
        case_id=case_id,
        methods=(SearchMethod.AUTO,),
        enable_query_expansion=False,
        enable_reranking=False,
        enable_neural_reranking=False,
    )


def test_confidence_is_separate_from_relevance_score() -> None:
    source = SourceStub(source_id=uuid4(), sha256="a" * 64)
    low = make_hit(score=0.10, source=source, metadata={"source_id": str(source.source_id), "sha256": source.sha256})
    high = make_hit(score=0.99, source=source, metadata={"source_id": str(source.source_id), "sha256": source.sha256})

    service = SearchConfidenceService()
    low_breakdown = service.calculate(low)
    high_breakdown = service.calculate(high)

    assert low_breakdown.confidence == pytest.approx(high_breakdown.confidence)
    assert low.scores.lexical == pytest.approx(0.10)
    assert high.scores.lexical == pytest.approx(0.99)


def test_source_integrity_and_object_confidence_are_explained() -> None:
    source = SourceStub(confidence=0.85, source_id=uuid4(), sha256="b" * 64)
    hit = make_hit(
        source=source,
        metadata={
            "source_id": str(source.source_id),
            "sha256": source.sha256,
            "confidence": 0.85,
            "evidence_support_count": 2,
        },
    )

    SearchConfidenceService().annotate([hit])
    payload = hit.metadata["evidence_confidence"]

    assert hit.scores.evidence is not None
    assert hit.scores.confidence is not None
    assert payload["object_confidence"] == pytest.approx(0.85)
    assert payload["source_integrity"] == pytest.approx(1.0)
    assert payload["support_strength"] == pytest.approx(0.80)
    assert payload["provenance_completeness"] == pytest.approx(1.0)


def test_explanation_contains_identity_methods_reasons_scores_and_confidence() -> None:
    source = SourceStub(source_id=uuid4())
    hit = make_hit(source=source, metadata={"source_id": str(source.source_id)})
    SearchConfidenceService().annotate([hit])
    SearchExplanationService().annotate([hit])

    explanation = hit.metadata["search_explanation"]
    assert explanation["identity"]["object_id"] == str(hit.object_id)
    assert explanation["matched_methods"] == ["lexical"]
    assert explanation["reasons"][0]["reason"] == "Exact token match"
    assert explanation["reasons"][0]["details"]["field"] == "value"
    assert explanation["scores"]["lexical"] == pytest.approx(0.8)
    assert explanation["confidence"]["confidence"] == pytest.approx(hit.scores.confidence)
    assert "matched by lexical" in explanation["summary"]


def test_unified_search_adds_confidence_and_explanation_without_changing_final_relevance() -> None:
    source = SourceStub(source_id=uuid4(), checksum="checksum")
    original_hit = make_hit(
        source=source,
        metadata={
            "source_id": str(source.source_id),
            "checksum": source.checksum,
        },
    )

    # The complete UnifiedSearch pipeline is allowed to change ``scores.final``
    # during fusion/ranking. Therefore the correct control is the *same* search
    # pipeline with no-op annotation services, not the raw pre-fusion stub score.
    control_hit = deepcopy(original_hit)
    annotated_hit = deepcopy(original_hit)

    control_service = UnifiedSearchService(
        retrievers=[StubRetriever(control_hit)],
        search_confidence_service=PassthroughAnnotationService(),
        search_explanation_service=PassthroughAnnotationService(),
    )
    control_response = control_service.search(make_query(control_hit.case_id))

    service = UnifiedSearchService(retrievers=[StubRetriever(annotated_hit)])
    response = service.search(make_query(annotated_hit.case_id))

    assert control_response.returned_count == 1
    assert response.returned_count == 1

    control_final = control_response.hits[0].scores.final
    result = response.hits[0]

    assert result.scores.final == pytest.approx(control_final)
    assert result.scores.confidence is not None
    assert "evidence_confidence" in result.metadata
    assert "search_explanation" in result.metadata
    assert response.metadata["confidence_scoring"]["applied"] is True
    assert response.metadata["confidence_scoring"]["relevance_is_confidence"] is False
    assert response.metadata["explainability"]["applied"] is True


def test_confidence_failure_is_isolated_and_explanation_still_runs() -> None:
    hit = make_hit()
    service = UnifiedSearchService(
        retrievers=[StubRetriever(hit)],
        search_confidence_service=FailingConfidenceService(),
    )
    response = service.search(make_query(hit.case_id))

    assert response.returned_count == 1
    assert response.metadata["confidence_scoring"]["applied"] is False
    assert response.metadata["explainability"]["applied"] is True
    assert any("confidence annotation failed" in warning.lower() for warning in response.warnings)


def test_explanation_failure_is_isolated_and_confidence_survives() -> None:
    hit = make_hit()
    service = UnifiedSearchService(
        retrievers=[StubRetriever(hit)],
        search_explanation_service=FailingExplanationService(),
    )
    response = service.search(make_query(hit.case_id))

    assert response.returned_count == 1
    assert response.hits[0].scores.confidence is not None
    assert response.metadata["confidence_scoring"]["applied"] is True
    assert response.metadata["explainability"]["applied"] is False
    assert any("explanation annotation failed" in warning.lower() for warning in response.warnings)


def test_support_strength_is_conservative_and_monotonic() -> None:
    service = SearchConfidenceService()
    scores = []
    for count in (0, 1, 2, 3):
        hit = make_hit(metadata={"evidence_support_count": count})
        scores.append(service.calculate(hit).support_strength)

    assert scores == [0.0, 0.6, 0.8, 1.0]

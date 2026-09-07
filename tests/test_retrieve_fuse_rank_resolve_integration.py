from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from app.investigation.search_query import InvestigationSearchQuery, SearchMethod
from app.investigation.search_result import InvestigationSearchHit, SearchMatchReason, SearchScores
from app.services.search_retriever import SearchRetriever, SearchRetrieverInfo
from app.services.unified_search_service import UnifiedSearchService


class StubRetriever(SearchRetriever):
    def __init__(
        self,
        *,
        name: str,
        method: SearchMethod,
        hits: list[InvestigationSearchHit] | None = None,
        error: Exception | None = None,
        priority: int = 100,
    ) -> None:
        self._info = SearchRetrieverInfo(
            name=name,
            method=method,
            description="integration-test retriever",
            enabled=True,
            priority=priority,
        )
        self._hits = list(hits or [])
        self._error = error

    @property
    def info(self) -> SearchRetrieverInfo:
        return self._info

    def can_handle(self, query: InvestigationSearchQuery) -> bool:
        return query.case_id is not None and (
            query.has_text_query or method_is_structured(self.method)
        )

    def retrieve(self, query: InvestigationSearchQuery) -> list[InvestigationSearchHit]:
        if self._error is not None:
            raise self._error
        return list(self._hits)


def method_is_structured(method: SearchMethod) -> bool:
    return method == SearchMethod.STRUCTURED


def make_hit(
    *,
    case_id: UUID,
    object_id: UUID,
    method: SearchMethod,
    score: float,
    object_type: str = "entity",
    title: str = "",
    snippet: str = "",
    source: object | None = None,
    metadata: dict | None = None,
) -> InvestigationSearchHit:
    scores = SearchScores()
    setattr(scores, method.value, score)
    return InvestigationSearchHit(
        object_id=object_id,
        object_type=object_type,
        case_id=case_id,
        title=title,
        snippet=snippet,
        scores=scores,
        matched_methods=[method],
        reasons=[
            SearchMatchReason(
                reason=f"matched by {method.value}",
                method=method,
                score=score,
            )
        ],
        source=source,
        metadata=dict(metadata or {}),
    )


def build_query(case_id: UUID, *, rerank: bool = False, limit: int = 50) -> InvestigationSearchQuery:
    return InvestigationSearchQuery(
        query="alice 380671234567",
        case_id=case_id,
        methods=(SearchMethod.AUTO,),
        limit=limit,
        candidate_limit=max(50, limit),
        enable_query_expansion=False,
        enable_reranking=rerank,
        enable_neural_reranking=False,
    )


def test_same_object_from_four_methods_resolves_to_one_unified_hit() -> None:
    case_id = uuid4()
    object_id = uuid4()
    source = {"origin": "telegram-message"}

    service = UnifiedSearchService(
        retrievers=[
            StubRetriever(
                name="structured-test",
                method=SearchMethod.STRUCTURED,
                hits=[make_hit(case_id=case_id, object_id=object_id, method=SearchMethod.STRUCTURED, score=1.0, title="Alice", source=source, metadata={"structured_marker": True})],
            ),
            StubRetriever(
                name="lexical-test",
                method=SearchMethod.LEXICAL,
                hits=[make_hit(case_id=case_id, object_id=object_id, method=SearchMethod.LEXICAL, score=0.92, snippet="alice 380671234567", metadata={"lexical_marker": True})],
            ),
            StubRetriever(
                name="fuzzy-test",
                method=SearchMethod.FUZZY,
                hits=[make_hit(case_id=case_id, object_id=object_id, method=SearchMethod.FUZZY, score=0.86)],
            ),
            StubRetriever(
                name="semantic-test",
                method=SearchMethod.SEMANTIC,
                hits=[make_hit(case_id=case_id, object_id=object_id, method=SearchMethod.SEMANTIC, score=0.81)],
            ),
        ]
    )

    response = service.search(build_query(case_id))

    assert response.returned_count == 1
    hit = response.hits[0]
    assert hit.identity_key == (case_id, "entity", object_id)
    assert set(hit.matched_methods) == {
        SearchMethod.STRUCTURED,
        SearchMethod.LEXICAL,
        SearchMethod.FUZZY,
        SearchMethod.SEMANTIC,
    }
    assert hit.scores.structured == pytest.approx(1.0)
    assert hit.scores.lexical == pytest.approx(0.92)
    assert hit.scores.fuzzy == pytest.approx(0.86)
    assert hit.scores.semantic == pytest.approx(0.81)
    assert hit.scores.fusion == pytest.approx(1.0)
    assert hit.source is source
    assert hit.metadata["structured_marker"] is True
    assert hit.metadata["lexical_marker"] is True
    assert len(hit.reasons) == 4


def test_rrf_consensus_outranks_single_method_candidate() -> None:
    case_id = uuid4()
    consensus_id = uuid4()
    single_id = uuid4()

    service = UnifiedSearchService(
        retrievers=[
            StubRetriever(
                name="structured-test",
                method=SearchMethod.STRUCTURED,
                hits=[
                    make_hit(case_id=case_id, object_id=consensus_id, method=SearchMethod.STRUCTURED, score=0.80),
                    make_hit(case_id=case_id, object_id=single_id, method=SearchMethod.STRUCTURED, score=1.0),
                ],
            ),
            StubRetriever(
                name="lexical-test",
                method=SearchMethod.LEXICAL,
                hits=[make_hit(case_id=case_id, object_id=consensus_id, method=SearchMethod.LEXICAL, score=0.75)],
            ),
            StubRetriever(
                name="semantic-test",
                method=SearchMethod.SEMANTIC,
                hits=[make_hit(case_id=case_id, object_id=consensus_id, method=SearchMethod.SEMANTIC, score=0.70)],
            ),
        ]
    )

    response = service.search(build_query(case_id))

    assert [hit.object_id for hit in response.hits[:2]] == [consensus_id, single_id]
    assert response.hits[0].scores.fusion > response.hits[1].scores.fusion


def test_full_mathematical_pipeline_preserves_scores_and_is_deterministic() -> None:
    case_id = uuid4()
    first_id = UUID("00000000-0000-0000-0000-000000000011")
    second_id = UUID("00000000-0000-0000-0000-000000000022")

    def make_service() -> UnifiedSearchService:
        return UnifiedSearchService(
            retrievers=[
                StubRetriever(
                    name="lexical-test",
                    method=SearchMethod.LEXICAL,
                    hits=[
                        make_hit(case_id=case_id, object_id=first_id, method=SearchMethod.LEXICAL, score=0.95, title="alice", snippet="alice 380671234567"),
                        make_hit(case_id=case_id, object_id=second_id, method=SearchMethod.LEXICAL, score=0.70, title="other", snippet="unrelated value"),
                    ],
                ),
                StubRetriever(
                    name="semantic-test",
                    method=SearchMethod.SEMANTIC,
                    hits=[make_hit(case_id=case_id, object_id=first_id, method=SearchMethod.SEMANTIC, score=0.84, title="alice")],
                ),
            ]
        )

    query = build_query(case_id, rerank=True)
    first = make_service().search(query)
    second = make_service().search(query)

    assert [hit.object_id for hit in first.hits] == [hit.object_id for hit in second.hits]
    assert first.metadata["fusion"] == "rrf"
    assert first.metadata["ranking"] == "mathematical"
    for hit in first.hits:
        assert hit.scores.fusion is not None
        assert hit.scores.rerank is not None
        assert 0.0 <= hit.scores.fusion <= 1.0
        assert 0.0 <= hit.scores.rerank <= 1.0
        assert 0.0 <= hit.scores.final <= 1.0
        assert "mathematical_ranking" in hit.metadata


def test_retriever_failure_is_isolated_and_other_results_survive() -> None:
    case_id = uuid4()
    object_id = uuid4()

    service = UnifiedSearchService(
        retrievers=[
            StubRetriever(name="broken", method=SearchMethod.FUZZY, error=RuntimeError("boom")),
            StubRetriever(
                name="lexical-test",
                method=SearchMethod.LEXICAL,
                hits=[make_hit(case_id=case_id, object_id=object_id, method=SearchMethod.LEXICAL, score=0.9)],
            ),
        ]
    )

    response = service.search(build_query(case_id))

    assert response.returned_count == 1
    assert response.hits[0].object_id == object_id
    assert any("broken" in error and "boom" in error for error in response.errors)


def test_unified_boundary_discards_hit_from_another_case() -> None:
    active_case = uuid4()
    foreign_case = uuid4()
    allowed_id = uuid4()
    foreign_id = uuid4()

    service = UnifiedSearchService(
        retrievers=[
            StubRetriever(
                name="scope-test",
                method=SearchMethod.LEXICAL,
                hits=[
                    make_hit(case_id=active_case, object_id=allowed_id, method=SearchMethod.LEXICAL, score=0.8),
                    make_hit(case_id=foreign_case, object_id=foreign_id, method=SearchMethod.LEXICAL, score=1.0),
                ],
            )
        ]
    )

    response = service.search(build_query(active_case))

    assert [hit.object_id for hit in response.hits] == [allowed_id]
    assert all(hit.case_id == active_case for hit in response.hits)
    assert any("outside the active case scope" in warning for warning in response.warnings)


def test_unified_boundary_discards_unscoped_hit_for_case_query() -> None:
    active_case = uuid4()
    object_id = uuid4()
    hit = make_hit(case_id=active_case, object_id=object_id, method=SearchMethod.LEXICAL, score=0.9)
    hit.case_id = None

    service = UnifiedSearchService(
        retrievers=[StubRetriever(name="unscoped", method=SearchMethod.LEXICAL, hits=[hit])]
    )

    response = service.search(build_query(active_case))

    assert response.hits == []
    assert response.total_matches == 0
    assert any("outside the active case scope" in warning for warning in response.warnings)


def test_final_limit_is_applied_after_unified_ordering() -> None:
    case_id = uuid4()
    ids = [uuid4() for _ in range(4)]

    service = UnifiedSearchService(
        retrievers=[
            StubRetriever(
                name="lexical-test",
                method=SearchMethod.LEXICAL,
                hits=[
                    make_hit(case_id=case_id, object_id=ids[0], method=SearchMethod.LEXICAL, score=0.95),
                    make_hit(case_id=case_id, object_id=ids[1], method=SearchMethod.LEXICAL, score=0.90),
                    make_hit(case_id=case_id, object_id=ids[2], method=SearchMethod.LEXICAL, score=0.85),
                    make_hit(case_id=case_id, object_id=ids[3], method=SearchMethod.LEXICAL, score=0.80),
                ],
            )
        ]
    )

    response = service.search(build_query(case_id, limit=2))

    assert response.total_matches == 4
    assert response.returned_count == 2
    assert response.hits[0].final_score >= response.hits[1].final_score


def test_duplicate_inside_one_method_does_not_gain_extra_rrf_influence() -> None:
    case_id = uuid4()
    duplicate_id = uuid4()
    peer_id = uuid4()

    service = UnifiedSearchService(
        retrievers=[
            StubRetriever(
                name="lexical-a",
                method=SearchMethod.LEXICAL,
                hits=[
                    make_hit(case_id=case_id, object_id=duplicate_id, method=SearchMethod.LEXICAL, score=0.90),
                    make_hit(case_id=case_id, object_id=peer_id, method=SearchMethod.LEXICAL, score=0.85),
                ],
                priority=10,
            ),
            StubRetriever(
                name="lexical-b",
                method=SearchMethod.LEXICAL,
                hits=[make_hit(case_id=case_id, object_id=duplicate_id, method=SearchMethod.LEXICAL, score=0.99)],
                priority=20,
            ),
        ]
    )

    response = service.search(build_query(case_id))

    assert response.returned_count == 2
    duplicate = next(hit for hit in response.hits if hit.object_id == duplicate_id)
    assert duplicate.scores.lexical == pytest.approx(0.99)
    # The duplicate is merged and contributes only once to the LEXICAL ranking.
    assert len([m for m in duplicate.matched_methods if m == SearchMethod.LEXICAL]) == 1

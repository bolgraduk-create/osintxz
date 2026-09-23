from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.analysis.graph_explainability import (
    GraphEntityExplanation,
    GraphMetricRank,
    GraphPairExplanation,
)
from app.entity_resolution.contracts import (
    EntityResolutionDecision,
    EntityResolutionReason,
    EntityResolutionResult,
    EntityResolutionSignalDirection,
)
from app.investigation.explainability import (
    InvestigationExplainabilityBundle,
    InvestigationExplanationDomain,
    InvestigationExplanationQuestion,
)
from app.investigation.search_result import (
    InvestigationSearchHit,
    SearchMatchReason,
    SearchScores,
)
from app.investigation.search_query import SearchMethod
from app.models.entity_merge import EntityMerge
from app.services.investigation_explainability_service import (
    InvestigationExplainabilityService,
)
from app.services.investigation_rag_retrieval_service import (
    InvestigationRAGRetrievalService,
)


def _search_hit():
    case_id = uuid4()
    object_id = uuid4()
    hit = InvestigationSearchHit(
        object_id=object_id,
        object_type="message",
        case_id=case_id,
        title="Message",
        snippet="Alice observed in the source material.",
        scores=SearchScores(
            lexical=0.91,
            fusion=0.63,
            rerank=0.77,
            confidence=0.42,
            final=0.77,
        ),
        matched_methods=[SearchMethod.LEXICAL],
        reasons=[
            SearchMatchReason(
                reason="Exact token match",
                method=SearchMethod.LEXICAL,
                score=0.91,
                details={"field": "text"},
            )
        ],
        metadata={
            "search_explanation": {
                "summary": "matched by lexical; rerank=0.770",
                "matched_methods": ["lexical"],
                "reasons": [
                    {
                        "reason": "Exact token match",
                        "method": "lexical",
                        "score": 0.91,
                        "details": {"field": "text"},
                    }
                ],
                "ranking": {
                    "score": 0.77,
                    "signals": {"text": 0.91},
                },
            },
            "mathematical_ranking": {
                "score": 0.77,
                "signals": {"text": 0.91},
            },
        },
    )
    return hit


def _canonical_evidence_payload():
    return {
        "version": "m024b",
        "scope": "proposition_support",
        "proposition_count": 1,
        "strongest_confidence": 0.84,
        "strongest_assessment_coverage": 0.77,
        "ranking_unchanged": True,
        "propositions": [
            {
                "proposition_key": "entity_observed:example",
                "confidence_score": 0.84,
                "assessment_coverage": 0.77,
                "hard_conflict": False,
                "explanation": {
                    "version": "m025a",
                    "propositionKey": "entity_observed:example",
                    "summary": (
                        "Canonical proposition confidence is 84% with "
                        "77% assessment coverage."
                    ),
                    "reasons": [
                        {
                            "code": "verified_independence",
                            "category": "independence",
                            "effect": "support",
                            "message": "Independent provenance is verified.",
                            "value": 1.0,
                            "coverage": 1.0,
                            "details": {},
                        }
                    ],
                    "limitations": [
                        {
                            "code": "assessment_incomplete",
                            "category": "coverage",
                            "effect": "uncertainty",
                            "message": "Assessment coverage is incomplete.",
                            "value": None,
                            "coverage": 0.77,
                            "details": {},
                        }
                    ],
                },
            }
        ],
    }


def test_unified_search_contract_answers_why_found_and_why_ranked_separately():
    hit = _search_hit()

    bundle = InvestigationExplainabilityService().explain_search_hit(hit)

    found = bundle.for_question(
        InvestigationExplanationQuestion.FOUND
    )
    ranked = bundle.for_question(
        InvestigationExplanationQuestion.RANKED
    )

    assert len(found) == 1
    assert len(ranked) == 1
    assert found[0].domain == InvestigationExplanationDomain.SEARCH
    assert ranked[0].domain == InvestigationExplanationDomain.SEARCH
    assert "Exact token match" in found[0].reasons[0].message
    assert "explains retrieval, not whether" in found[0].summary
    assert found[0].metadata["retrievalRelevanceIsEvidenceConfidence"] is False
    assert "not Evidence confidence" in ranked[0].summary
    assert ranked[0].metadata["rankingChangedByExplainability"] is False


def test_canonical_evidence_explanation_uses_same_unified_contract():
    hit = _search_hit()
    hit.metadata[
        "canonical_evidence_confidence"
    ] = _canonical_evidence_payload()

    bundle = InvestigationExplainabilityService().explain_search_hit(hit)

    confident = bundle.for_question(
        InvestigationExplanationQuestion.CONFIDENT
    )

    assert len(confident) == 1
    assert confident[0].domain == InvestigationExplanationDomain.EVIDENCE
    assert confident[0].metadata["confidence"] == pytest.approx(0.84)
    assert confident[0].metadata["coverage"] == pytest.approx(0.77)
    assert confident[0].metadata["generalSourceTruthScore"] is False
    assert confident[0].reasons[0].code == "verified_independence"
    assert confident[0].limitations[0].code == "assessment_incomplete"


def test_entity_resolution_is_explained_as_resolution_not_as_merge():
    first = uuid4()
    second = uuid4()
    result = EntityResolutionResult(
        first_entity_id=first,
        second_entity_id=second,
        decision=EntityResolutionDecision.MATCH,
        identity_score=0.86,
        confidence=0.82,
        support_score=0.89,
        contradiction_score=0.12,
        reasons=[
            EntityResolutionReason(
                code="email_match",
                message="Normalized email values match.",
                direction=EntityResolutionSignalDirection.SUPPORT,
                score=1.0,
            ),
            EntityResolutionReason(
                code="name_conflict",
                message="One name signal conflicts.",
                direction=EntityResolutionSignalDirection.CONTRADICT,
                score=0.12,
            ),
        ],
    )

    bundle = InvestigationExplainabilityService().explain_entity_resolution(
        result
    )

    resolved = bundle.for_question(
        InvestigationExplanationQuestion.RESOLVED
    )
    contradicted = bundle.for_question(
        InvestigationExplanationQuestion.CONTRADICTED
    )
    merged = bundle.for_question(
        InvestigationExplanationQuestion.MERGED
    )

    assert len(resolved) == 1
    assert len(contradicted) == 1
    assert merged == ()
    assert resolved[0].metadata["mergePerformed"] is False
    assert "not treated as calibrated probabilities" in resolved[0].summary


def test_persisted_merge_record_is_the_only_source_for_why_merged():
    source_id = uuid4()
    target_id = uuid4()
    merge = EntityMerge(
        source_entity_id=source_id,
        target_entity_id=target_id,
        reason="Analyst-approved duplicate identity.",
    )

    bundle = InvestigationExplainabilityService().explain_entity_merge(
        merge
    )
    merged = bundle.for_question(
        InvestigationExplanationQuestion.MERGED
    )

    assert len(merged) == 1
    assert merged[0].domain == InvestigationExplanationDomain.ENTITY_MERGE
    assert merged[0].metadata["persistedMergeRecord"] is True
    assert merged[0].metadata["resolutionDecisionInferred"] is False
    assert "Analyst-approved duplicate identity." in merged[0].summary


def test_graph_entity_ranking_does_not_invent_combined_importance_score():
    entity_id = uuid4()
    explanation = GraphEntityExplanation(
        entity_id=entity_id,
        component_index=0,
        component_size=3,
        community_id=0,
        community_size=2,
        metric_ranks=(
            GraphMetricRank(
                metric="pagerank",
                value=0.42,
                rank=1,
                total_entities=3,
            ),
            GraphMetricRank(
                metric="betweenness",
                value=0.25,
                rank=2,
                total_entities=3,
            ),
        ),
        signals=(),
        reasons=(
            "PageRank 0.42 (rank 1/3).",
            "Betweenness 0.25 (rank 2/3).",
        ),
    )

    bundle = InvestigationExplainabilityService().explain_graph_entity(
        explanation
    )
    ranked = bundle.for_question(
        InvestigationExplanationQuestion.RANKED
    )

    assert len(ranked) == 1
    assert ranked[0].domain == InvestigationExplanationDomain.GRAPH
    assert "no combined graph-importance score is invented" in ranked[0].summary
    assert {reason.code for reason in ranked[0].reasons} >= {
        "graph_rank:pagerank",
        "graph_rank:betweenness",
    }


def test_graph_pair_why_linked_preserves_association_vs_identity_boundary():
    first = uuid4()
    second = uuid4()
    explanation = GraphPairExplanation(
        source_entity_id=first,
        target_entity_id=second,
        direct_edge=None,
        prediction=None,
        same_component=True,
        component_mode="weak",
        same_community=True,
        signals=(),
        reasons=(
            "Entities share the same weak component.",
            "Entities share the same Louvain community.",
        ),
    )

    bundle = InvestigationExplainabilityService().explain_graph_pair(
        explanation
    )
    linked = bundle.for_question(
        InvestigationExplanationQuestion.LINKED
    )

    assert len(linked) == 1
    assert "without claiming a direct Relationship" in linked[0].summary
    assert linked[0].metadata["sameComponent"] is True
    assert linked[0].metadata["sameCommunity"] is True


class _UnifiedSearchStub:
    def __init__(self, hit):
        self.hit = hit

    def search(self, query):
        return SimpleNamespace(
            hits=[self.hit],
            total_matches=1,
            candidate_count=1,
            duration_seconds=0.01,
            metadata={},
            warnings=[],
            errors=[],
        )


def test_rag_retrieval_attaches_unified_contract_without_changing_search_score():
    hit = _search_hit()
    before = (
        hit.scores.final,
        hit.scores.confidence,
    )

    result = InvestigationRAGRetrievalService(
        unified_search_service=_UnifiedSearchStub(hit),
    ).retrieve(
        question="What is known about Alice?",
        case_id=hit.case_id,
        enable_query_expansion=False,
        enable_reranking=False,
        enable_neural_reranking=False,
    )

    source = result.sources[0]
    payload = source.metadata["investigation_explainability"]
    questions = {
        row["question"]
        for row in payload
    }

    assert "why_found" in questions
    assert "why_ranked" in questions
    assert result.search_metadata[
        "investigation_explainability"
    ]["search_ranking_changed"] is False
    assert result.search_metadata[
        "investigation_explainability"
    ]["score_recalculated"] is False

    after = (
        hit.scores.final,
        hit.scores.confidence,
    )
    assert after == before


def test_bounded_rag_context_receives_search_why_lines():
    source = Path(
        "app/services/investigation_rag_context_builder.py"
    ).read_text(encoding="utf-8")

    assert '"investigation_explanation: "' in source
    assert '"investigation_reason: "' in source
    assert '"why_found"' in source
    assert '"why_ranked"' in source


def test_analysis_and_chat_payloads_expose_same_unified_contract():
    worker = Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")
    chat = Path(
        "app/application/analysis_chat_service.py"
    ).read_text(encoding="utf-8")

    assert '"investigationExplainability"' in worker
    assert '"investigationExplainability"' in chat
    assert '"investigation_explainability"' in worker
    assert '"investigation_explainability"' in chat


def test_service_container_wires_one_unified_explainability_service():
    source = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert "InvestigationExplainabilityService()" in source
    assert "self.investigation_explainability_service" in source
    assert "explainability_service=(" in source


def test_unified_explainability_layer_never_calculates_domain_scores_or_mutates():
    source = Path(
        "app/services/investigation_explainability_service.py"
    ).read_text(encoding="utf-8")

    assert "EvidenceConfidenceAggregationService" not in source
    assert "SearchRankingService" not in source
    assert ".merge_pair(" not in source
    assert ".rank(" not in source
    assert "AIExecutionService" not in source
    assert "OpenAI" not in source
    assert "Ollama" not in source


def test_ai_prompts_preserve_unified_why_semantic_boundaries():
    paths = (
        "app/services/investigation_rag_prompt_service.py",
        "app/services/investigation_rag_conclusions_service.py",
        "app/application/analysis_chat_service.py",
    )

    for path in paths:
        source = Path(path).read_text(encoding="utf-8")
        assert "investigation_explanation" in source
        assert "investigation_reason" in source
        assert "M025b" in source
        assert "WHY" in source



def test_unified_payload_round_trip_preserves_question_subject_and_reason():
    service = InvestigationExplainabilityService()
    original = service.explain_search_hit(
        _search_hit()
    )

    restored = service.from_payloads(
        original.to_payload()
    )

    assert isinstance(
        restored,
        InvestigationExplainabilityBundle,
    )
    assert len(restored.explanations) == len(
        original.explanations
    )
    assert {
        item.question
        for item in restored.explanations
    } == {
        item.question
        for item in original.explanations
    }
    assert (
        restored.explanations[0].subject.object_id
        == original.explanations[0].subject.object_id
    )


def test_unified_analytical_context_has_first_class_explainability_section():
    source = Path(
        "app/services/investigation_unified_analytical_context_service.py"
    ).read_text(encoding="utf-8")

    assert "InvestigationExplainabilityBundle" in source
    assert "explainability:" in source
    assert '"explainability"' in source
    assert "normalized_explainability" in source


def test_orchestrator_collects_existing_layers_without_materializing_graph_pairs():
    source = Path(
        "app/application/investigation_analysis_orchestrator.py"
    ).read_text(encoding="utf-8")

    assert "explain_entity_resolution(" in source
    assert "explain_evidence_proposition(" in source
    assert "explain_graph_entity(" in source
    assert "from_payloads(" in source
    assert "unified_explainability" in source
    assert '"graph_pair_explanations_materialized": False' in source
    assert ".explain_pair(" not in source


def test_service_container_reuses_same_explainability_instance_for_rag_and_orchestrator():
    source = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert source.count(
        "self.investigation_explainability_service"
    ) >= 3
    assert "explainability_service=(" in source
    assert "investigation_explainability_service=(" in source

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.investigation.search_result import (
    InvestigationSearchHit,
    SearchScores,
)
from app.services.investigation_evidence_confidence_search_enrichment_service import (
    CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY,
    InvestigationEvidenceConfidenceSearchEnrichmentService,
)
from app.services.investigation_rag_context_builder import (
    InvestigationRAGContextBuilder,
)
from app.services.investigation_rag_retrieval_service import (
    InvestigationRAGRetrievalService,
)


def _confidence_breakdown(
    *,
    confidence: float = 0.84,
    coverage: float = 0.77,
):
    return SimpleNamespace(
        confidence_score=confidence,
        assessment_coverage=coverage,
        intrinsic_strength=0.88,
        source_reliability_score=0.93,
        source_reliability_coverage=0.80,
        raw_corroboration_score=0.42,
        effective_corroboration_score=0.31,
        independence_score=1.0,
        independence_coverage=0.74,
        contradiction_strength=0.10,
        conflict_score=0.10,
        hard_conflict=False,
        net_support_margin=0.72,
    )


def _proposition(
    *,
    entity_id: UUID,
    evidence_id: UUID,
    source_id: UUID,
    origin_object_type: str = "message",
    origin_object_id: UUID | None = None,
):
    breakdown = _confidence_breakdown()
    return SimpleNamespace(
        proposition_key=f"entity_observed:{entity_id}",
        entity_id=entity_id,
        entity_type="email",
        entity_label="alice@example.com",
        evidence_ids=(evidence_id,),
        source_ids=(source_id,),
        origin_objects=(
            (
                origin_object_type,
                str(origin_object_id or uuid4()),
            ),
        ),
        confidence=breakdown,
        confidence_score=breakdown.confidence_score,
        assessment_coverage=breakdown.assessment_coverage,
    )


def _hit(
    *,
    object_id: UUID,
    object_type: str,
    case_id: UUID,
    final: float = 0.77,
    search_confidence: float = 0.33,
):
    return InvestigationSearchHit(
        object_id=object_id,
        object_type=object_type,
        case_id=case_id,
        title="Candidate",
        snippet="Alice observed in source material.",
        scores=SearchScores(
            lexical=0.80,
            confidence=search_confidence,
            final=final,
        ),
        source="Alice observed in source material.",
        metadata={},
    )


def test_enrichment_matches_entity_evidence_and_persisted_origin_without_reranking():
    case_id = uuid4()
    entity_id = uuid4()
    evidence_id = uuid4()
    source_id = uuid4()
    message_id = uuid4()

    proposition = _proposition(
        entity_id=entity_id,
        evidence_id=evidence_id,
        source_id=source_id,
        origin_object_id=message_id,
    )

    hits = [
        _hit(
            object_id=entity_id,
            object_type="entity",
            case_id=case_id,
        ),
        _hit(
            object_id=evidence_id,
            object_type="evidence",
            case_id=case_id,
        ),
        _hit(
            object_id=message_id,
            object_type="message",
            case_id=case_id,
        ),
        _hit(
            object_id=uuid4(),
            object_type="document",
            case_id=case_id,
        ),
    ]

    before = [
        (
            hit.scores.final,
            hit.scores.confidence,
        )
        for hit in hits
    ]

    InvestigationEvidenceConfidenceSearchEnrichmentService().annotate(
        hits,
        (proposition,),
    )

    for hit in hits[:3]:
        payload = hit.metadata[
            CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY
        ]
        assert payload["scope"] == "proposition_support"
        assert payload["strongest_confidence"] == pytest.approx(0.84)
        assert payload["strongest_assessment_coverage"] == pytest.approx(0.77)
        assert payload["ranking_unchanged"] is True
        assert payload["propositions"][0]["proposition_key"] == (
            f"entity_observed:{entity_id}"
        )

    assert (
        CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY
        not in hits[3].metadata
    )

    after = [
        (
            hit.scores.final,
            hit.scores.confidence,
        )
        for hit in hits
    ]
    assert after == before


class _UnifiedSearchStub:
    def __init__(self, hit):
        self.hit = hit

    def search(self, query):
        return SimpleNamespace(
            hits=[self.hit],
            total_matches=1,
            candidate_count=1,
            duration_seconds=0.01,
            metadata={
                "fusion": "rrf",
            },
            warnings=[],
            errors=[],
        )


def test_rag_retrieval_carries_canonical_confidence_in_source_metadata():
    case_id = uuid4()
    entity_id = uuid4()
    evidence_id = uuid4()
    source_id = uuid4()
    message_id = uuid4()

    hit = _hit(
        object_id=message_id,
        object_type="message",
        case_id=case_id,
    )
    proposition = _proposition(
        entity_id=entity_id,
        evidence_id=evidence_id,
        source_id=source_id,
        origin_object_id=message_id,
    )

    service = InvestigationRAGRetrievalService(
        unified_search_service=_UnifiedSearchStub(hit),
    )

    result = service.retrieve(
        question="What is known about Alice?",
        case_id=case_id,
        enable_query_expansion=False,
        enable_reranking=False,
        enable_neural_reranking=False,
        evidence_confidence_results=(proposition,),
    )

    assert result.source_count == 1
    source = result.sources[0]
    payload = source.metadata[
        CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY
    ]

    assert payload["strongest_confidence"] == pytest.approx(0.84)
    assert result.search_metadata[
        "canonical_evidence_confidence"
    ]["applied_hit_count"] == 1
    assert result.search_metadata[
        "canonical_evidence_confidence"
    ]["ranking_changed"] is False
    assert source.final_score == pytest.approx(0.77)
    assert source.confidence == pytest.approx(0.33)


def test_rag_context_exposes_retrieval_and_evidence_confidence_as_separate_fields():
    case_id = uuid4()
    entity_id = uuid4()
    evidence_id = uuid4()
    source_id = uuid4()
    message_id = uuid4()

    hit = _hit(
        object_id=message_id,
        object_type="message",
        case_id=case_id,
    )
    proposition = _proposition(
        entity_id=entity_id,
        evidence_id=evidence_id,
        source_id=source_id,
        origin_object_id=message_id,
    )

    retrieval = InvestigationRAGRetrievalService(
        unified_search_service=_UnifiedSearchStub(hit),
    ).retrieve(
        question="What is known about Alice?",
        case_id=case_id,
        enable_query_expansion=False,
        enable_reranking=False,
        enable_neural_reranking=False,
        evidence_confidence_results=(proposition,),
    )

    context = InvestigationRAGContextBuilder().build(
        retrieval
    )

    assert "retrieval_score: 0.770000" in context.text
    assert "evidence_confidence_scope: proposition_support" in context.text
    assert "evidence_confidence: 0.840000" in context.text
    assert "evidence_confidence_coverage: 0.770000" in context.text
    assert "intrinsic=0.880000" in context.text
    assert "source_reliability=0.930000" in context.text
    assert "source_reliability_coverage=0.800000" in context.text
    assert "corroboration=0.310000" in context.text
    assert "independence=1.000000" in context.text
    assert "independence_coverage=0.740000" in context.text
    assert "contradiction=0.100000" in context.text
    assert (
        f"evidence_proposition: entity_observed:{entity_id}"
        in context.text
    )


def test_context_does_not_fabricate_confidence_when_no_m024_result_exists():
    case_id = uuid4()
    hit = _hit(
        object_id=uuid4(),
        object_type="message",
        case_id=case_id,
    )

    retrieval = InvestigationRAGRetrievalService(
        unified_search_service=_UnifiedSearchStub(hit),
    ).retrieve(
        question="What is known?",
        case_id=case_id,
        enable_query_expansion=False,
        enable_reranking=False,
        enable_neural_reranking=False,
    )

    context = InvestigationRAGContextBuilder().build(
        retrieval
    )

    assert "retrieval_score: 0.770000" in context.text
    assert "evidence_confidence:" not in context.text
    assert "evidence_confidence_coverage:" not in context.text


def test_orchestrator_passes_evidence_stage_confidence_into_rag():
    source = Path(
        "app/application/investigation_analysis_orchestrator.py"
    ).read_text(encoding="utf-8")

    assert (
        "InvestigationAnalysisStage.EVIDENCE"
        in source
    )
    assert (
        '"proposition_confidence_results"'
        in source
    )
    assert (
        "evidence_confidence_results=("
        in source
    )


def test_ai_grounding_rules_forbid_invented_confidence_numbers():
    prompt_source = Path(
        "app/services/investigation_rag_prompt_service.py"
    ).read_text(encoding="utf-8")
    conclusion_source = Path(
        "app/services/investigation_rag_conclusions_service.py"
    ).read_text(encoding="utf-8")

    for source in (
        prompt_source,
        conclusion_source,
    ):
        assert "canonical M024" in source
        assert "not a general truth" in source
        assert (
            "Never invent"
            in source
        )



def test_conversational_analysis_chat_uses_current_m024_confidence():
    service_source = Path(
        "app/application/analysis_chat_service.py"
    ).read_text(encoding="utf-8")
    worker_source = Path(
        "app/interface/desktop/workers/analysis_chat_worker.py"
    ).read_text(encoding="utf-8")

    assert "evidence_confidence_results=(" in service_source
    assert "canonical M024 confidence" in service_source
    assert '"evidenceConfidence"' in service_source
    assert (
        "investigation_evidence_analysis_service"
        in worker_source
    )
    assert (
        '"proposition_confidence_results"'
        in worker_source
    )
    assert (
        "evidence_confidence_results=("
        in worker_source
    )


def test_analysis_workspace_payload_exposes_m024_source_confidence():
    worker_source = Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")

    assert '"canonical_evidence_confidence"' in worker_source
    assert '"evidenceConfidence"' in worker_source
    assert '"evidenceConfidenceCoverage"' in worker_source
    assert '"evidencePropositionCount"' in worker_source

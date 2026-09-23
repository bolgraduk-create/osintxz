from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.evidence.evidence_confidence_explanation import (
    EvidenceConfidenceExplanation,
    EvidenceConfidenceExplanationReason,
    EvidenceConfidenceExplanationService,
)
from app.evidence.source_reliability import (
    SourceReliabilityFactorState,
)
from app.investigation.search_result import (
    InvestigationSearchHit,
    SearchScores,
)
from app.services.investigation_evidence_confidence_search_enrichment_service import (
    CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY,
    InvestigationEvidenceConfidenceSearchEnrichmentService,
)


def _factor(
    *,
    name: str,
    state=SourceReliabilityFactorState.UNKNOWN,
    quality=None,
    reason: str = "",
):
    return SimpleNamespace(
        name=name,
        state=state,
        quality=quality,
        weight=0.2,
        reason=reason,
    )


def _parts(
    *,
    confidence_score: float = 0.72,
    assessment_coverage: float = 0.4,
    source_reliability_score: float = 0.9,
    source_reliability_coverage: float = 0.4,
    raw_corroboration_score: float = 0.0,
    effective_corroboration_score: float = 0.0,
    independence_score: float = 0.0,
    independence_coverage: float = 0.0,
    contradiction_strength: float = 0.0,
    hard_conflict: bool = False,
    supporting_evidence_count: int = 1,
    total_pair_count: int = 0,
    independent_pair_count: int = 0,
    dependent_pair_count: int = 0,
    unknown_pair_count: int = 0,
):
    confidence = SimpleNamespace(
        proposition_key="entity_observed:example",
        confidence_score=confidence_score,
        intrinsic_strength=0.8,
        source_reliability_score=source_reliability_score,
        source_reliability_coverage=source_reliability_coverage,
        raw_corroboration_score=raw_corroboration_score,
        effective_corroboration_score=effective_corroboration_score,
        independence_score=independence_score,
        independence_coverage=independence_coverage,
        contradiction_strength=contradiction_strength,
        conflict_score=min(0.8, contradiction_strength),
        contradiction_penalty_factor=(
            0.0 if hard_conflict else max(0.0, 1.0 - contradiction_strength)
        ),
        hard_conflict=hard_conflict,
        assessment_coverage=assessment_coverage,
    )
    strength = SimpleNamespace(
        considered_signal_count=1,
        duplicate_signal_count=0,
    )
    source_reliability = SimpleNamespace(
        evaluated_factor_count=2,
        unknown_factor_count=2,
        negative_factor_count=0,
        factors=(
            _factor(
                name="checksum_presence",
                state=SourceReliabilityFactorState.POSITIVE,
                quality=1.0,
                reason="Checksum is present.",
            ),
            _factor(
                name="original_path",
                reason="Original path is unavailable.",
            ),
        ),
    )
    corroboration = SimpleNamespace(
        is_corroborated=supporting_evidence_count >= 2
        and raw_corroboration_score > 0.0,
        supporting_evidence_count=supporting_evidence_count,
        distinct_source_count=max(1, supporting_evidence_count),
    )
    independence = SimpleNamespace(
        total_pair_count=total_pair_count,
        independent_pair_count=independent_pair_count,
        dependent_pair_count=dependent_pair_count,
        unknown_pair_count=unknown_pair_count,
        same_source_pair_count=dependent_pair_count,
        shared_origin_pair_count=0,
        shared_lineage_pair_count=0,
        shared_fingerprint_pair_count=0,
    )
    contradiction = SimpleNamespace(
        hard_conflict=hard_conflict,
        hard_conflict_evidence_ids=(uuid4(),) if hard_conflict else (),
        contradiction_evidence_count=1 if contradiction_strength > 0 else 0,
    )
    return (
        confidence,
        strength,
        source_reliability,
        corroboration,
        contradiction,
        independence,
    )


def _build(**kwargs):
    (
        confidence,
        strength,
        source_reliability,
        corroboration,
        contradiction,
        independence,
    ) = _parts(**kwargs)

    return EvidenceConfidenceExplanationService().build(
        confidence=confidence,
        strength=strength,
        source_reliability=source_reliability,
        corroboration=corroboration,
        contradiction=contradiction,
        independence=independence,
    )


def test_unknown_reliability_inputs_are_explained_as_uncertainty_not_negative_evidence():
    explanation = _build(
        source_reliability_coverage=0.4,
        assessment_coverage=0.4,
    )

    limitation_codes = {
        item.code
        for item in explanation.limitations
    }

    assert "source_reliability_incomplete" in limitation_codes
    assert "assessment_incomplete" in limitation_codes

    incomplete = next(
        item
        for item in explanation.limitations
        if item.code == "source_reliability_incomplete"
    )
    assert "unknown instead of being treated as negative evidence" in (
        incomplete.message
    )


def test_raw_corroboration_without_verified_independence_does_not_claim_boost():
    explanation = _build(
        raw_corroboration_score=0.6,
        effective_corroboration_score=0.0,
        supporting_evidence_count=2,
        total_pair_count=1,
        unknown_pair_count=1,
        independence_coverage=0.0,
    )

    reason_codes = {
        item.code
        for item in explanation.reasons
    }
    limitation_codes = {
        item.code
        for item in explanation.limitations
    }

    assert "corroboration_applied" not in reason_codes
    assert "corroboration_not_independent" in limitation_codes
    assert "independence_unknown" in limitation_codes


def test_verified_independence_and_corroboration_are_positive_reasons():
    explanation = _build(
        confidence_score=0.86,
        assessment_coverage=1.0,
        source_reliability_coverage=1.0,
        raw_corroboration_score=0.5,
        effective_corroboration_score=0.5,
        supporting_evidence_count=2,
        total_pair_count=1,
        independent_pair_count=1,
        independence_score=1.0,
        independence_coverage=1.0,
    )

    reason_codes = {
        item.code
        for item in explanation.reasons
    }

    assert "corroboration_applied" in reason_codes
    assert "verified_independence" in reason_codes
    assert "86%" in explanation.summary


def test_hard_conflict_explanation_states_canonical_zero_veto():
    explanation = _build(
        confidence_score=0.0,
        contradiction_strength=0.9,
        hard_conflict=True,
    )

    limitation = next(
        item
        for item in explanation.limitations
        if item.code == "hard_conflict"
    )

    assert "vetoed to zero" in limitation.message
    assert "hard conflict veto is active" in explanation.summary.lower()


class _Explanation:
    def to_payload(self):
        return EvidenceConfidenceExplanation(
            proposition_key="entity_observed:example",
            summary="Canonical proposition confidence is 84% with 77% assessment coverage.",
            reasons=(
                EvidenceConfidenceExplanationReason(
                    code="verified_independence",
                    category="independence",
                    effect="support",
                    message="Independent provenance is verified.",
                    value=1.0,
                    coverage=1.0,
                ),
            ),
            limitations=(),
        ).to_payload()


def test_search_enrichment_carries_m025_explanation_without_changing_ranking():
    case_id = uuid4()
    entity_id = uuid4()
    hit = InvestigationSearchHit(
        object_id=entity_id,
        object_type="entity",
        case_id=case_id,
        title="Entity",
        snippet="example",
        scores=SearchScores(
            lexical=0.8,
            confidence=0.33,
            final=0.71,
        ),
        metadata={
            "search_explanation": {
                "summary": "matched by lexical",
            }
        },
    )
    proposition = SimpleNamespace(
        proposition_key="entity_observed:example",
        entity_id=entity_id,
        entity_type="email",
        entity_label="alice@example.com",
        evidence_ids=(uuid4(),),
        source_ids=(uuid4(),),
        origin_objects=(),
        confidence_score=0.84,
        assessment_coverage=0.77,
        confidence=SimpleNamespace(
            confidence_score=0.84,
            assessment_coverage=0.77,
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
        ),
        explanation=_Explanation(),
    )

    before = (
        hit.scores.final,
        hit.scores.confidence,
    )

    InvestigationEvidenceConfidenceSearchEnrichmentService().annotate(
        [hit],
        (proposition,),
    )

    canonical = hit.metadata[
        CANONICAL_EVIDENCE_CONFIDENCE_METADATA_KEY
    ]
    assert canonical["propositions"][0]["explanation"]["version"] == "m025a"
    assert (
        canonical["propositions"][0]["explanation"]["reasons"][0]["code"]
        == "verified_independence"
    )

    linked = hit.metadata["search_explanation"][
        "canonical_evidence_confidence"
    ]
    assert linked["confidence"] == pytest.approx(0.84)
    assert linked["search_ranking_changed"] is False
    assert linked["explanation"]["version"] == "m025a"

    after = (
        hit.scores.final,
        hit.scores.confidence,
    )
    assert after == before


def test_rag_context_receives_deterministic_reason_and_limitation_lines():
    source = Path(
        "app/services/investigation_rag_context_builder.py"
    ).read_text(encoding="utf-8")

    assert '"evidence_explanation: "' in source
    assert '"evidence_reason: "' in source
    assert '"evidence_limitation: "' in source
    assert 'explanation.get(' in source


def test_analysis_workspace_exposes_expandable_why_explanation():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")
    worker = Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")

    assert '"evidenceConfidenceExplanation"' in worker
    assert "function evidenceExplanation(item)" in qml
    assert "function evidenceExplanationText(item)" in qml
    assert "property bool explanationOpen: false" in qml
    assert 'text: factCard.explanationOpen ? "WHY ▲" : "WHY ▼"' in qml
    assert "factCard.explanationOpen = !factCard.explanationOpen" in qml


def test_service_container_wires_explainability_without_a_second_score_formula():
    container = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")
    explainer = Path(
        "app/evidence/evidence_confidence_explanation.py"
    ).read_text(encoding="utf-8")

    assert "EvidenceConfidenceExplanationService()" in container
    assert "explanation_service=(" in container
    assert "confidence_score =" not in explainer
    assert "EvidenceConfidenceAggregationService" not in explainer


def test_m025_explanation_is_deterministic_not_llm_generated():
    source = Path(
        "app/evidence/evidence_confidence_explanation.py"
    ).read_text(encoding="utf-8")

    assert "AIExecutionService" not in source
    assert "PromptManager" not in source
    assert "OpenAI" not in source
    assert "Ollama" not in source



def test_ai_may_paraphrase_but_not_invent_m025_confidence_reasons():
    prompt_source = Path(
        "app/services/investigation_rag_prompt_service.py"
    ).read_text(encoding="utf-8")
    conclusion_source = Path(
        "app/services/investigation_rag_conclusions_service.py"
    ).read_text(encoding="utf-8")
    chat_source = Path(
        "app/application/analysis_chat_service.py"
    ).read_text(encoding="utf-8")

    for source in (
        prompt_source,
        conclusion_source,
        chat_source,
    ):
        assert "evidence_reason" in source
        assert "evidence_limitation" in source
        assert "deterministic M025" in source
        assert "paraphrase" in source


def test_analysis_qml_uses_only_defined_theme_tokens_for_explanation_surface():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    assert "Theme.surfaceRaised" in qml
    assert "Theme.panel" not in qml

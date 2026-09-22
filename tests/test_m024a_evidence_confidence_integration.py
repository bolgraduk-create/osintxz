from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.investigation_evidence_analysis_service import (
    InvestigationEvidenceAnalysisService,
)
from app.application.investigation_evidence_confidence_service import (
    InvestigationEvidenceConfidenceService,
)
from app.evidence.contradiction_detection import (
    EvidenceContradictionDetectionService,
)
from app.evidence.corroboration import (
    EvidenceCorroborationService,
)
from app.evidence.evidence_confidence import (
    EvidenceConfidenceAggregationService,
)
from app.evidence.evidence_strength import (
    EvidenceStrengthScoringService,
)
from app.evidence.source_independence import (
    EvidenceSourceIndependenceService,
)
from app.evidence.source_reliability import (
    SourceReliabilityBreakdown,
)


def _reliability(
    score: float = 0.90,
    coverage: float = 1.0,
) -> SourceReliabilityBreakdown:
    return SourceReliabilityBreakdown(
        reliability_score=score,
        coverage_score=coverage,
        evaluated_weight=coverage,
        total_weight=1.0,
        factors=(),
        evaluated_factor_count=0,
        positive_factor_count=0,
        partial_factor_count=0,
        negative_factor_count=0,
        unknown_factor_count=0,
        invalid_metadata=False,
    )


def _confidence_service() -> InvestigationEvidenceConfidenceService:
    return InvestigationEvidenceConfidenceService(
        strength_scoring_service=EvidenceStrengthScoringService(),
        corroboration_service=EvidenceCorroborationService(),
        contradiction_service=EvidenceContradictionDetectionService(),
        source_independence_service=EvidenceSourceIndependenceService(),
        confidence_aggregation_service=EvidenceConfidenceAggregationService(),
    )


def _source(*, source_id=None, checksum=None):
    return SimpleNamespace(
        id=source_id or uuid4(),
        source_type=SimpleNamespace(value="telegram"),
        checksum=checksum,
    )


def _entity(*, entity_id=None):
    return SimpleNamespace(
        id=entity_id or uuid4(),
        entity_type=SimpleNamespace(value="email"),
        value="alice@example.com",
        normalized_value="alice@example.com",
    )


def _evidence(
    *,
    case_id,
    source,
    entity,
    evidence_id=None,
    confidence=0.80,
    origin_key=None,
    malformed=False,
):
    if malformed:
        metadata_json = "{not-json"
    else:
        metadata_json = json.dumps(
            {
                "extraction_provenance": {
                    "extractor": "IdentifierExtractor",
                    "origin": {
                        "object_type": "message",
                        "object_id": str(uuid4()),
                        "source_id": str(source.id),
                        "external_id": "42",
                        "metadata": (
                            {"origin_key": origin_key}
                            if origin_key
                            else {}
                        ),
                    },
                    "candidates": [
                        {
                            "entity_type": "email",
                            "value": "alice@example.com",
                            "normalized_value": "alice@example.com",
                            "confidence": confidence,
                            "metadata": {},
                        }
                    ],
                }
            }
        )

    return SimpleNamespace(
        id=evidence_id or uuid4(),
        case_id=case_id,
        source_id=source.id,
        source=source,
        evidence_type=SimpleNamespace(value="message"),
        sha256=None,
        metadata_json=metadata_json,
        entity_links=[
            SimpleNamespace(entity=entity)
        ],
    )


def _reliability_map(*sources):
    return {
        str(source.id): _reliability()
        for source in sources
    }


def test_single_persisted_extraction_observation_produces_real_confidence():
    case_id = uuid4()
    entity = _entity()
    source = _source()
    evidence = _evidence(
        case_id=case_id,
        source=source,
        entity=entity,
    )

    result = _confidence_service().analyze(
        case_id=case_id,
        evidence=(evidence,),
        source_reliability_by_source_key=_reliability_map(source),
    )

    assert len(result.propositions) == 1
    proposition = result.propositions[0]

    assert proposition.proposition_key == f"entity_observed:{entity.id}"
    assert proposition.entity_id == entity.id
    assert proposition.signal_count == 1
    assert proposition.strength.intrinsic_strength == pytest.approx(0.80)
    assert proposition.corroboration.corroboration_score == pytest.approx(0.0)
    assert proposition.independence.total_pair_count == 0
    assert proposition.confidence_score == pytest.approx(0.72)


def test_two_evidence_from_same_source_do_not_gain_independent_corroboration():
    case_id = uuid4()
    entity = _entity()
    source = _source()

    first = _evidence(
        case_id=case_id,
        source=source,
        entity=entity,
        origin_key="telegram:chat-a:message-1",
    )
    second = _evidence(
        case_id=case_id,
        source=source,
        entity=entity,
        origin_key="telegram:chat-a:message-2",
    )

    proposition = _confidence_service().analyze(
        case_id=case_id,
        evidence=(first, second),
        source_reliability_by_source_key=_reliability_map(source),
    ).propositions[0]

    assert proposition.corroboration.corroboration_score > 0.0
    assert proposition.independence.same_source_pair_count == 1
    assert proposition.independence.conservative_independence_score == 0.0
    assert proposition.confidence.effective_corroboration_score == 0.0
    assert proposition.confidence_score == pytest.approx(0.72)


def test_distinct_explicit_origins_can_raise_confidence_conservatively():
    case_id = uuid4()
    entity = _entity()
    source_a = _source()
    source_b = _source()

    first = _evidence(
        case_id=case_id,
        source=source_a,
        entity=entity,
        origin_key="registry-a:record-123",
    )
    second = _evidence(
        case_id=case_id,
        source=source_b,
        entity=entity,
        origin_key="registry-b:record-987",
    )

    result = _confidence_service().analyze(
        case_id=case_id,
        evidence=(first, second),
        source_reliability_by_source_key=_reliability_map(
            source_a,
            source_b,
        ),
    )
    proposition = result.propositions[0]

    assert proposition.independence.independent_pair_count == 1
    assert proposition.independence.conservative_independence_score == pytest.approx(1.0)
    assert proposition.confidence.effective_corroboration_score > 0.0
    assert proposition.confidence_score > 0.72


def test_different_source_ids_without_explicit_origin_do_not_prove_independence():
    case_id = uuid4()
    entity = _entity()
    source_a = _source()
    source_b = _source()

    first = _evidence(
        case_id=case_id,
        source=source_a,
        entity=entity,
    )
    second = _evidence(
        case_id=case_id,
        source=source_b,
        entity=entity,
    )

    proposition = _confidence_service().analyze(
        case_id=case_id,
        evidence=(first, second),
        source_reliability_by_source_key=_reliability_map(
            source_a,
            source_b,
        ),
    ).propositions[0]

    assert proposition.independence.unknown_pair_count == 1
    assert proposition.independence.evaluated_pair_count == 0
    assert proposition.confidence.effective_corroboration_score == 0.0


def test_malformed_or_unmatched_metadata_never_fabricates_a_proposition():
    case_id = uuid4()
    entity = _entity()
    source = _source()
    evidence = _evidence(
        case_id=case_id,
        source=source,
        entity=entity,
        malformed=True,
    )

    result = _confidence_service().analyze(
        case_id=case_id,
        evidence=(evidence,),
        source_reliability_by_source_key=_reliability_map(source),
    )

    assert result.propositions == ()
    assert result.invalid_metadata_count == 1
    assert result.eligible_signal_count == 0
    assert any(
        "No persisted extraction-provenance Entity proposition"
        in warning
        for warning in result.warnings
    )


class _EvidenceService:
    def __init__(self, rows):
        self.rows = list(rows)

    def get_case_evidence(self, case_id):
        return [
            item
            for item in self.rows
            if item.case_id == case_id
        ]


class _SourceReliabilityService:
    def __init__(self):
        self.calls = 0

    def score(self, source):
        self.calls += 1
        return _reliability()


def test_case_evidence_analysis_populates_proposition_confidence_results():
    case_id = uuid4()
    entity = _entity()
    source = _source()
    first = _evidence(
        case_id=case_id,
        source=source,
        entity=entity,
    )
    second = _evidence(
        case_id=case_id,
        source=source,
        entity=entity,
    )
    source_reliability = _SourceReliabilityService()

    service = InvestigationEvidenceAnalysisService(
        evidence_service=_EvidenceService([first, second]),
        source_reliability_scoring_service=source_reliability,
        evidence_confidence_service=_confidence_service(),
    )

    result = service.analyze_case(case_id)

    assert result.evidence_count() == 2
    assert result.analyzed_evidence_count() == 2
    assert result.has_proposition_confidence() is True
    assert len(result.proposition_confidence_results) == 1
    assert source_reliability.calls == 1


def test_service_container_reuses_canonical_evidence_math_instead_of_second_formula():
    from pathlib import Path

    source = Path("app/core/service_container.py").read_text(
        encoding="utf-8"
    )
    adapter = Path(
        "app/application/investigation_evidence_confidence_service.py"
    ).read_text(encoding="utf-8")

    for expected in (
        "EvidenceStrengthScoringService()",
        "EvidenceCorroborationService()",
        "EvidenceContradictionDetectionService()",
        "EvidenceSourceIndependenceService()",
        "EvidenceConfidenceAggregationService()",
        "InvestigationEvidenceConfidenceService(",
    ):
        assert expected in source

    assert "confidence_score =" not in adapter
    assert "confidence_aggregation_service.aggregate(" in adapter
    assert "Different Source IDs alone are never treated as proof" in adapter


def test_legacy_evidence_analysis_caller_can_omit_m024_adapter():
    case_id = uuid4()
    source_reliability = _SourceReliabilityService()

    service = InvestigationEvidenceAnalysisService(
        evidence_service=_EvidenceService([]),
        source_reliability_scoring_service=source_reliability,
    )

    result = service.analyze_case(case_id)

    assert result.evidence == ()
    assert result.proposition_confidence_results == ()

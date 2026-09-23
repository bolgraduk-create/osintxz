from __future__ import annotations

from pathlib import Path


def _worker() -> str:
    return Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")


def _qml() -> str:
    return Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")


def test_analysis_worker_exposes_explainable_m024_breakdown():
    source = _worker()

    for expected in (
        '"evidenceConfidence"',
        '"evidenceConfidenceCoverage"',
        '"evidencePropositionCount"',
        '"evidenceConfidenceDetails"',
        '"intrinsicStrength"',
        '"sourceReliability"',
        '"sourceReliabilityCoverage"',
        '"corroboration"',
        '"independence"',
        '"independenceCoverage"',
        '"contradiction"',
        '"hardConflict"',
    ):
        assert expected in source

    assert '"canonical_evidence_confidence"' in source
    assert 'strongest_proposition = (' in source


def test_fact_payload_reuses_same_canonical_breakdown():
    source = _worker()

    facts_start = source.index("facts.append(")
    facts_block = source[facts_start:facts_start + 2200]

    assert '"evidenceConfidence"' in facts_block
    assert '"evidenceConfidenceCoverage"' in facts_block
    assert '"evidenceConfidenceDetails"' in facts_block
    assert 'source_row[' in facts_block


def test_analysis_ui_visually_separates_search_relevance_from_evidence_confidence():
    qml = _qml()

    assert "Search relevance and Evidence confidence are separate signals" in qml
    assert '"\\nSEARCH " + Number(sourceRow.modelData.score || 0).toFixed(3)' in qml
    assert '"\\nEVIDENCE "' in qml
    assert "sourceRow.modelData.evidenceConfidence" in qml
    assert "sourceRow.modelData.evidenceConfidenceCoverage" in qml


def test_missing_m024_confidence_is_never_displayed_as_zero_confidence():
    qml = _qml()

    assert "function hasEvidenceConfidence(item)" in qml
    assert 'return "—"' in qml
    assert '"\\nEVIDENCE —"' in qml
    assert (
        'Number(sourceRow.modelData.evidenceConfidence || 0)'
        not in qml
    )


def test_analysis_ui_exposes_confidence_coverage_and_reason_factors():
    qml = _qml()

    for expected in (
        "function evidenceConfidenceFactors(item)",
        '"intrinsic " + root.scorePercent(details.intrinsicStrength)',
        '"source " + root.scorePercent(details.sourceReliability)',
        '"corroboration " + root.scorePercent(details.corroboration)',
        '"independence " + root.scorePercent(details.independence)',
        '"contradiction " + root.scorePercent(details.contradiction)',
        '"hard conflict"',
        '" · COV "',
    ):
        assert expected in qml


def test_low_coverage_and_hard_conflict_are_not_painted_as_high_confidence():
    qml = _qml()

    assert "function evidenceConfidenceColor(item)" in qml
    assert "if (Boolean(details.hardConflict))" in qml
    assert "return Theme.danger" in qml
    assert "if (coverage < 0.5)" in qml
    assert "return Theme.warning" in qml


def test_m024c_does_not_change_search_or_evidence_scoring_formulas():
    qml = _qml()
    worker = _worker()

    assert "EvidenceConfidenceAggregationService" not in qml
    assert "EvidenceConfidenceAggregationService" not in worker
    assert "SearchScores" not in qml
    assert "SearchScores" not in worker
    assert "confidence_score =" not in qml

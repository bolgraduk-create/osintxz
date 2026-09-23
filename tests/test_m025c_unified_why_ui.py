from __future__ import annotations

from pathlib import Path


def _qml() -> str:
    return Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")


def _worker() -> str:
    return Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")


def test_analysis_snapshot_exposes_first_class_unified_explainability():
    worker = _worker()

    assert '"explainability": explainability' in worker
    assert 'unified_explainability = getattr(' in worker
    assert '"explainability"' in worker


def test_analysis_navigation_has_dedicated_why_layer():
    qml = _qml()

    assert '{key:"explainability", label:"Why"' in qml
    assert 'if (key === "explainability") return root.explainability.length' in qml
    assert 'property var explainability: run.explainability || []' in qml
    assert 'root.explainability = root.run.explainability || []' in qml
    assert 'title: "Explainability"' in qml
    assert 'model: root.explainability' in qml


def test_unified_why_questions_are_rendered_as_distinct_semantic_actions():
    qml = _qml()

    for value, label in (
        ("why_found", "WHY FOUND"),
        ("why_ranked", "WHY RANKED"),
        ("why_confident", "WHY CONFIDENT"),
        ("why_linked", "WHY LINKED"),
        ("why_resolved", "WHY RESOLVED"),
        ("why_merged", "WHY MERGED"),
        ("why_contradicted", "WHY CONTRADICTED"),
    ):
        assert f'if (key === "{value}") return "{label}"' in qml


def test_fact_and_source_rows_open_same_unified_why_drawer():
    qml = _qml()

    assert "function openWhyForItem(item, title)" in qml
    assert "function openWhyPayload(rows, title)" in qml
    assert "root.openWhyForItem(" in qml
    assert "sourceWhyButton" in qml
    assert "factWhyButton" in qml
    assert "root.hasUnifiedWhy(sourceRow.modelData)" in qml
    assert "root.hasUnifiedWhy(factCard.modelData)" in qml


def test_old_evidence_why_remains_as_history_fallback_only():
    qml = _qml()

    assert "root.hasEvidenceExplanation(factCard.modelData)" in qml
    assert "!root.hasUnifiedWhy(factCard.modelData)" in qml
    assert "factCard.explanationOpen = !factCard.explanationOpen" in qml


def test_unified_why_drawer_displays_summary_reasons_limitations_and_subject():
    qml = _qml()

    for expected in (
        'id: whyDrawer',
        'text: "UNIFIED WHY"',
        "root.explanationSubjectText(",
        "whyExplanationCard.modelData.summary",
        "whyExplanationCard.modelData.reasons || []",
        "whyExplanationCard.modelData.limitations || []",
        'text: "REASONS"',
        'text: "LIMITATIONS / UNCERTAINTY"',
        "root.whyEffectColor(",
    ):
        assert expected in qml


def test_unified_why_ui_does_not_recalculate_scores_or_call_ai():
    qml = _qml()

    for forbidden in (
        "EvidenceConfidenceAggregationService",
        "SearchRankingService",
        "AIExecutionService",
        "OpenAIProvider",
        "OllamaProvider",
        "confidence_score =",
    ):
        assert forbidden not in qml

    assert "no score is recalculated here" in qml


def test_source_open_action_is_preserved_next_to_why_action():
    qml = _qml()

    assert (
        'analysisBridge.openSource(String(sourceRow.modelData.reference || ""))'
        in qml
    )
    assert "sourceWhyButton" in qml


def test_unified_why_drawer_is_responsive_and_closable():
    qml = _qml()

    assert "Math.min(" in qml
    assert "root.width * 0.54" in qml
    assert "function closeWhy()" in qml
    assert "onClicked: root.closeWhy()" in qml
    assert "visible: root.whyDrawerOpen" in qml

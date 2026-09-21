from __future__ import annotations

from pathlib import Path


def test_analysis_ui_uses_separate_non_overlapping_layout_zones():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    assert 'objectName: "analysisLayerRail"' in qml
    assert 'objectName: "analysisComposer"' in qml
    assert 'objectName: "analysisModeRow"' in qml
    assert 'objectName: "analysisControlRow"' in qml

    mode_index = qml.index('objectName: "analysisModeRow"')
    control_index = qml.index('objectName: "analysisControlRow"')
    assert mode_index < control_index

    mode_block = qml[mode_index:mode_index + 220]
    control_block = qml[control_index:control_index + 220]
    assert "height: 38" in mode_block
    assert "height: 48" in control_block

    assert 'Layout.preferredHeight: 206' in qml
    assert 'text: "SCOPE"' in qml
    assert 'text: "MODEL"' in qml
    assert 'text: "REASONING"' in qml


def test_analysis_ui_has_assistant_style_composer_and_empty_state():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    assert (
        'placeholderText: "Ask what you want to understand '
        'about this investigation..."'
    ) in qml
    assert 'text: "What do you want to understand?"' in qml
    assert '"Summarize the case"' in qml
    assert '"Find contradictions"' in qml
    assert '"Plan next steps"' in qml
    assert "root.usePrompt(" in qml


def test_analysis_ui_keeps_structured_analytical_layers():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    for layer in (
        "Overview",
        "Facts",
        "Hypotheses",
        "Contradictions",
        "Next Steps",
        "Sources",
        "Pipeline",
        "History",
    ):
        assert f'label:"{layer}"' in qml

    assert 'title: "AI Summary"' in qml
    assert 'title: "RAG Sources"' in qml
    assert 'title: "Analysis Pipeline"' in qml
    assert 'title: "Analysis History"' in qml


def test_analysis_mode_pills_are_not_dropdown_labels():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    assert "modePill.modelData.label" in qml
    assert "(modeRow.width - 14) / 3" in qml
    assert "root.applyMode(" in qml

    # The old layout placed mode cards in a RowLayout directly above labelled
    # form controls and caused text collisions at real desktop sizes.
    assert 'title: "Analysis Focus"' not in qml


def test_local_provider_cannot_claim_stale_gpt_model_or_reasoning():
    bridge = Path(
        "app/interface/desktop/bridges/analysis_bridge.py"
    ).read_text(encoding="utf-8")
    worker = Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    assert "Local providers own their model selection" in bridge
    assert 'selected_model = str(provider.get("model") or "").strip()' in bridge
    assert 'selected_reasoning = ""' in bridge
    assert 'if provider_name == "openai"' in worker
    assert 'else ""' in worker
    assert 'return [String(root.provider.model || "Local model")]' in qml
    assert '["Local provider"]' in qml


def test_analysis_redaction_and_source_navigation_survive_ui_redesign():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    assert "analysisBridge.openSource(" in qml
    assert "analysisBridge.openHistory(" in qml
    assert "root.run.redactions" in qml
    assert "credential/secret fragment(s) were redacted" in qml
    assert "AI output is analysis, not Evidence." in qml

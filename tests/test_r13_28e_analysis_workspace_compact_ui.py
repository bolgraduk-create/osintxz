from __future__ import annotations

from pathlib import Path


def _qml() -> str:
    return Path("app/interface/desktop/qml/pages/Analysis.qml").read_text(encoding="utf-8")


def test_analysis_workspace_uses_horizontal_tabs_and_bottom_composer():
    qml = _qml()

    tabs_index = qml.index('objectName: "analysisLayerRail"')
    stack_index = qml.index("StackLayout {")
    composer_index = qml.index('objectName: "analysisComposer"')

    assert tabs_index < stack_index < composer_index
    assert "second full-height sidebar" in qml
    assert "composer stays at the bottom" in qml


def test_analysis_composer_geometry_has_no_vertical_overflow():
    qml = _qml()

    assert 'Layout.preferredHeight: 206' in qml
    assert 'objectName: "analysisModeRow"' in qml
    assert 'height: 68' in qml
    assert 'objectName: "analysisControlRow"' in qml

    mode_index = qml.index('objectName: "analysisModeRow"')
    control_index = qml.index('objectName: "analysisControlRow"')
    assert "height: 38" in qml[mode_index:mode_index + 220]
    assert "height: 48" in qml[control_index:control_index + 220]


def test_analysis_assistant_contract_survives_compact_redesign():
    qml = _qml()

    for expected in (
        'text: "AI Analysis"',
        'placeholderText: "Ask what you want to understand about this investigation..."',
        'title: "AI Summary"',
        'title: "RAG Sources"',
        'title: "Analysis Pipeline"',
        'title: "Analysis History"',
        'analysisBridge.runAnalysis',
        'analysisBridge.openSource(',
        'analysisBridge.openHistory(',
        '"storage off"',
        '"Run Analysis"',
        '"Local provider"',
    ):
        assert expected in qml

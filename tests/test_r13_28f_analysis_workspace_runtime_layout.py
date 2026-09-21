from __future__ import annotations

from pathlib import Path


def _qml() -> str:
    return Path("app/interface/desktop/qml/pages/Analysis.qml").read_text(encoding="utf-8")


def test_analysis_tabs_use_layout_instead_of_manual_delegate_widths():
    qml = _qml()
    tab_start = qml.index('id: analysisTabs')
    workspace_start = qml.index('id: analysisWorkspace')
    tab_block = qml[tab_start:workspace_start]

    assert "RowLayout {" in tab_block
    assert "Layout.fillWidth: true" in tab_block
    assert "Layout.minimumWidth: 72" in tab_block
    assert "root.layerItems.length" not in tab_block


def test_overview_empty_state_uses_visible_flickable_height():
    qml = _qml()

    assert "id: overviewFlick" in qml
    assert "Math.max(330, overviewFlick.height - 20)" in qml
    assert "overviewContent.parent.height" not in qml
    assert 'text: "What do you want to understand?"' in qml


def test_analysis_workspace_masks_decorative_background():
    qml = _qml()

    workspace = qml.index('id: analysisWorkspace')
    composer = qml.index('objectName: "analysisComposer"')
    block = qml[workspace:composer]

    assert 'color: "#091722"' in block
    assert "clip: true" in block
    assert "StackLayout {" in block


def test_scope_never_renders_as_empty_dropdown():
    qml = _qml()

    assert 'out.push(desktopBridge.hasCurrentCase ? "Entire Investigation" : "Select an investigation")' in qml

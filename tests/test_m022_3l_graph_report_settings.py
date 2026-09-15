from pathlib import Path


ROOT = Path("app/interface/desktop")


def test_person_detail_column_scrolls_and_identifier_section_can_grow():
    person = (ROOT / "qml/pages/Person.qml").read_text(encoding="utf-8")
    assert "id: rightDetailScroll" in person
    assert "contentHeight: rightDetailColumn.implicitHeight" in person
    assert "Layout.minimumHeight: 300" in person
    assert "Math.max(root.relatedRows.length * 58, root.evidenceRows.length * 62)" in person
    assert 'title: "Related Identifiers"' in person


def test_graph_uses_live_entity_graph_service_and_has_bounded_explorer():
    bridge = (ROOT / "bridges/desktop_bridge.py").read_text(encoding="utf-8")
    graph = (ROOT / "qml/pages/Graph.qml").read_text(encoding="utf-8")
    assert "entity_graph_service" in bridge
    assert "get_case_graph_data" in bridge
    assert "def _graph_workspace_payload" in bridge
    assert '@Property("QVariantMap", notify=changed)\n    def graphWorkspace' in bridge
    assert "EntityWeb" in graph
    assert 'title: "Graph Explorer"' in graph
    assert "desktopBridge.selectGraphEntity" in graph
    assert "desktopBridge.setGraphDepth" in graph


def test_reports_are_clickable_and_route_to_report_reader():
    bridge = (ROOT / "bridges/desktop_bridge.py").read_text(encoding="utf-8")
    main = (ROOT / "qml/Main.qml").read_text(encoding="utf-8")
    workspace = (ROOT / "qml/pages/DataWorkspace.qml").read_text(encoding="utf-8")
    reports = (ROOT / "qml/pages/Reports.qml").read_text(encoding="utf-8")
    report = (ROOT / "qml/pages/Report.qml").read_text(encoding="utf-8")
    assert "def openReport" in bridge
    assert "def currentReport" in bridge
    assert 'navigationRequested.emit("report")' in bridge
    assert 'case "report": return "pages/Report.qml"' in main
    assert 'root.pageKey === "reports"' in workspace
    assert "desktopBridge.openReport(recordId)" in reports
    assert 'title: "Report Content"' in report
    assert "Text.MarkdownText" in report


def test_settings_are_real_local_preferences_not_placeholder_copy():
    bridge = (ROOT / "bridges/desktop_bridge.py").read_text(encoding="utf-8")
    settings = (ROOT / "qml/pages/Settings.qml").read_text(encoding="utf-8")
    main = (ROOT / "qml/Main.qml").read_text(encoding="utf-8")
    assert "QSettings" in bridge
    assert "def setUiSetting" in bridge
    assert "def resetUiSettings" in bridge
    assert 'title: "Appearance"' in settings
    assert 'title: "Graph"' in settings
    assert 'desktopBridge.setUiSetting("showWorldMap"' in settings
    assert 'desktopBridge.setUiSetting("graphNodeLimit"' in settings
    assert "visible: Boolean(desktopBridge.uiSettings.showWorldMap)" in main

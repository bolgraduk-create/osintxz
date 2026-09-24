from __future__ import annotations

from pathlib import Path


ROOT = Path("app/interface/desktop/qml")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ui_r1_sidebar_exposes_only_primary_workspaces():
    qml = _read("components/Sidebar.qml")

    for expected in (
        '{ key: "overview", label: "Overview"',
        '{ key: "cases", label: "Investigations"',
        '{ key: "search", label: "Search"',
        '{ key: "entities", label: "Entities"',
        '{ key: "analysis", label: "Analysis"',
        '{ key: "evidence", label: "Evidence"',
        '{ key: "reports", label: "Reports"',
        '{ key: "settings", label: "Settings"',
    ):
        assert expected in qml

    for removed_primary_item in (
        '{key:"graph", label:"Graph"',
        '{key:"timeline", label:"Timeline"',
        '{key:"osint", label:"OSINT"',
        '{key:"sources", label:"Sources"',
        '{key:"registry", label:"Registry"',
    ):
        assert removed_primary_item not in qml


def test_ui_r1_sidebar_collapses_and_normalizes_legacy_routes():
    sidebar = _read("components/Sidebar.qml")
    item = _read("components/SidebarItem.qml")
    main = _read("Main.qml")

    assert "property bool collapsed: false" in sidebar
    assert 'if (key === "graph" || key === "timeline" || key === "analysis")' in sidebar
    assert 'if (key === "registry" || key === "osint")' in sidebar
    assert 'if (key === "sources")' in sidebar
    assert 'if (key === "person")' in sidebar
    assert 'if (key === "report")' in sidebar
    assert "collapsed: root.collapsed" in sidebar
    assert "property bool collapsed: false" in item
    assert "root.collapsed ? 76" in main


def test_ui_r1_analysis_route_uses_workspace_shell_and_keeps_legacy_routes():
    main = _read("Main.qml")

    assert 'case "analysis": return "pages/AnalysisWorkspace.qml"' in main
    for route, page in (
        ("graph", "Graph.qml"),
        ("timeline", "Timeline.qml"),
        ("osint", "Osint.qml"),
        ("registry", "Registry.qml"),
        ("sources", "Sources.qml"),
    ):
        assert f'case "{route}": return "pages/{page}"' in main


def test_ui_r1_analysis_workspace_reuses_existing_analysis_graph_and_timeline():
    qml = _read("pages/AnalysisWorkspace.qml")

    assert 'return "Analysis.qml"' in qml
    assert 'return "Graph.qml"' in qml
    assert 'return "Timeline.qml"' in qml

    for key, label in (
        ("intelligence", "Intelligence"),
        ("graph", "Graph"),
        ("timeline", "Timeline"),
        ("map", "Map"),
        ("media", "Media"),
    ):
        assert f'{{ key: "{key}", label: "{label}"' in qml


def test_ui_r1_map_and_media_are_foundations_not_fake_data_views():
    qml = _read("pages/AnalysisWorkspace.qml")

    assert 'root.activeWorkspace === "map" || root.activeWorkspace === "media"' in qml
    assert "GEO enrichment, satellite layers" in qml
    assert "images, video and audio" in qml
    assert "FOUNDATION READY · DATA CONNECTION NEXT" in qml


def test_ui_r1_source_center_remains_reachable_from_sidebar_status():
    qml = _read("components/Sidebar.qml")

    assert 'onClicked: root.navigate("sources")' in qml
    assert 'ToolTip.text: "Open Source Center"' in qml

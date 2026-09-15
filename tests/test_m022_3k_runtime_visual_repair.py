from pathlib import Path
from PIL import Image


def test_dashboard_uses_live_case_row_contract_and_is_not_hidden_by_animation():
    dashboard = Path("app/interface/desktop/qml/pages/Dashboard.qml").read_text(encoding="utf-8")
    assert "opacity: 1" in dashboard
    assert "titleText:" not in dashboard
    assert "subtitleText:" not in dashboard
    assert "stateText:" not in dashboard
    assert "metaText:" not in dashboard
    assert 'name: String(modelData.title || "Untitled investigation")' in dashboard
    assert 'detail: String(modelData.detail || "No description")' in dashboard
    assert 'priority: String(modelData.status || "Active")' in dashboard
    assert "desktopBridge.openCase(caseId)" in dashboard


def test_global_map_is_visible_but_still_background_styled():
    main = Path("app/interface/desktop/qml/Main.qml").read_text(encoding="utf-8")
    world = Path("app/interface/desktop/assets/images/world_network.svg").read_text(encoding="utf-8")
    assert 'source: "../assets/images/world_network.svg"' in main
    assert 'opacity: window.currentPage === "overview" ? 0.40 : 0.31' in main
    assert 'fill-opacity="0.72"' in world
    assert world.count("<path") > 100


def test_sidebar_logo_is_high_resolution_crisp_alpha_asset():
    sidebar = Path("app/interface/desktop/qml/components/Sidebar.qml").read_text(encoding="utf-8")
    logo_path = Path("app/interface/desktop/assets/icons/logo_shirt_mark.png")
    with Image.open(logo_path) as logo:
        assert logo.size == (512, 512)
        assert logo.mode == "RGBA"
        alpha = logo.getchannel("A")
        assert alpha.getextrema() == (0, 255)
    assert "mipmap: true" in sidebar
    assert "sourceSize.width: 512" in sidebar

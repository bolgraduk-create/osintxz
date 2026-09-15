from __future__ import annotations

from pathlib import Path


def test_reference_dashboard_layout_and_brand_assets_are_wired():
    root = Path("app/interface/desktop")
    dashboard = (root / "qml/pages/Dashboard.qml").read_text(encoding="utf-8")
    main = (root / "qml/Main.qml").read_text(encoding="utf-8")
    sidebar = (root / "qml/components/Sidebar.qml").read_text(encoding="utf-8")

    assert 'title: "Selected Person"' in dashboard
    assert 'title: "Linked Profiles & Accounts"' in dashboard
    assert 'text: "\\\"Information creates advantage.\\\""' in dashboard
    assert 'text: "— OSINTXZ"' in dashboard
    assert "EntityWeb" in dashboard
    assert 'text: "Full Graph"' in dashboard

    assert 'source: "../assets/images/world_network.svg"' in main
    assert 'source: "../../assets/icons/logo_shirt_mark.png"' in sidebar
    assert (root / "assets/images/world_network.svg").is_file()
    assert (root / "assets/icons/logo_shirt_mark.png").is_file()


def test_person_page_prioritizes_accounts_and_large_attachments_without_graph():
    person = Path("app/interface/desktop/qml/pages/Person.qml").read_text(encoding="utf-8")

    assert 'title: "Profiles & Accounts"' in person
    assert 'title: "Photos & Files"' in person
    assert "property var profileRows" in person
    assert "function buildProfileRows()" in person
    assert "root.profileRows.length" in person
    assert "width: 72" in person and "height: 72" in person
    assert 'title: "Account Map"' not in person
    assert "EntityWeb" not in person


def test_world_map_asset_is_realistic_vector_not_old_placeholder():
    world_map = Path("app/interface/desktop/assets/images/world_network.svg").read_text(encoding="utf-8")
    assert world_map.count("<path") > 100
    assert "<circle" in world_map
    assert "<line" in world_map
    assert "#2d8cff" in world_map

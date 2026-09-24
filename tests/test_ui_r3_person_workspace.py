from __future__ import annotations

from pathlib import Path


PERSON_QML = Path("app/interface/desktop/qml/pages/Person.qml")


def _qml() -> str:
    return PERSON_QML.read_text(encoding="utf-8")


def test_ui_r3_person_workspace_has_seven_primary_tabs():
    qml = _qml()

    assert 'property string activePersonTab: "overview"' in qml
    for key, label in (
        ("overview", "Overview"),
        ("accounts", "Accounts"),
        ("media", "Media"),
        ("locations", "Locations"),
        ("relations", "Relations"),
        ("evidence", "Evidence"),
        ("timeline", "Timeline"),
    ):
        assert f'{{ key: "{key}", label: "{label}"' in qml


def test_ui_r3_preserves_existing_person_card_workflows_and_titles():
    qml = _qml()

    for expected in (
        'title: "Person Overview"',
        'title: "Intelligence Summary"',
        'title: "Core Intelligence"',
        'title: "Accounts & Profiles"',
        'title: "Corroborating Mentions"',
        'title: "Photos & Files"',
        'title: "Intelligence Attributes"',
        'title: "Supporting Evidence"',
        'text: "+  Add item"',
        'text: "+  From intelligence"',
        "desktopBridge.reviewIdentityCandidate",
        "desktopBridge.identityReviewHistory",
        "desktopBridge.addExistingDataToPerson",
        "desktopBridge.openManagedAttachment",
    ):
        assert expected in qml


def test_ui_r3_routes_existing_sections_through_person_tabs():
    qml = _qml()

    for expression in (
        'visible: root.activePersonTab === "overview"',
        'visible: root.activePersonTab === "accounts"',
        'visible: root.activePersonTab === "media"',
        'visible: root.activePersonTab === "locations"',
        'visible: root.activePersonTab === "relations"',
        'visible: root.activePersonTab === "evidence"',
        'visible: root.activePersonTab === "timeline"',
    ):
        assert expression in qml

    assert 'visible: root.activePersonTab === "relations" || root.activePersonTab === "evidence"' in qml


def test_ui_r3_locations_use_real_person_location_rows():
    qml = _qml()

    assert 'title: "Person Locations"' in qml
    assert "model: root.locationRows" in qml
    assert "root.locationRows.length" in qml
    assert 'title: "No linked locations"' in qml
    assert "root.intelligenceRowDetail(personLocationRow.modelData)" in qml


def test_ui_r3_timeline_is_explicit_foundation_not_fake_person_events():
    qml = _qml()

    assert 'title: "Person Timeline"' in qml
    assert 'subtitle: "Person-scoped temporal workspace foundation"' in qml
    assert 'text: "Open Investigation Timeline"' in qml
    assert 'desktopBridge.navigateTo("timeline")' in qml
    assert "without inventing attribution" in qml


def test_ui_r3_tab_counts_reuse_existing_person_data_models():
    qml = _qml()

    assert "function personTabCount(tab)" in qml
    assert 'if (tab === "accounts")' in qml
    assert "root.profileRows.length + root.mentionRows.length" in qml
    assert "root.attachmentRows.length" in qml
    assert "root.locationRows.length" in qml
    assert "root.relatedRows.length" in qml
    assert "root.evidenceRows.length" in qml


def test_ui_r3_keeps_identity_anchor_visible_as_left_panel():
    qml = _qml()

    assert 'title: "Person Overview"' in qml
    assert 'subtitle: "Identity anchor · always visible while exploring this person"' in qml
    assert "CircularAvatar" in qml
    assert 'text: "NORMALIZED IDENTITY"' not in qml
    assert '{ label: "NORMALIZED IDENTITY"' in qml

from pathlib import Path


def _qml() -> str:
    return Path("app/interface/desktop/qml/pages/Person.qml").read_text(encoding="utf-8")


def test_person_card_v2_marker_and_summary_exist():
    qml = _qml()
    assert "R13.23 PERSON CARD V2" in qml
    assert 'title: "Intelligence Summary"' in qml
    assert 'title: "Core Intelligence"' in qml
    assert 'title: "Accounts & Profiles"' in qml
    assert 'title: "Intelligence Attributes"' in qml


def test_person_card_v2_has_structured_sections():
    qml = _qml()
    for token in (
        "contactRows",
        "organizationRows",
        "locationRows",
        "technicalRows",
        "intelligenceGroups",
        "summaryMetrics",
        "rebuildIntelligenceSections",
        "intelligenceRowDetail",
    ):
        assert token in qml


def test_person_card_v2_preserves_provenance_language():
    qml = _qml()
    assert "provenance remains authoritative" in qml
    assert "analyst linked" in qml
    assert "Entity confidence" in qml


def test_person_card_v2_keeps_existing_attachment_and_selection_workflows():
    qml = _qml()
    assert "desktopBridge.addPersonAttachment" in qml
    assert "desktopBridge.addExistingDataToPerson" in qml
    assert 'text: "+  From intelligence"' in qml
    assert 'text: "+  Add item"' in qml


def test_person_card_v2_keeps_safe_empty_states_and_scrolling():
    qml = _qml()
    assert "No linked contacts" in qml
    assert "No linked organizations" in qml
    assert "No linked locations" in qml
    assert "No web / network identifiers" in qml
    assert "ScrollBar.vertical" in qml

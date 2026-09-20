from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "app/interface/desktop/qml/pages/Person.qml"


def _qml() -> str:
    return QML.read_text(encoding="utf-8")


def test_person_card_keeps_split_web_and_technical_sections():
    qml = _qml()
    assert 'title: "WEB PROFILES / PAGES"' in qml
    assert 'title: "TECHNICAL"' in qml


def test_person_card_keeps_legacy_safe_empty_state_contract():
    qml = _qml()
    assert "No web / network identifiers" in qml


def test_person_card_keeps_mentions_integration():
    qml = _qml()
    assert "Corroborating Mentions" in qml
    assert "R13.23.1 PERSON CARD POLISH + MENTIONS" in qml

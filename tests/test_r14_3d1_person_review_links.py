from pathlib import Path


def test_identity_review_candidates_expose_open_external_link_action():
    qml = Path(
        "app/interface/desktop/qml/pages/Person.qml"
    ).read_text(encoding="utf-8")

    for token in (
        "property bool hasExternalUrl:",
        "id: openExternalButton",
        'text: "Open"',
        "desktopBridge.openExternalUrl(",
        "String(candidateRow.modelData.url || \"\")",
        "visible: candidateRow.hasExternalUrl",
    ):
        assert token in qml


def test_open_action_does_not_replace_identity_review_actions():
    qml = Path(
        "app/interface/desktop/qml/pages/Person.qml"
    ).read_text(encoding="utf-8")

    for token in (
        'text: "Confirm"',
        'text: "Review"',
        'text: "Reject"',
        'text: "History"',
        "id: addExistingButton",
    ):
        assert token in qml


def test_external_url_bridge_remains_http_https_only():
    bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")

    assert "def openExternalUrl(self, value: str) -> bool:" in bridge
    assert "Only explicit http:// or https:// links can be opened." in bridge
    assert "QDesktopServices.openUrl(QUrl(normalized))" in bridge
    assert 'parsed.scheme.lower() not in {"http", "https"}' in bridge

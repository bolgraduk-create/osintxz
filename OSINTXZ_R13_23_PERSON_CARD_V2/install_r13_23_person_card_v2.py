from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PATCH_MARKER = "// R13.23 PERSON CARD V2"

PROPERTY_MARKER = '    property var metadataRows: person.metadataRows || []\n'
PROPERTY_INSERT = '''    property var metadataRows: person.metadataRows || []
    // R13.23 PERSON CARD V2
    property var contactRows: []
    property var organizationRows: []
    property var locationRows: []
    property var technicalRows: []
    property var otherIntelligenceRows: []
    property var intelligenceGroups: []
    property var summaryMetrics: []
'''

FUNCTION_MARKER = '    function attachmentKind() {\n'
FUNCTION_INSERT = r'''    function rebuildIntelligenceSections() {
        var contacts = []
        var organizations = []
        var locations = []
        var technical = []
        var other = []

        for (var i = 0; i < root.relatedRows.length; ++i) {
            var item = root.relatedRows[i]
            var rawType = String(item.rawType || item.type || "")
                .toLowerCase().replace(/ /g, "_")

            if (rawType === "username" || rawType === "account")
                continue
            if (rawType === "email" || rawType === "phone")
                contacts.push(item)
            else if (rawType === "organization")
                organizations.push(item)
            else if (rawType === "location" || rawType === "address")
                locations.push(item)
            else if (rawType === "domain" || rawType === "url" || rawType === "ip")
                technical.push(item)
            else
                other.push(item)
        }

        root.contactRows = contacts
        root.organizationRows = organizations
        root.locationRows = locations
        root.technicalRows = technical
        root.otherIntelligenceRows = other
        root.intelligenceGroups = [
            { title: "CONTACTS", rows: contacts, empty: "No linked contacts" },
            { title: "ORGANIZATIONS", rows: organizations, empty: "No linked organizations" },
            { title: "LOCATIONS", rows: locations, empty: "No linked locations" },
            { title: "WEB & TECHNICAL", rows: technical, empty: "No web / network identifiers" }
        ]
        root.summaryMetrics = [
            { label: "Accounts", value: root.profileRows.length },
            { label: "Contacts", value: contacts.length },
            { label: "Organizations", value: organizations.length },
            { label: "Locations", value: locations.length },
            { label: "Evidence", value: root.evidenceRows.length },
            { label: "Review", value: root.profileCandidates.length }
        ]
    }

    function intelligenceRowDetail(item) {
        var parts = []
        var rawType = String(item.rawType || item.type || "").replace(/_/g, " ")
        if (rawType.length) parts.push(rawType)
        if (item.basis === "analyst_selected") parts.push("analyst linked")
        else if (item.basis === "manual") parts.push("manual")
        else if (item.basis) parts.push(String(item.basis))
        if (item.evidenceTitle) parts.push(String(item.evidenceTitle))
        return parts.join(" · ")
    }

    function attachmentKind() {
'''

RELOAD_OLD = '''        root.metadataRows = root.person.metadataRows || []
        root.profileRows = root.buildProfileRows()
'''
RELOAD_NEW = '''        root.metadataRows = root.person.metadataRows || []
        root.profileRows = root.buildProfileRows()
        root.rebuildIntelligenceSections()
'''

PROFILE_PANEL_MARKER = '''                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(420, Math.max(210, 96 + root.profileRows.length * 66))
'''

SUMMARY_AND_CORE = r'''                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 126
                    Layout.minimumHeight: 126
                    Layout.maximumHeight: 126
                    title: "Intelligence Summary"
                    subtitle: "Structured view of linked intelligence · provenance remains authoritative"
                    iconSource: "../../assets/icons/chart_blue.svg"

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8

                        Repeater {
                            model: root.summaryMetrics
                            delegate: Rectangle {
                                id: summaryMetric
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: 8
                                color: "#0d1f2c"
                                border.width: 1
                                border.color: Theme.border
                                Text {
                                    x: 12; y: 11
                                    text: String(summaryMetric.modelData.label || "Metric").toUpperCase()
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    font.letterSpacing: 0.8
                                }
                                Text {
                                    x: 12; y: 34
                                    text: String(summaryMetric.modelData.value || 0)
                                    color: Theme.textPrimary
                                    font.pixelSize: 22
                                    font.weight: Font.DemiBold
                                }
                            }
                        }
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 352
                    Layout.minimumHeight: 352
                    Layout.maximumHeight: 352
                    title: "Core Intelligence"
                    subtitle: "Contacts, organizations, locations and technical identifiers grouped by type"
                    iconSource: "../../assets/icons/users_cyan.svg"

                    GridLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        columns: 2
                        rowSpacing: 10
                        columnSpacing: 10

                        Repeater {
                            model: root.intelligenceGroups
                            delegate: Rectangle {
                                id: intelligenceGroup
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 126
                                radius: 8
                                color: "#0d1f2c"
                                border.width: 1
                                border.color: Theme.border

                                Text {
                                    x: 12; y: 10
                                    width: parent.width - 60
                                    text: String(intelligenceGroup.modelData.title || "INTELLIGENCE")
                                    color: Theme.textSecondary
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.8
                                    elide: Text.ElideRight
                                }
                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 12
                                    y: 10
                                    text: String((intelligenceGroup.modelData.rows || []).length)
                                    color: Theme.accent
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                }

                                Column {
                                    x: 12
                                    y: 34
                                    width: parent.width - 24
                                    spacing: 5

                                    Repeater {
                                        model: (intelligenceGroup.modelData.rows || []).slice(0, 3)
                                        delegate: Item {
                                            id: groupedRow
                                            required property var modelData
                                            width: parent.width
                                            height: 25
                                            Text {
                                                width: parent.width
                                                text: String(groupedRow.modelData.value || "—")
                                                color: groupedRow.modelData.url ? Theme.accent : Theme.textPrimary
                                                font.pixelSize: 10
                                                font.weight: Font.Medium
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                y: 13
                                                width: parent.width
                                                text: root.intelligenceRowDetail(groupedRow.modelData)
                                                color: Theme.textMuted
                                                font.pixelSize: 7
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }

                                    Text {
                                        visible: (intelligenceGroup.modelData.rows || []).length === 0
                                        text: String(intelligenceGroup.modelData.empty || "No linked intelligence")
                                        color: Theme.textMuted
                                        font.pixelSize: 9
                                    }
                                    Text {
                                        visible: (intelligenceGroup.modelData.rows || []).length > 3
                                        text: "+ " + String((intelligenceGroup.modelData.rows || []).length - 3) + " more"
                                        color: Theme.accent
                                        font.pixelSize: 8
                                    }
                                }
                            }
                        }
                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(420, Math.max(210, 96 + root.profileRows.length * 66))
'''


def patch_person_qml(text: str) -> str:
    if PATCH_MARKER in text:
        return text

    required = [PROPERTY_MARKER, FUNCTION_MARKER, RELOAD_OLD, PROFILE_PANEL_MARKER]
    missing = [marker[:80] for marker in required if marker not in text]
    if missing:
        raise RuntimeError(
            "Person.qml baseline is not compatible with R13.23. Missing patch anchors: "
            + repr(missing)
        )

    text = text.replace(PROPERTY_MARKER, PROPERTY_INSERT, 1)
    text = text.replace(FUNCTION_MARKER, FUNCTION_INSERT, 1)
    text = text.replace(RELOAD_OLD, RELOAD_NEW, 1)
    text = text.replace(PROFILE_PANEL_MARKER, SUMMARY_AND_CORE, 1)

    text = text.replace(
        '+ "Confidence " + String(root.person.confidenceText || "—")',
        '+ "Entity confidence " + String(root.person.confidenceText || "—")',
        1,
    )
    text = text.replace(
        'text: "PERSON · " + String(root.person.confidenceText || "—")',
        'text: "PERSON ENTITY · " + String(root.person.confidenceText || "—")',
        1,
    )
    text = text.replace('title: "Profiles & Accounts"', 'title: "Accounts & Profiles"', 1)
    text = text.replace('title: "Related Identifiers"', 'title: "Intelligence Attributes"', 1)
    text = text.replace(
        'subtitle: "Connected through shared supporting evidence"',
        'subtitle: "Evidence-linked identifiers · manual and analyst-linked items remain labeled"',
        1,
    )
    return text


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Install OSINTXZ R13.23 Person Intelligence Card v2")
    parser.add_argument("project_root")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    person_qml = root / "app/interface/desktop/qml/pages/Person.qml"
    search_qml = root / "app/interface/desktop/qml/pages/Search.qml"
    if not person_qml.is_file():
        raise SystemExit(f"Person.qml not found: {person_qml}")
    if not search_qml.is_file():
        raise SystemExit(f"Search.qml not found: {search_qml}")
    if "Mentions" not in search_qml.read_text(encoding="utf-8"):
        raise SystemExit("R13.22 baseline was not detected in Search.qml. Install R13.22 first.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_dir = root / "storage/patch_backups" / f"r13_23_{timestamp}"
    backup_target = backup_dir / "app/interface/desktop/qml/pages/Person.qml"
    backup_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(person_qml, backup_target)

    original = person_qml.read_text(encoding="utf-8")
    patched = patch_person_qml(original)
    person_qml.write_text(patched, encoding="utf-8")

    package_root = Path(__file__).resolve().parent
    test_src = package_root / "payload/tests/test_r13_23_person_card_v2.py"
    test_dst = root / "tests/test_r13_23_person_card_v2.py"
    test_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(test_src, test_dst)

    print("R13.23 Person Intelligence Card v2 installed.")
    print(f"Backup: {backup_dir}")
    print(f"Person.qml SHA-256: {sha256(person_qml)}")

    if args.run_tests:
        tests = [
            "tests/test_r13_23_person_card_v2.py",
            "tests/test_qml_desktop_bridge.py",
        ]
        existing = [item for item in tests if (root / item).is_file()]
        cmd = [sys.executable, "-m", "pytest", "-q", *existing]
        print("Running:", " ".join(cmd))
        return subprocess.call(cmd, cwd=root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

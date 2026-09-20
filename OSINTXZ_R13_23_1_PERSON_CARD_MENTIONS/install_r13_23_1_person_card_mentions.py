from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

PATCH = "R13.23.1"
PERSON_MARKER = "// R13.23.1 PERSON CARD POLISH + MENTIONS"
SEARCH_MARKER = "// R13.23.1 ADD MENTION TO PERSON"
DESKTOP_MARKER = "# R13.23.1 PERSON MENTION SNAPSHOT"
BRIDGE_MARKER = "# R13.23.1 PERSON MENTION ACTIONS"


def python_for(root: Path) -> Path:
    candidate = root / ".venv" / "Scripts" / "python.exe"
    return candidate if candidate.is_file() else Path(sys.executable)


def replace_once(text: str, old: str, new: str, *, name: str) -> str:
    if old not in text:
        raise RuntimeError(f"{name}: patch anchor not found")
    return text.replace(old, new, 1)


def patch_investigation_bridge(text: str) -> str:
    if BRIDGE_MARKER in text:
        return text

    imports_old = '''from datetime import datetime
import logging
from typing import Any

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot
'''
    imports_new = '''from datetime import datetime
import logging
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from app.application.person_mention_selection_service import (
    PersonMentionSelectionService,
)
from app.models.entity import EntityType
'''
    text = replace_once(text, imports_old, imports_new, name="investigation bridge imports")

    success_old = '''        run.update(
            {
                "hasRun": True,
                "phase": "completed",
'''
    success_new = '''        run.update(
            {
                "hasRun": True,
                "caseId": str(self._context.get("caseId") or ""),
                "phase": "completed",
'''
    text = replace_once(text, success_old, success_new, name="investigation bridge case id")

    method_anchor = '''    def _set_message(self, value: str) -> None:
'''
    methods = r'''    # R13.23.1 PERSON MENTION ACTIONS
    @Slot(str, result="QVariantList")
    def personOptions(self, case_id: str) -> list[dict[str, str]]:
        normalized = str(case_id or "").strip()
        if not normalized:
            return []
        entity_service = getattr(self._container, "entity_service", None)
        if entity_service is None:
            return []
        try:
            case_uuid = UUID(normalized)
        except (TypeError, ValueError, AttributeError):
            return []

        try:
            try:
                rows = list(
                    entity_service.get_page(
                        limit=250,
                        offset=0,
                        case_id=case_uuid,
                        entity_types=(EntityType.PERSON,),
                    )
                    or []
                )
            except TypeError:
                rows = [
                    item
                    for item in list(entity_service.get_case_entities(case_uuid) or [])
                    if str(
                        getattr(
                            getattr(item, "entity_type", None),
                            "value",
                            getattr(item, "entity_type", ""),
                        )
                        or ""
                    ) == EntityType.PERSON.value
                ]
        except Exception:
            LOGGER.exception("Unable to load person options for mention selection")
            return []

        result = [
            {
                "id": str(getattr(item, "id", "") or ""),
                "label": str(getattr(item, "value", "") or "Unnamed person"),
            }
            for item in rows
            if getattr(item, "id", None) is not None
        ]
        result.sort(key=lambda item: (item["label"].casefold(), item["id"]))
        return result

    @Slot(str, "QVariantMap", result="QVariantMap")
    def addMentionToPerson(self, person_id: str, mention: object) -> dict[str, Any]:
        normalized_person_id = str(person_id or "").strip()
        payload = dict(mention) if isinstance(mention, dict) else {}
        if not normalized_person_id:
            return {"ok": False, "error": "Select a person first."}
        if not payload:
            return {"ok": False, "error": "The mention payload is unavailable."}

        entity_service = getattr(self._container, "entity_service", None)
        source_service = getattr(self._container, "source_service", None)
        evidence_service = getattr(self._container, "evidence_service", None)
        link_service = getattr(self._container, "evidence_link_service", None)
        if any(service is None for service in (
            entity_service,
            source_service,
            evidence_service,
            link_service,
        )):
            return {"ok": False, "error": "Mention persistence services are unavailable."}

        try:
            person = entity_service.get_entity(UUID(normalized_person_id))
        except Exception as exc:
            LOGGER.exception("Unable to resolve PERSON for corroborating mention")
            return {"ok": False, "error": f"Unable to resolve person: {exc}"}
        if person is None:
            return {"ok": False, "error": "The selected person no longer exists."}

        run_case_id = str(self._run.get("caseId") or "").strip()
        person_case_id = str(getattr(person, "case_id", "") or "")
        if run_case_id and person_case_id != run_case_id:
            return {
                "ok": False,
                "error": "The selected person belongs to a different investigation.",
            }

        service = PersonMentionSelectionService(
            source_service=source_service,
            evidence_service=evidence_service,
            evidence_link_service=link_service,
        )
        try:
            result = service.add(person=person, mention=payload)
            if result.duplicate:
                return {
                    "ok": True,
                    "duplicate": True,
                    "message": "This mention is already attached to the person.",
                    "evidenceId": result.evidence_id,
                }
            self._container.commit()
        except Exception as exc:
            try:
                self._container.rollback()
            except Exception:
                LOGGER.debug("Rollback after mention selection failed", exc_info=True)
            LOGGER.exception("Unable to attach corroborating mention to PERSON")
            return {"ok": False, "error": str(exc)}

        self._set_message("Corroborating mention added to person profile.")
        return {
            "ok": True,
            "duplicate": False,
            "message": "Corroborating mention added to person profile.",
            "evidenceId": result.evidence_id,
        }

'''
    text = replace_once(text, method_anchor, methods + method_anchor, name="investigation bridge methods")
    return text


def patch_search_qml(text: str) -> str:
    if SEARCH_MARKER in text:
        return text

    prop_old = '''    property bool busy: investigationSearchBridge.busy
'''
    prop_new = '''    property bool busy: investigationSearchBridge.busy
    // R13.23.1 ADD MENTION TO PERSON
    property var selectedMention: ({})
    property var mentionPersonOptions: []
    property string mentionLinkError: ""
'''
    text = replace_once(text, prop_old, prop_new, name="Search.qml mention properties")

    opacity_anchor = '''    opacity: 0
'''
    functions = r'''    function openMentionPersonDialog(row) {
        root.selectedMention = row || ({})
        root.mentionLinkError = ""
        root.mentionPersonOptions = investigationSearchBridge.personOptions(desktopBridge.currentCaseId)
        mentionPersonDialog.open()
    }

'''
    text = replace_once(text, opacity_anchor, functions + opacity_anchor, name="Search.qml mention function")

    right_text_old = '''                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 16
                                anchors.top: statusBadge.bottom
                                anchors.topMargin: 10
                                width: row.rightColumnWidth - 12
'''
    right_text_new = '''                            Text {
                                visible: root.activeTab !== "mentions"
                                anchors.right: parent.right
                                anchors.rightMargin: 16
                                anchors.top: statusBadge.bottom
                                anchors.topMargin: 10
                                width: row.rightColumnWidth - 12
'''
    text = replace_once(text, right_text_old, right_text_new, name="Search.qml right metadata")

    mouse_old = '''                            MouseArea {
                                id: rowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: row.modelData.url ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    if (row.modelData.url) desktopBridge.openExternalUrl(String(row.modelData.url))
                                }
                            }
'''
    mouse_new = r'''                            AppButton {
                                id: addMentionToPersonButton
                                visible: root.activeTab === "mentions"
                                anchors.right: parent.right
                                anchors.rightMargin: 16
                                anchors.top: statusBadge.bottom
                                anchors.topMargin: 8
                                width: Math.min(126, row.rightColumnWidth - 8)
                                height: 30
                                text: "Add to person"
                                primary: true
                                onClicked: root.openMentionPersonDialog(row.modelData)
                            }
                            MouseArea {
                                id: rowMouse
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                anchors.right: addMentionToPersonButton.visible ? addMentionToPersonButton.left : parent.right
                                hoverEnabled: true
                                cursorShape: row.modelData.url ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    if (row.modelData.url) desktopBridge.openExternalUrl(String(row.modelData.url))
                                }
                            }
'''
    text = replace_once(text, mouse_old, mouse_new, name="Search.qml mention button")

    dialog = r'''

    Dialog {
        id: mentionPersonDialog
        modal: true
        anchors.centerIn: parent
        width: Math.min(560, root.width - 80)
        height: 340
        padding: 0
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            radius: 12
            color: Theme.surface
            border.width: 1
            border.color: Theme.border
        }

        contentItem: ColumnLayout {
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                color: "transparent"
                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                Text { x: 20; y: 13; text: "Add mention to person"; color: Theme.textPrimary; font.pixelSize: 18; font.weight: Font.DemiBold }
                Text { x: 20; y: 41; width: parent.width - 40; text: "Creates analyst-selected provenance Evidence; it does not mark identity as verified."; color: Theme.textMuted; font.pixelSize: 9; elide: Text.ElideRight }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.topMargin: 14
                Layout.bottomMargin: 16
                spacing: 10

                Text { text: "MENTION"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                Text {
                    Layout.fillWidth: true
                    text: String(root.selectedMention.title || "Corroborating mention")
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: String(root.selectedMention.mentionSummary || "")
                    color: Theme.textSecondary
                    font.pixelSize: 9
                    wrapMode: Text.Wrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }

                Text { text: "PERSON"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                AppComboBox {
                    id: mentionPersonBox
                    Layout.fillWidth: true
                    model: root.mentionPersonOptions
                    textRole: "label"
                }

                Text {
                    Layout.fillWidth: true
                    visible: root.mentionPersonOptions.length === 0
                    text: "No PERSON entities are available in the selected investigation."
                    color: Theme.warning
                    font.pixelSize: 9
                    wrapMode: Text.Wrap
                }
                Text {
                    Layout.fillWidth: true
                    visible: root.mentionLinkError.length > 0
                    text: root.mentionLinkError
                    color: Theme.danger
                    font.pixelSize: 9
                    wrapMode: Text.Wrap
                }

                Item { Layout.fillHeight: true }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    AppButton { text: "Cancel"; Layout.preferredWidth: 96; onClicked: mentionPersonDialog.close() }
                    AppButton {
                        text: "Add mention"
                        primary: true
                        Layout.preferredWidth: 120
                        enabled: root.mentionPersonOptions.length > 0 && mentionPersonBox.currentIndex >= 0
                        onClicked: {
                            root.mentionLinkError = ""
                            var selected = root.mentionPersonOptions[mentionPersonBox.currentIndex]
                            var result = investigationSearchBridge.addMentionToPerson(
                                selected ? String(selected.id || "") : "",
                                root.selectedMention
                            )
                            if (result && result.ok) {
                                mentionPersonDialog.close()
                            } else {
                                root.mentionLinkError = result && result.error
                                    ? String(result.error)
                                    : "Unable to attach mention."
                            }
                        }
                    }
                }
            }
        }
    }
'''
    idx = text.rfind("\n}")
    if idx < 0:
        raise RuntimeError("Search.qml root closing brace not found")
    text = text[:idx] + dialog + text[idx:]
    return text


def patch_desktop_bridge(text: str) -> str:
    if DESKTOP_MARKER in text:
        return text

    init_old = '''        evidence_rows: list[dict[str, Any]] = []
        related_rows: list[dict[str, Any]] = []
'''
    init_new = '''        evidence_rows: list[dict[str, Any]] = []
        # R13.23.1 PERSON MENTION SNAPSHOT
        mention_rows: list[dict[str, Any]] = []
        related_rows: list[dict[str, Any]] = []
'''
    text = replace_once(text, init_old, init_new, name="DesktopBridge mention rows")

    evidence_old = '''            evidence_rows.append(evidence_row)
            if preview_url:
'''
    evidence_new = r'''            evidence_rows.append(evidence_row)
            if evidence_workflow == "person_mention_selection":
                raw_mention = evidence_metadata.get("mention")
                mention = raw_mention if isinstance(raw_mention, dict) else {}
                raw_signals = mention.get("signals") or []
                signals = [
                    str(item).strip()
                    for item in list(raw_signals)
                    if str(item or "").strip()
                ][:8] if isinstance(raw_signals, (list, tuple, set, frozenset)) else []
                try:
                    mention_score = float(mention.get("score") or 0.0)
                except (TypeError, ValueError):
                    mention_score = 0.0
                mention_rows.append({
                    "id": str(getattr(evidence, "id", "") or ""),
                    "title": str(mention.get("title") or evidence_title),
                    "detail": str(mention.get("detail") or ""),
                    "summary": str(mention.get("summary") or " · ".join(signals[:4])),
                    "url": self._normalized_external_url(str(mention.get("url") or "")) or "",
                    "source": str(mention.get("source") or "Corroborating mention"),
                    "signals": signals,
                    "score": round(max(0.0, min(100.0, mention_score)), 1),
                    "lane": str(mention.get("lane") or ""),
                    "status": str(mention.get("status") or "Corroborating mention"),
                    "date": self._date_text(getattr(evidence, "created_at", None)),
                    "basis": "analyst_selected",
                })
            if preview_url:
'''
    text = replace_once(text, evidence_old, evidence_new, name="DesktopBridge mention extraction")

    return_old = '''            "evidence": evidence_rows[:50],
            "relatedEntities": related_rows[:100],
'''
    return_new = '''            "evidence": evidence_rows[:50],
            "mentions": mention_rows[:40],
            "relatedEntities": related_rows[:100],
'''
    text = replace_once(text, return_old, return_new, name="DesktopBridge mention payload")
    return text


def patch_person_qml(text: str) -> str:
    if PERSON_MARKER in text:
        return text
    if "// R13.23 PERSON CARD V2" not in text:
        raise RuntimeError("R13.23 Person Card v2 baseline is required")

    prop_old = '''    property var summaryMetrics: []
'''
    prop_new = '''    property var summaryMetrics: []
    // R13.23.1 PERSON CARD POLISH + MENTIONS
    property var webRows: []
    property var mentionRows: []
    property var reviewRows: []
'''
    text = replace_once(text, prop_old, prop_new, name="Person.qml v2.1 properties")

    start = text.find("    function rebuildIntelligenceSections() {")
    end = text.find("    function intelligenceRowDetail(item) {", start)
    if start < 0 or end < 0:
        raise RuntimeError("Person.qml R13.23 intelligence function anchors not found")
    functions = r'''    function normalizeReviewKey(value) {
        var text = String(value || "").trim().toLowerCase()
        while (text.length > 1 && text.endsWith("/")) text = text.slice(0, -1)
        return text
    }

    function rebuildReviewRows() {
        var known = ({})
        function addKnown(value) {
            var key = root.normalizeReviewKey(value)
            if (key.length) known[key] = true
        }

        addKnown(root.person.title)
        addKnown(root.person.normalizedValue)
        for (var i = 0; i < root.relatedRows.length; ++i) {
            addKnown(root.relatedRows[i].value)
            addKnown(root.relatedRows[i].url)
        }
        for (var j = 0; j < root.links.length; ++j) {
            addKnown(root.links[j].value)
            addKnown(root.links[j].url)
        }
        for (var k = 0; k < root.profileRows.length; ++k) {
            addKnown(root.profileRows[k].value)
            addKnown(root.profileRows[k].url)
        }

        var review = []
        for (var n = 0; n < root.profileCandidates.length; ++n) {
            var candidate = root.profileCandidates[n]
            var originKey = root.normalizeReviewKey(candidate.origin)
            var valueKey = root.normalizeReviewKey(candidate.value)
            var urlKey = root.normalizeReviewKey(candidate.url)
            if ((originKey.length && known[originKey])
                    || (valueKey.length && known[valueKey])
                    || (urlKey.length && known[urlKey])) {
                review.push(candidate)
            }
        }
        root.reviewRows = review
    }

    function rebuildIntelligenceSections() {
        var contacts = []
        var organizations = []
        var locations = []
        var web = []
        var technical = []
        var other = []
        var profileKeys = ({})

        for (var p = 0; p < root.profileRows.length; ++p) {
            var profileKey = root.normalizeReviewKey(root.profileRows[p].url || root.profileRows[p].value)
            if (profileKey.length) profileKeys[profileKey] = true
        }

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
            else if (rawType === "url") {
                var webKey = root.normalizeReviewKey(item.url || item.value)
                if (!webKey.length || !profileKeys[webKey]) web.push(item)
            }
            else if (rawType === "domain" || rawType === "ip" || rawType === "asn" || rawType === "hash")
                technical.push(item)
            else
                other.push(item)
        }

        root.contactRows = contacts
        root.organizationRows = organizations
        root.locationRows = locations
        root.webRows = web
        root.technicalRows = technical
        root.otherIntelligenceRows = other
        root.rebuildReviewRows()

        var groups = [
            { title: "CONTACTS", rows: contacts, empty: "No linked contacts" },
            { title: "ORGANIZATIONS", rows: organizations, empty: "No linked organizations" },
            { title: "LOCATIONS", rows: locations, empty: "No linked locations" },
            { title: "WEB PROFILES / PAGES", rows: web, empty: "No additional linked pages" },
            { title: "TECHNICAL", rows: technical, empty: "No domain / network identifiers" }
        ]
        if (other.length > 0)
            groups.push({ title: "OTHER INTELLIGENCE", rows: other, empty: "" })
        root.intelligenceGroups = groups
        root.summaryMetrics = [
            { label: "Accounts", value: root.profileRows.length },
            { label: "Contacts", value: contacts.length },
            { label: "Organizations", value: organizations.length },
            { label: "Locations", value: locations.length },
            { label: "Mentions", value: root.mentionRows.length },
            { label: "Evidence", value: root.evidenceRows.length },
            { label: "Review", value: root.reviewRows.length }
        ]
    }

'''
    text = text[:start] + functions + text[end:]

    reload_old = '''        root.evidenceRows = root.person.evidence || []
        root.relatedRows = root.person.relatedEntities || []
'''
    reload_new = '''        root.evidenceRows = root.person.evidence || []
        root.mentionRows = root.person.mentions || []
        root.relatedRows = root.person.relatedEntities || []
'''
    text = replace_once(text, reload_old, reload_new, name="Person.qml mention reload")

    filtered_old = '''        if (!query.length) return root.profileCandidates
        var result = []
        for (var i = 0; i < root.profileCandidates.length; ++i) {
            var item = root.profileCandidates[i]
'''
    filtered_new = '''        if (!query.length) return root.reviewRows
        var result = []
        for (var i = 0; i < root.reviewRows.length; ++i) {
            var item = root.reviewRows[i]
'''
    text = replace_once(text, filtered_old, filtered_new, name="Person.qml review filter")

    text = replace_once(
        text,
        '''                    Layout.preferredHeight: 126
                    Layout.minimumHeight: 126
                    Layout.maximumHeight: 126
                    title: "Intelligence Summary"
''',
        '''                    Layout.preferredHeight: 166
                    Layout.minimumHeight: 166
                    Layout.maximumHeight: 166
                    title: "Intelligence Summary"
''',
        name="Person.qml summary height",
    )
    metric_old = '''                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: 8
'''
    metric_new = '''                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.minimumHeight: 72
                                radius: 8
'''
    text = replace_once(text, metric_old, metric_new, name="Person.qml metric height")

    core_old = '''                    Layout.preferredHeight: 352
                    Layout.minimumHeight: 352
                    Layout.maximumHeight: 352
                    title: "Core Intelligence"
                    subtitle: "Contacts, organizations, locations and technical identifiers grouped by type"
'''
    core_new = '''                    Layout.preferredHeight: Math.min(560, Math.max(352, 94 + Math.ceil(root.intelligenceGroups.length / 2) * 132))
                    Layout.minimumHeight: 352
                    Layout.maximumHeight: 560
                    title: "Core Intelligence"
                    subtitle: "Contacts, organizations, locations, web pages and technical identifiers grouped by type"
'''
    text = replace_once(text, core_old, core_new, name="Person.qml core intelligence height")

    mentions_panel = r'''                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(420, Math.max(210, 96 + root.mentionRows.length * 78))
                    Layout.minimumHeight: 210
                    Layout.maximumHeight: 420
                    title: "Corroborating Mentions"
                    subtitle: root.mentionRows.length > 0
                        ? String(root.mentionRows.length) + " analyst-linked multi-signal mention(s)"
                        : "Attach a multi-signal mention from Investigation Search"
                    iconSource: "../../assets/icons/search.svg"

                    Item {
                        anchors.fill: parent
                        EmptyState {
                            anchors.fill: parent
                            anchors.margins: 14
                            visible: root.mentionRows.length === 0
                            iconSource: "../../assets/icons/search.svg"
                            title: "No corroborating mentions"
                            description: "In Search → Mentions, use Add to person to preserve a relevant page/document with matched signals and provenance."
                        }
                        ListView {
                            anchors.fill: parent
                            visible: root.mentionRows.length > 0
                            clip: true
                            model: root.mentionRows
                            boundsBehavior: Flickable.StopAtBounds
                            delegate: Rectangle {
                                id: mentionRow
                                required property var modelData
                                width: ListView.view.width
                                height: 78
                                color: mentionMouse.containsMouse ? Theme.surfaceHover : "transparent"
                                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                                Text { x: 16; y: 10; width: parent.width - 170; text: String(mentionRow.modelData.title || "Corroborating mention"); color: Theme.textPrimary; font.pixelSize: 11; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                Text { x: 16; y: 31; width: parent.width - 170; text: String(mentionRow.modelData.summary || "Multi-signal match"); color: Theme.textSecondary; font.pixelSize: 9; elide: Text.ElideRight }
                                Text { x: 16; y: 51; width: parent.width - 170; text: String(mentionRow.modelData.source || "Source") + (mentionRow.modelData.date ? " · " + String(mentionRow.modelData.date) : ""); color: Theme.textMuted; font.pixelSize: 8; elide: Text.ElideRight }
                                Rectangle {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 126
                                    height: 28
                                    radius: 6
                                    color: "transparent"
                                    border.width: 1
                                    border.color: Theme.success
                                    Text { anchors.centerIn: parent; text: "MENTION · " + Number(mentionRow.modelData.score || 0).toFixed(0); color: Theme.success; font.pixelSize: 8; font.weight: Font.DemiBold }
                                }
                                MouseArea {
                                    id: mentionMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: mentionRow.modelData.url ? Qt.PointingHandCursor : Qt.ArrowCursor
                                    enabled: String(mentionRow.modelData.url || "").length > 0
                                    onClicked: desktopBridge.openExternalUrl(String(mentionRow.modelData.url || ""))
                                }
                            }
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        }
                    }
                }

'''
    photos_anchor = '''                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(460, Math.max(250, 100 + root.attachmentRows.length * 104))
'''
    text = replace_once(text, photos_anchor, mentions_panel + photos_anchor, name="Person.qml mentions panel")

    text = text.replace(
        'enabled: root.profileCandidates.length > 0',
        'enabled: root.reviewRows.length > 0',
        1,
    )
    text = text.replace(
        'root.profileCandidates.length === 0',
        'root.reviewRows.length === 0',
        1,
    )
    text = text.replace(
        'String(root.profileCandidates.length) + " candidate(s) available"',
        'String(root.reviewRows.length) + " relevant candidate(s) available"',
        1,
    )
    return text


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install OSINTXZ R13.23.1 Person Card Polish + Mentions Integration"
    )
    parser.add_argument("project_root")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    if not (root / "app").is_dir():
        raise SystemExit(f"Invalid OSINTXZ project root: {root}")

    files = {
        "person": root / "app/interface/desktop/qml/pages/Person.qml",
        "search": root / "app/interface/desktop/qml/pages/Search.qml",
        "desktop": root / "app/interface/desktop/bridges/desktop_bridge.py",
        "investigation": root / "app/interface/desktop/bridges/investigation_search_bridge.py",
    }
    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        raise SystemExit("R13.23/R13.22 baseline files missing: " + ", ".join(missing))

    if "// R13.23 PERSON CARD V2" not in files["person"].read_text(encoding="utf-8", errors="ignore"):
        raise SystemExit("R13.23 Person Card v2 must be installed first.")
    if 'key: "mentions"' not in files["search"].read_text(encoding="utf-8", errors="ignore"):
        raise SystemExit("R13.22 Corroborating Mentions must be installed first.")

    payload = Path(__file__).resolve().parent / "payload"
    service_src = payload / "app/application/person_mention_selection_service.py"
    test_src = payload / "tests/test_r13_23_1_person_card_mentions.py"
    for path in (service_src, test_src):
        if not path.is_file():
            raise SystemExit(f"Patch payload missing: {path}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = root / "storage/patch_backups" / f"r13_23_1_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    for path in files.values():
        relative = path.relative_to(root)
        target = backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    service_dst = root / "app/application/person_mention_selection_service.py"
    if service_dst.exists():
        backup_service = backup / service_dst.relative_to(root)
        backup_service.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(service_dst, backup_service)
    service_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(service_src, service_dst)

    files["person"].write_text(
        patch_person_qml(files["person"].read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    files["search"].write_text(
        patch_search_qml(files["search"].read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    files["desktop"].write_text(
        patch_desktop_bridge(files["desktop"].read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    files["investigation"].write_text(
        patch_investigation_bridge(files["investigation"].read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    test_dst = root / "tests/test_r13_23_1_person_card_mentions.py"
    test_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(test_src, test_dst)

    py = python_for(root)
    subprocess.run(
        [
            str(py), "-m", "py_compile",
            str(service_dst),
            str(files["desktop"]),
            str(files["investigation"]),
        ],
        cwd=root,
        check=True,
    )

    checks = (
        (PERSON_MARKER, files["person"]),
        ("Corroborating Mentions", files["person"]),
        ("root.reviewRows.length", files["person"]),
        (SEARCH_MARKER, files["search"]),
        ("Add to person", files["search"]),
        (DESKTOP_MARKER, files["desktop"]),
        ('"mentions": mention_rows[:40]', files["desktop"]),
        (BRIDGE_MARKER, files["investigation"]),
        ("addMentionToPerson", files["investigation"]),
    )
    absent = [marker for marker, path in checks if marker not in path.read_text(encoding="utf-8", errors="ignore")]
    if absent:
        raise SystemExit("R13.23.1 install verification failed: " + ", ".join(absent))

    print(f"{PATCH} Person Card Polish + Mentions installed.")
    print(f"Backup: {backup}")
    print(f"Person.qml SHA-256: {sha256(files['person'])}")

    if args.run_tests:
        tests = [
            "tests/test_r13_23_1_person_card_mentions.py",
            "tests/test_r13_23_person_card_v2.py",
            "tests/test_r13_22_corroborating_mentions.py",
            "tests/test_qml_desktop_bridge.py",
        ]
        existing = [item for item in tests if (root / item).is_file()]
        cmd = [str(py), "-m", "pytest", "-q", *existing]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, cwd=root, check=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

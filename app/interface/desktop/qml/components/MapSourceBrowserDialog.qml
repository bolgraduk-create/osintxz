pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

AppDialog {
    id: root

    property var sources: []
    property string currentPrimaryId: ""
    property bool satelliteAvailable: false
    property string query: ""
    property string categoryFilter: "all"

    signal sourceChosen(string sourceId, bool asSecondary)
    signal addSourceRequested()
    signal removeSourceRequested(string sourceId)

    width: 720
    title: "Map Source Browser"
    description: "Browse built-in and analyst-added raster map sources."
    primaryText: "Close"
    cancelText: "Close"
    bodyHeight: 560

    function filteredSources() {
        var normalized = root.query.trim().toLowerCase()
        var result = []

        for (var i = 0; i < root.sources.length; ++i) {
            var source = root.sources[i]
            var category = String(source.category || "other").toLowerCase()

            if (root.categoryFilter !== "all"
                    && category !== root.categoryFilter)
                continue

            var metadata = source.metadata || ({})
            var haystack = (
                String(source.name || "")
                + " "
                + String(source.kind || "")
                + " "
                + category
                + " "
                + String(source.attribution || "")
                + " "
                + String(metadata.description || "")
                + " "
                + String(metadata.provider || "")
            ).toLowerCase()

            if (normalized.length > 0
                    && haystack.indexOf(normalized) < 0)
                continue

            result.push(source)
        }

        return result
    }

    function primarySelectable(source) {
        var metadata = (source || {}).metadata || ({})
        return metadata.primarySelectable !== false
    }

    function roleLabel(source) {
        var metadata = (source || {}).metadata || ({})
        var role = String(metadata.role || "base").toUpperCase()
        if (!Boolean((source || {}).enabled))
            return "REFERENCE"
        return role
    }

    function sourceAvailable(source) {
        if (!Boolean((source || {}).enabled))
            return false
        if (String((source || {}).kind || "") === "schematic")
            return true
        if (String((source || {}).id || "") === "sentinel_selected")
            return root.satelliteAvailable
        return true
    }

    onRejected: close()

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 18
        anchors.rightMargin: 18
        anchors.topMargin: 12
        anchors.bottomMargin: 12
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            AppTextField {
                id: sourceSearch
                Layout.fillWidth: true
                placeholderText: "Search maps by name, type, category..."
                text: root.query
                onTextChanged: root.query = text
            }

            AppButton {
                text: "+ Add source"
                onClicked: root.addSourceRequested()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Repeater {
                model: [
                    { key: "all", label: "All" },
                    { key: "streets", label: "Streets" },
                    { key: "topographic", label: "Topo" },
                    { key: "earth", label: "Earth" },
                    { key: "maritime", label: "Maritime" },
                    { key: "infrastructure", label: "Infrastructure" },
                    { key: "satellite", label: "Satellite" },
                    { key: "custom", label: "Custom" }
                ]

                delegate: AppButton {
                    required property var modelData
                    text: String(modelData.label || "")
                    primary: root.categoryFilter === String(modelData.key || "")
                    quiet: !primary
                    onClicked: root.categoryFilter = String(modelData.key || "all")
                }
            }

            Item { Layout.fillWidth: true }
        }

        RowLayout {
            Layout.fillWidth: true

            Text {
                text: String(root.filteredSources().length) + " source(s)"
                color: Theme.textMuted
                font.pixelSize: 9
            }

            Item { Layout.fillWidth: true }

            Text {
                text: "XYZ · WMS · WMTS · Sentinel"
                color: Theme.textMuted
                font.pixelSize: 8
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.divider
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Column {
                width: parent.width
                spacing: 7

                Repeater {
                    model: root.filteredSources()

                    delegate: Rectangle {
                        id: sourceRow
                        required property var modelData

                        width: parent.width
                        height: 104
                        radius: 8
                        color: Theme.surface
                        border.width: String(modelData.id || "") === root.currentPrimaryId ? 1 : 0
                        border.color: Theme.accent

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 10
                            anchors.topMargin: 8
                            anchors.bottomMargin: 8
                            spacing: 10

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 3

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 7

                                    Text {
                                        Layout.fillWidth: true
                                        text: String(sourceRow.modelData.name || "Map source")
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }

                                    Rectangle {
                                        width: typeText.implicitWidth + 14
                                        height: 20
                                        radius: 5
                                        color: Theme.accentSoft

                                        Text {
                                            id: typeText
                                            anchors.centerIn: parent
                                            text: String(sourceRow.modelData.kind || "").toUpperCase()
                                            color: Theme.accent
                                            font.pixelSize: 7
                                            font.weight: Font.DemiBold
                                        }
                                    }

                                    Rectangle {
                                        width: roleText.implicitWidth + 14
                                        height: 20
                                        radius: 5
                                        color: Theme.surfaceHover

                                        Text {
                                            id: roleText
                                            anchors.centerIn: parent
                                            text: root.roleLabel(sourceRow.modelData)
                                            color: Boolean(sourceRow.modelData.enabled)
                                                ? Theme.textSecondary
                                                : Theme.warning
                                            font.pixelSize: 7
                                            font.weight: Font.DemiBold
                                        }
                                    }

                                    Rectangle {
                                        visible: Boolean(sourceRow.modelData.userDefined)
                                        width: customText.implicitWidth + 14
                                        height: 20
                                        radius: 5
                                        color: Theme.surfaceHover

                                        Text {
                                            id: customText
                                            anchors.centerIn: parent
                                            text: "CUSTOM"
                                            color: Theme.textSecondary
                                            font.pixelSize: 7
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: String((sourceRow.modelData.metadata || {}).description || "")
                                    color: Theme.textSecondary
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
                                    visible: text.length > 0
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: String(sourceRow.modelData.category || "map")
                                        + " · "
                                        + String((sourceRow.modelData.metadata || {}).provider
                                            || sourceRow.modelData.attribution
                                            || "source")
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: String((sourceRow.modelData.metadata || {}).policyNote || "")
                                    color: Boolean((sourceRow.modelData.metadata || {}).policyRestricted)
                                        ? Theme.warning
                                        : Theme.textMuted
                                    font.pixelSize: 7
                                    elide: Text.ElideRight
                                    visible: text.length > 0
                                }

                                Text {
                                    Layout.fillWidth: true
                                    visible: String(sourceRow.modelData.id || "") === "sentinel_selected"
                                        && !root.satelliteAvailable
                                    text: "Select a Sentinel-2 scene before using this source."
                                    color: Theme.warning
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
                                }
                            }

                            AppButton {
                                text: String(sourceRow.modelData.id || "") === root.currentPrimaryId
                                    ? "Active"
                                    : "Use"
                                enabled: root.sourceAvailable(sourceRow.modelData)
                                    && root.primarySelectable(sourceRow.modelData)
                                    && String(sourceRow.modelData.id || "") !== root.currentPrimaryId
                                primary: String(sourceRow.modelData.id || "") !== root.currentPrimaryId
                                onClicked: root.sourceChosen(
                                    String(sourceRow.modelData.id || ""),
                                    false
                                )
                            }

                            AppButton {
                                text: "Compare"
                                enabled: root.sourceAvailable(sourceRow.modelData)
                                    && Boolean(sourceRow.modelData.compareSupported)
                                    && String(sourceRow.modelData.id || "") !== root.currentPrimaryId
                                onClicked: root.sourceChosen(
                                    String(sourceRow.modelData.id || ""),
                                    true
                                )
                            }

                            AppButton {
                                text: "Remove"
                                destructive: true
                                visible: Boolean(sourceRow.modelData.userDefined)
                                onClicked: root.removeSourceRequested(
                                    String(sourceRow.modelData.id || "")
                                )
                            }
                        }
                    }
                }

                Text {
                    width: parent.width
                    visible: root.filteredSources().length === 0
                    text: "No map sources match the search."
                    color: Theme.textMuted
                    font.pixelSize: 10
                    horizontalAlignment: Text.AlignHCenter
                    topPadding: 40
                }
            }
        }
    }
}

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

    signal sourceChosen(string sourceId, bool asSecondary)
    signal addSourceRequested()

    width: 720
    title: "Map Source Browser"
    description: "Browse built-in and analyst-added raster map sources."
    primaryText: "Close"
    cancelText: "Close"
    bodyHeight: 500

    function filteredSources() {
        var normalized = root.query.trim().toLowerCase()
        if (normalized.length === 0)
            return root.sources

        var result = []
        for (var i = 0; i < root.sources.length; ++i) {
            var source = root.sources[i]
            var haystack = (
                String(source.name || "")
                + " "
                + String(source.kind || "")
                + " "
                + String(source.category || "")
                + " "
                + String(source.attribution || "")
            ).toLowerCase()
            if (haystack.indexOf(normalized) >= 0)
                result.push(source)
        }
        return result
    }

    function sourceAvailable(source) {
        if (String((source || {}).kind || "") === "schematic")
            return true
        if (String((source || {}).id || "") === "sentinel_selected")
            return root.satelliteAvailable
        return Boolean((source || {}).enabled)
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
                        height: 76
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
                                    text: String(sourceRow.modelData.category || "map")
                                        + (String(sourceRow.modelData.attribution || "").length > 0
                                            ? " · " + String(sourceRow.modelData.attribution || "")
                                            : "")
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
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

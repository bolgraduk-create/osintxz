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

    width: 820
    title: "Map Source Browser"
    description: "Choose a basemap or comparison layer."
    primaryText: "Close"
    cancelText: "Close"
    bodyHeight: 520

    function filteredSources() {
        var normalized = root.query.trim().toLowerCase()
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
                + String(source.region || "")
                + " "
                + String(source.provider || "")
                + " "
                + String((source.tags || []).join(" "))
                + " "
                + String(source.attribution || "")
            ).toLowerCase()
            var categoryMatches = root.categoryFilter === "all"
                || String(source.category || "") === root.categoryFilter
                || (root.categoryFilter === "custom" && Boolean(source.userDefined))
            if (haystack.indexOf(normalized) >= 0 && categoryMatches)
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

            AppComboBox {
                Layout.preferredWidth: 164
                Layout.preferredHeight: 38
                model: [
                    { key: "all", label: "All maps" },
                    { key: "streets", label: "Street" },
                    { key: "satellite", label: "Satellite" },
                    { key: "terrain", label: "Terrain" },
                    { key: "historical", label: "Historical" },
                    { key: "transport", label: "Transport" },
                    { key: "marine", label: "Marine" },
                    { key: "custom", label: "Custom" }
                ]
                textRole: "label"
                onActivated: function(index) {
                    root.categoryFilter = String(model[index].key || "all")
                }
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
                        height: 64
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
                                        width: typeText.implicitWidth + 12
                                        height: 18
                                        radius: 5
                                        color: Theme.accentSoft

                                        Text {
                                            id: typeText
                                            anchors.centerIn: parent
                                            text: String(sourceRow.modelData.category || "map").toUpperCase()
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
                                    text: String(sourceRow.modelData.region || "World")
                                        + (String(sourceRow.modelData.provider || "").length > 0
                                            ? " · " + String(sourceRow.modelData.provider || "")
                                            : "")
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    visible: Boolean(sourceRow.modelData.requiresApiKey)
                                        && !Boolean(sourceRow.modelData.credentialConfigured)
                                    text: "API key required · configure it in .env"
                                    color: Theme.warning
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
                                    && sourceRow.modelData.primarySupported !== false
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

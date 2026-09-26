pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

AppDialog {
    id: root

    property bool locationsVisible: true
    property bool photoGpsVisible: true
    property bool nearbyPoiVisible: true
    property bool nearbyPoiAvailable: false
    property var importedLayers: []

    signal locationsVisibilityRequested(bool visible)
    signal photoGpsVisibilityRequested(bool visible)
    signal nearbyPoiVisibilityRequested(bool visible)
    signal importRequested()
    signal layerVisibilityRequested(string layerId, bool visible)
    signal layerOpacityRequested(string layerId, real opacity)
    signal fitLayerRequested(string layerId)
    signal removeLayerRequested(string layerId)

    width: 700
    title: "Map Layers"
    description: "Control investigation overlays and imported geographic files."
    primaryText: "Done"
    cancelText: "Close"
    bodyHeight: 520

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 18
        anchors.rightMargin: 18
        anchors.topMargin: 12
        anchors.bottomMargin: 12
        spacing: 9

        Text {
            text: "INVESTIGATION"
            color: Theme.textMuted
            font.pixelSize: 8
            font.weight: Font.DemiBold
            font.letterSpacing: 1.0
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 18

            CheckBox {
                text: "Locations"
                checked: root.locationsVisible
                onToggled: root.locationsVisibilityRequested(checked)
            }

            CheckBox {
                text: "Photo GPS"
                checked: root.photoGpsVisible
                onToggled: root.photoGpsVisibilityRequested(checked)
            }

            CheckBox {
                text: "Nearby POI"
                checked: root.nearbyPoiVisible
                enabled: root.nearbyPoiAvailable
                onToggled: root.nearbyPoiVisibilityRequested(checked)
            }

            Item { Layout.fillWidth: true }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.divider
        }

        RowLayout {
            Layout.fillWidth: true

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: "IMPORTED"
                    color: Theme.textMuted
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.0
                }

                Text {
                    text: "GeoJSON · KML · GPX"
                    color: Theme.textMuted
                    font.pixelSize: 8
                }
            }

            AppButton {
                text: "Import layer"
                primary: true
                onClicked: root.importRequested()
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Column {
                width: parent.width
                spacing: 7

                Repeater {
                    model: root.importedLayers

                    delegate: Rectangle {
                        id: layerRow
                        required property var modelData

                        width: parent.width
                        height: 82
                        radius: 8
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.border

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            anchors.topMargin: 7
                            anchors.bottomMargin: 7
                            spacing: 5

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 7

                                CheckBox {
                                    checked: Boolean(layerRow.modelData.visible)
                                    onToggled: root.layerVisibilityRequested(
                                        String(layerRow.modelData.id || ""),
                                        checked
                                    )
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1

                                    Text {
                                        Layout.fillWidth: true
                                        text: String(layerRow.modelData.name || "Imported layer")
                                        color: Theme.textPrimary
                                        font.pixelSize: 10
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: String(layerRow.modelData.sourceFormat || "").toUpperCase()
                                            + " · "
                                            + String(layerRow.modelData.featureCount || 0)
                                            + " feature(s)"
                                        color: Theme.textMuted
                                        font.pixelSize: 8
                                        elide: Text.ElideRight
                                    }
                                }

                                AppButton {
                                    text: "Fit"
                                    enabled: (layerRow.modelData.bounds || []).length === 4
                                    onClicked: root.fitLayerRequested(
                                        String(layerRow.modelData.id || "")
                                    )
                                }

                                AppButton {
                                    text: "Remove"
                                    destructive: true
                                    onClicked: root.removeLayerRequested(
                                        String(layerRow.modelData.id || "")
                                    )
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Text {
                                    text: "Opacity"
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                }

                                Slider {
                                    Layout.fillWidth: true
                                    from: 0.05
                                    to: 1.0
                                    stepSize: 0.05
                                    value: Number(layerRow.modelData.opacity || 0.9)
                                    onMoved: root.layerOpacityRequested(
                                        String(layerRow.modelData.id || ""),
                                        value
                                    )
                                }

                                Text {
                                    text: Math.round(
                                        Number(layerRow.modelData.opacity || 0.9) * 100
                                    ) + "%"
                                    color: Theme.textSecondary
                                    font.pixelSize: 8
                                    Layout.preferredWidth: 34
                                }
                            }
                        }
                    }
                }

                Text {
                    width: parent.width
                    visible: root.importedLayers.length === 0
                    text: "No imported geographic layers yet."
                    color: Theme.textMuted
                    font.pixelSize: 10
                    horizontalAlignment: Text.AlignHCenter
                    topPadding: 34
                }
            }
        }
    }
}

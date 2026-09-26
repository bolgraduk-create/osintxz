pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

Rectangle {
    id: root

    property var sources: []
    property string primarySourceId: "osm_standard"
    property string secondarySourceId: ""
    property bool compareEnabled: false
    property string compareMode: "overlay"
    property real secondaryOpacity: 0.75
    property bool satelliteAvailable: false

    signal primarySourceRequested(string sourceId)
    signal secondarySourceRequested(string sourceId)
    signal compareEnabledRequested(bool enabled)
    signal compareModeRequested(string mode)
    signal secondaryOpacityRequested(real opacity)
    signal browseSourcesRequested()
    signal layersRequested()
    signal addSourceRequested()
    signal removeSourceRequested(string sourceId)

    function sourceForId(sourceId) {
        for (var i = 0; i < root.sources.length; ++i) {
            if (String(root.sources[i].id || "") === String(sourceId || ""))
                return root.sources[i]
        }
        return ({})
    }

    function sourceAvailable(source) {
        if (String((source || {}).id || "") === "sentinel_selected")
            return root.satelliteAvailable
        return Boolean((source || {}).enabled)
    }

    function selectableSources() {
        var result = []
        for (var i = 0; i < root.sources.length; ++i) {
            var source = root.sources[i]
            if (!root.sourceAvailable(source))
                continue
            result.push(source)
        }
        return result
    }

    function compareSources() {
        var result = []
        var rows = root.sources
        for (var i = 0; i < rows.length; ++i) {
            var source = rows[i]
            if (!root.sourceAvailable(source))
                continue
            if (!Boolean(source.compareSupported))
                continue
            if (String(source.kind || "") === "schematic")
                continue
            if (String(source.id || "") === root.primarySourceId)
                continue
            result.push(source)
        }
        return result
    }

    function indexInRows(rows, sourceId) {
        for (var i = 0; i < rows.length; ++i) {
            if (String(rows[i].id || "") === String(sourceId || ""))
                return i
        }
        return rows.length > 0 ? 0 : -1
    }

    implicitHeight: root.compareEnabled ? 104 : 58
    radius: 10
    color: Theme.surface
    border.width: 1
    border.color: Theme.border

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.topMargin: 8
        anchors.bottomMargin: 8
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            spacing: 8

            Text {
                text: "MAP SOURCE"
                color: Theme.textMuted
                font.pixelSize: 8
                font.weight: Font.DemiBold
                font.letterSpacing: 1.0
                Layout.preferredWidth: 76
            }

            AppComboBox {
                id: primaryBox
                Layout.preferredWidth: 250
                Layout.preferredHeight: 34
                model: root.selectableSources()
                textRole: "name"
                currentIndex: root.indexInRows(
                    root.selectableSources(),
                    root.primarySourceId
                )
                onActivated: function(index) {
                    var rows = root.selectableSources()
                    if (index >= 0 && index < rows.length)
                        root.primarySourceRequested(String(rows[index].id || ""))
                }
            }

            Rectangle {
                Layout.preferredWidth: primaryType.implicitWidth + 16
                Layout.preferredHeight: 24
                radius: 6
                color: Theme.accentSoft
                visible: String(root.sourceForId(root.primarySourceId).kind || "").length > 0

                Text {
                    id: primaryType
                    anchors.centerIn: parent
                    text: String(root.sourceForId(root.primarySourceId).kind || "").toUpperCase()
                    color: Theme.accent
                    font.pixelSize: 7
                    font.weight: Font.DemiBold
                }
            }

            Item { Layout.fillWidth: true }

            AppButton {
                Layout.preferredHeight: 34
                text: "Browse"
                quiet: true
                onClicked: root.browseSourcesRequested()
            }

            AppButton {
                Layout.preferredHeight: 34
                text: "Layers"
                quiet: true
                onClicked: root.layersRequested()
            }

            AppButton {
                Layout.preferredHeight: 34
                text: root.compareEnabled ? "Compare on" : "Compare"
                primary: root.compareEnabled
                onClicked: root.compareEnabledRequested(!root.compareEnabled)
            }

            AppButton {
                Layout.preferredHeight: 34
                text: "+ Source"
                quiet: true
                onClicked: root.addSourceRequested()
            }

            AppButton {
                Layout.preferredHeight: 34
                text: "Remove"
                destructive: true
                visible: Boolean(root.sourceForId(root.primarySourceId).userDefined)
                onClicked: root.removeSourceRequested(root.primarySourceId)
            }
        }

        Rectangle {
            visible: root.compareEnabled
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 1 : 0
            color: Theme.divider
        }

        RowLayout {
            visible: root.compareEnabled
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 36 : 0
            spacing: 8

            Text {
                text: "SECONDARY"
                color: Theme.textMuted
                font.pixelSize: 8
                font.weight: Font.DemiBold
                font.letterSpacing: 1.0
                Layout.preferredWidth: 76
            }

            AppComboBox {
                id: secondaryBox
                Layout.preferredWidth: 250
                Layout.preferredHeight: 34
                model: root.compareSources()
                textRole: "name"
                currentIndex: root.indexInRows(
                    root.compareSources(),
                    root.secondarySourceId
                )
                onActivated: function(index) {
                    var rows = root.compareSources()
                    if (index >= 0 && index < rows.length)
                        root.secondarySourceRequested(String(rows[index].id || ""))
                }
            }

            AppComboBox {
                id: compareModeBox
                Layout.preferredWidth: 150
                Layout.preferredHeight: 34
                model: [
                    { key: "overlay", label: "Overlay" },
                    { key: "side_by_side", label: "Side by side" },
                    { key: "swipe", label: "Swipe" }
                ]
                textRole: "label"
                currentIndex: root.compareMode === "side_by_side"
                    ? 1
                    : (root.compareMode === "swipe" ? 2 : 0)
                onActivated: function(index) {
                    if (index >= 0 && index < model.length)
                        root.compareModeRequested(String(model[index].key || "overlay"))
                }
            }

            Text {
                text: "Opacity"
                color: Theme.textMuted
                font.pixelSize: 8
            }

            Slider {
                Layout.preferredWidth: 130
                from: 0.1
                to: 1.0
                stepSize: 0.05
                value: root.secondaryOpacity
                onMoved: root.secondaryOpacityRequested(value)
            }

            Text {
                text: Math.round(root.secondaryOpacity * 100) + "%"
                color: Theme.textSecondary
                font.pixelSize: 9
                Layout.preferredWidth: 34
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root.compareMode === "swipe"
                    ? "Drag divider on the map"
                    : "Pan and zoom stay synchronized"
                color: Theme.textMuted
                font.pixelSize: 8
            }
        }
    }
}

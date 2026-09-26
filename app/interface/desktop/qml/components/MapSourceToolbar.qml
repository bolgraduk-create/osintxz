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
    property bool toolsOpen: false

    signal primarySourceRequested(string sourceId)
    signal secondarySourceRequested(string sourceId)
    signal compareEnabledRequested(bool enabled)
    signal compareModeRequested(string mode)
    signal secondaryOpacityRequested(real opacity)
    signal browseSourcesRequested()
    signal layersRequested()
    signal toolsRequested()
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
            if (source.primarySupported === false)
                continue
            result.push(source)
        }
        return result
    }

    function compareSources() {
        var result = []
        for (var i = 0; i < root.sources.length; ++i) {
            var source = root.sources[i]
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

    implicitHeight: root.compareEnabled ? 94 : 52
    radius: 9
    color: Theme.surface
    border.width: 1
    border.color: Theme.border

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            spacing: 7

            AppComboBox {
                id: primaryBox
                Layout.preferredWidth: 330
                Layout.maximumWidth: 420
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

            Item { Layout.fillWidth: true }

            AppButton {
                Layout.preferredHeight: 34
                implicitWidth: 76
                text: "Browse"
                quiet: true
                onClicked: root.browseSourcesRequested()
            }

            AppButton {
                Layout.preferredHeight: 34
                implicitWidth: 72
                text: "Layers"
                quiet: true
                onClicked: root.layersRequested()
            }

            AppButton {
                Layout.preferredHeight: 34
                implicitWidth: 70
                text: "Tools"
                quiet: !root.toolsOpen
                primary: root.toolsOpen
                onClicked: root.toolsRequested()
            }

            AppButton {
                Layout.preferredHeight: 34
                implicitWidth: root.compareEnabled ? 104 : 84
                text: root.compareEnabled ? "Exit compare" : "Compare"
                primary: root.compareEnabled
                onClicked: root.compareEnabledRequested(!root.compareEnabled)
            }
        }

        RowLayout {
            visible: root.compareEnabled
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 32 : 0
            spacing: 7

            Text {
                text: "Compare with"
                color: Theme.textMuted
                font.pixelSize: 8
                Layout.preferredWidth: 76
            }

            AppComboBox {
                id: secondaryBox
                Layout.preferredWidth: 280
                Layout.preferredHeight: 32
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
                Layout.preferredWidth: 132
                Layout.preferredHeight: 32
                model: [
                    { key: "overlay", label: "Overlay" },
                    { key: "side_by_side", label: "Split" },
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
                visible: root.compareMode === "overlay"
                text: "Opacity"
                color: Theme.textMuted
                font.pixelSize: 8
            }

            Slider {
                visible: root.compareMode === "overlay"
                Layout.preferredWidth: 120
                from: 0.1
                to: 1.0
                stepSize: 0.05
                value: root.secondaryOpacity
                onMoved: root.secondaryOpacityRequested(value)
            }

            Text {
                visible: root.compareMode === "overlay"
                text: Math.round(root.secondaryOpacity * 100) + "%"
                color: Theme.textSecondary
                font.pixelSize: 8
                Layout.preferredWidth: 34
            }

            Item { Layout.fillWidth: true }
        }
    }
}

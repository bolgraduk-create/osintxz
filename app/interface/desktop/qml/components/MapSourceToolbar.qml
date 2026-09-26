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

    signal primarySourceRequested(string sourceId)
    signal secondarySourceRequested(string sourceId)
    signal compareEnabledRequested(bool enabled)
    signal compareModeRequested(string mode)
    signal secondaryOpacityRequested(real opacity)
    signal addSourceRequested()
    signal removeSourceRequested(string sourceId)

    function sourceIndex(sourceId) {
        for (var i = 0; i < root.sources.length; ++i) {
            if (String(root.sources[i].id || "") === String(sourceId || ""))
                return i
        }
        return -1
    }

    function sourceForId(sourceId) {
        var index = root.sourceIndex(sourceId)
        if (index >= 0)
            return root.sources[index]
        return ({})
    }

    function selectableSources() {
        return root.sources
    }

    function compareSources() {
        var result = []
        var rows = root.sources
        for (var i = 0; i < rows.length; ++i) {
            if (!Boolean(rows[i].compareSupported))
                continue
            if (String(rows[i].kind || "") === "schematic")
                continue
            result.push(rows[i])
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

    implicitHeight: root.compareEnabled ? 82 : 44
    radius: 8
    color: Theme.surface
    border.width: 1
    border.color: Theme.border

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        anchors.topMargin: 5
        anchors.bottomMargin: 5
        spacing: 5

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            spacing: 7

            Text {
                text: "MAP SOURCE"
                color: Theme.textMuted
                font.pixelSize: 8
                font.weight: Font.DemiBold
                font.letterSpacing: 1.0
            }

            AppComboBox {
                id: primaryBox
                Layout.preferredWidth: 210
                Layout.preferredHeight: 32
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

            CheckBox {
                id: compareCheck
                text: "Compare"
                checked: root.compareEnabled
                onToggled: root.compareEnabledRequested(checked)
            }

            Item { Layout.fillWidth: true }

            AppButton {
                Layout.preferredHeight: 30
                implicitHeight: 30
                text: "+ Source"
                onClicked: root.addSourceRequested()
            }

            AppButton {
                Layout.preferredHeight: 30
                implicitHeight: 30
                text: "Remove"
                destructive: true
                enabled: Boolean(
                    root.sourceForId(root.primarySourceId).userDefined
                )
                onClicked: root.removeSourceRequested(root.primarySourceId)
            }
        }

        RowLayout {
            visible: root.compareEnabled
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 32 : 0
            spacing: 7

            Text {
                text: "SECONDARY"
                color: Theme.textMuted
                font.pixelSize: 8
                font.weight: Font.DemiBold
                font.letterSpacing: 1.0
            }

            AppComboBox {
                id: secondaryBox
                Layout.preferredWidth: 210
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
                Layout.preferredWidth: 138
                Layout.preferredHeight: 32
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
                id: opacitySlider
                Layout.preferredWidth: 120
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
                    ? "Drag divider on map"
                    : "Synchronized pan / zoom"
                color: Theme.textMuted
                font.pixelSize: 8
            }
        }
    }
}

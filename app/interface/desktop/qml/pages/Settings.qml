pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root
    property var prefs: desktopBridge.uiSettings || ({})

    function reload() { root.prefs = desktopBridge.uiSettings || ({}) }

    Connections {
        target: desktopBridge
        function onChanged() { root.reload() }
    }
    Component.onCompleted: root.reload()

    component ToggleRow: Rectangle {
        id: toggleRoot
        property string label: "Setting"
        property string description: ""
        property bool checked: false
        signal changed(bool checked)
        width: parent ? parent.width : 400
        height: 70
        color: "transparent"
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
        Text { x: 16; y: 13; width: parent.width - 100; text: toggleRoot.label; color: Theme.textPrimary; font.pixelSize: 12; font.weight: Font.Medium; elide: Text.ElideRight }
        Text { x: 16; y: 37; width: parent.width - 100; text: toggleRoot.description; color: Theme.textMuted; font.pixelSize: 9; elide: Text.ElideRight }
        Rectangle {
            anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
            width: 42; height: 24; radius: 12
            color: toggleRoot.checked ? Theme.accent : "#1a2b39"
            border.width: 1; border.color: toggleRoot.checked ? Theme.accent : Theme.borderHover
            Rectangle {
                width: 18; height: 18; radius: 9
                y: 3
                x: toggleRoot.checked ? parent.width - width - 3 : 3
                color: "white"
                Behavior on x { NumberAnimation { duration: 120 } }
            }
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: toggleRoot.changed(!toggleRoot.checked)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Spacing.page
        anchors.rightMargin: Spacing.page
        anchors.topMargin: 16
        anchors.bottomMargin: 24
        spacing: Spacing.panelGap

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 78
            Text { x: 2; y: 0; text: "APPLICATION"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.Medium; font.letterSpacing: 1.7 }
            Text { x: 2; y: 19; text: "Settings"; color: Theme.textPrimary; font.pixelSize: Typography.pageTitle; font.weight: Font.DemiBold }
            Text { x: 3; y: 55; text: "Configure local desktop presentation and graph behaviour."; color: Theme.textSecondary; font.pixelSize: 12 }
            AppButton {
                anchors.right: parent.right
                anchors.top: parent.top
                width: 126; height: 36
                text: "Reset defaults"
                onClicked: desktopBridge.resetUiSettings()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Spacing.panelGap

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: Spacing.panelGap

                Panel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 330
                    title: "Appearance"
                    subtitle: "Local presentation preferences"
                    iconSource: "../../assets/icons/settings.svg"

                    Column {
                        anchors.fill: parent

                        ToggleRow {
                            label: "World map background"
                            description: "Show the global network map behind application pages"
                            checked: Boolean(root.prefs.showWorldMap)
                            onChanged: function(value) { desktopBridge.setUiSetting("showWorldMap", value) }
                        }
                        ToggleRow {
                            label: "Home slogan"
                            description: "Show the OSINTXZ statement on the Overview page"
                            checked: Boolean(root.prefs.showSlogan)
                            onChanged: function(value) { desktopBridge.setUiSetting("showSlogan", value) }
                        }


                    }
                }

                Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    title: "System"
                    subtitle: "Current local runtime"
                    iconSource: "../../assets/icons/settings.svg"

                    Column {
                        anchors.fill: parent
                        Repeater {
                            model: [
                                {label: "DATABASE", value: desktopBridge.databaseAvailable ? "Online" : "Unavailable"},
                                {label: "WORKSPACE", value: desktopBridge.currentCaseTitle || "No investigation selected"},
                                {label: "INTERFACE LANGUAGE", value: "English"},
                                {label: "PREFERENCE STORAGE", value: "Local desktop profile"}
                            ]
                            delegate: Rectangle {
                                id: systemRow
                                required property var modelData
                                width: parent.width
                                height: 62
                                color: "transparent"
                                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                                Text { x: 16; y: 12; text: String(systemRow.modelData.label); color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                                Text { x: 16; y: 33; width: parent.width - 32; text: String(systemRow.modelData.value); color: Theme.textPrimary; font.pixelSize: 11; elide: Text.ElideRight }
                            }
                        }
                    }
                }
            }

            Panel {
                Layout.preferredWidth: 430
                Layout.maximumWidth: 470
                Layout.fillHeight: true
                title: "Graph"
                subtitle: "Bounded relationship explorer defaults"
                iconSource: "../../assets/icons/graph_blue.svg"

                Column {
                    anchors.fill: parent

                    Rectangle {
                        width: parent.width; height: 86; color: "transparent"
                        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                        Text { x: 16; y: 12; text: "DEFAULT DEPTH"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                        AppComboBox {
                            x: 16; y: 35; width: parent.width - 32; height: 34
                            model: ["1 hop", "2 hops"]
                            currentIndex: Number(root.prefs.graphDepth || 1) >= 2 ? 1 : 0
                            onActivated: function(index) { desktopBridge.setUiSetting("graphDepth", index + 1) }
                        }
                    }

                    Rectangle {
                        width: parent.width; height: 86; color: "transparent"
                        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.divider }
                        Text { x: 16; y: 12; text: "VISIBLE NODE LIMIT"; color: Theme.textMuted; font.pixelSize: 8; font.letterSpacing: 1.0 }
                        AppComboBox {
                            x: 16; y: 35; width: parent.width - 32; height: 34
                            model: ["24 nodes", "36 nodes", "60 nodes", "80 nodes"]
                            currentIndex: {
                                var n = Number(root.prefs.graphNodeLimit || 36)
                                if (n <= 24) return 0
                                if (n <= 36) return 1
                                if (n <= 60) return 2
                                return 3
                            }
                            onActivated: function(index) {
                                var values = [24, 36, 60, 80]
                                desktopBridge.setUiSetting("graphNodeLimit", values[index])
                            }
                        }
                    }

                    ToggleRow {
                        label: "Relationship labels"
                        description: "Display relationship type badges on graph edges"
                        checked: Boolean(root.prefs.graphEdgeLabels)
                        onChanged: function(value) { desktopBridge.setUiSetting("graphEdgeLabels", value) }
                    }

                    Rectangle {
                        width: parent.width
                        height: 112
                        color: "transparent"
                        Text {
                            anchors.fill: parent
                            anchors.margins: 16
                            text: "Graph limits affect only the desktop visualization. Persisted entities and relationships are never deleted or truncated. Use a smaller node limit for a cleaner first view, then refocus on any entity."
                            color: Theme.textSecondary
                            font.pixelSize: 10
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }
    }
}

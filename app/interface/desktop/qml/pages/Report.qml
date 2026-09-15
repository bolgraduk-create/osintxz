pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root
    property var report: desktopBridge.currentReport || ({})

    Connections {
        target: desktopBridge
        function onChanged() { root.report = desktopBridge.currentReport || ({}) }
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
            Layout.preferredHeight: 88

            AppButton {
                anchors.left: parent.left
                anchors.top: parent.top
                width: 132
                height: 34
                text: "←  Reports"
                onClicked: desktopBridge.closeReport()
            }

            Text {
                x: 150; y: 0
                text: "REPORT READER"
                color: Theme.textMuted
                font.pixelSize: 9
                font.weight: Font.Medium
                font.letterSpacing: 1.7
            }
            Text {
                x: 150; y: 19
                width: Math.max(200, parent.width - 330)
                text: String(root.report.title || "Untitled report")
                color: Theme.textPrimary
                font.pixelSize: 28
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Text {
                x: 151; y: 58
                width: Math.max(200, parent.width - 330)
                text: String(root.report.type || "Report")
                    + (root.report.caseTitle ? " · " + String(root.report.caseTitle) : "")
                    + (root.report.updatedAt ? " · " + String(root.report.updatedAt) : "")
                color: Theme.textSecondary
                font.pixelSize: 11
                elide: Text.ElideRight
            }

            AppButton {
                anchors.right: parent.right
                anchors.top: parent.top
                width: 112
                height: 36
                text: "Copy report"
                enabled: String(root.report.content || "").length > 0
                onClicked: desktopBridge.copyCurrentReport()
            }
        }

        Panel {
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: "Report Content"
            subtitle: root.report.description || "Persisted investigation report"
            iconSource: "../../assets/icons/document_blue.svg"

            Rectangle {
                anchors.fill: parent
                anchors.margins: 14
                radius: 8
                color: "#091a28"
                border.width: 1
                border.color: Theme.border
                clip: true

                Flickable {
                    id: contentScroll
                    anchors.fill: parent
                    anchors.margins: 18
                    clip: true
                    contentWidth: width
                    contentHeight: reportText.implicitHeight
                    boundsBehavior: Flickable.StopAtBounds

                    TextEdit {
                        id: reportText
                        width: contentScroll.width
                        text: String(root.report.content || "This report has no content.")
                        textFormat: Text.MarkdownText
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        color: Theme.textPrimary
                        selectionColor: Theme.accent
                        selectedTextColor: "white"
                        font.pixelSize: 13
                        lineHeight: 1.35
                    }
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }
            }
        }
    }
}

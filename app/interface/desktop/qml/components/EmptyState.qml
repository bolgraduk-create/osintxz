import QtQuick
import "../theme"

Item {
    id: root
    objectName: "emptyState"

    property url iconSource
    property string title: "No records available"
    property string description: "Records will appear here when they are available."

    implicitHeight: 150

    Column {
        anchors.centerIn: parent
        width: Math.min(410, Math.max(240, root.width - 48))
        spacing: 9

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 44
            height: 44
            radius: 10
            color: Theme.surfaceRaised
            border.color: Theme.border
            border.width: 1

            Image {
                anchors.centerIn: parent
                width: 23
                height: 23
                source: root.iconSource
                opacity: 0.78
                fillMode: Image.PreserveAspectFit
            }
        }

        Text {
            objectName: "emptyStateTitle"
            width: parent.width
            text: root.title
            color: Theme.textPrimary
            font.pixelSize: 14
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Text {
            objectName: "emptyStateDescription"
            width: parent.width
            text: root.description
            color: Theme.textMuted
            font.pixelSize: 11
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            lineHeight: 1.25
        }
    }
}

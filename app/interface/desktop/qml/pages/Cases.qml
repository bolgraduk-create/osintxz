import QtQuick
import QtQuick.Controls
import "../components"
import "../theme"

DataWorkspace {
    id: root
    pageKey: "cases"
    eyebrow: "CASE MANAGEMENT"
    title: "Cases"
    subtitle: desktopBridge.currentCaseTitle ? "Current investigation: " + desktopBridge.currentCaseTitle : "Organize and open stored investigations."
    iconSource: "../../assets/icons/folder_blue.svg"
    primaryAction: "New Case"
    searchPlaceholder: "Search cases..."
    sectionTitle: "Active Investigations"
    contextTitle: "Case Context"
    emptyTitle: "No investigations yet"
    emptyDescription: "Create an investigation to begin organizing entities, evidence, and analysis."
    onPrimaryActionRequested: createDialog.open()
    onRecordActivated: function(recordId) { desktopBridge.activateRecord("cases", recordId) }
    onRecordOptionsRequested: function(recordId, recordTitle) {
        selectedCaseId = recordId
        selectedCaseTitle = recordTitle
        optionsMenu.open()
    }
    property string selectedCaseId: ""
    property string selectedCaseTitle: ""

    Menu {
        id: optionsMenu
        width: 176
        padding: 6
        background: Rectangle {
            color: Theme.surfaceRaised
            radius: 8
            border.color: Theme.borderHover
            border.width: 1
        }
        MenuItem {
            id: renameMenuItem
            text: "Rename"
            height: 38
            contentItem: Text {
                text: renameMenuItem.text
                color: Theme.textPrimary
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
                leftPadding: 9
            }
            background: Rectangle {
                radius: 6
                color: renameMenuItem.down ? "#183044" : (renameMenuItem.highlighted ? Theme.surfaceHover : "transparent")
            }
            onTriggered: {
                renameInput.text = root.selectedCaseTitle
                renameDialog.open()
            }
        }
        MenuItem {
            id: deleteMenuItem
            text: "Delete"
            height: 38
            contentItem: Text {
                text: deleteMenuItem.text
                color: Theme.danger
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
                leftPadding: 9
            }
            background: Rectangle {
                radius: 6
                color: deleteMenuItem.down ? "#3d222a" : (deleteMenuItem.highlighted ? "#2d2028" : "transparent")
            }
            onTriggered: deleteDialog.open()
        }
    }

    AppDialog {
        id: renameDialog
        objectName: "renameInvestigationDialog"
        width: 420
        title: "Rename investigation"
        description: "Update the title shown across the workspace."
        primaryText: "Rename"
        bodyHeight: 92
        onAccepted: desktopBridge.renameCase(root.selectedCaseId, renameInput.text)

        Column {
            anchors.fill: parent
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            anchors.topMargin: 16
            spacing: 6
            Text { text: "TITLE"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.Medium; font.letterSpacing: 1.2 }
            AppTextField {
                id: renameInput
                objectName: "renameInvestigationInput"
                width: parent.width
                placeholderText: "Investigation title"
                Keys.onReturnPressed: renameDialog.accept()
            }
        }
        onOpened: renameInput.forceActiveFocus()
    }

    AppDialog {
        id: deleteDialog
        objectName: "deleteInvestigationDialog"
        width: 440
        title: "Delete investigation?"
        description: "This action uses the existing soft-delete workflow."
        primaryText: "Delete"
        destructive: true
        bodyHeight: 106
        onAccepted: desktopBridge.deleteCase(root.selectedCaseId)

        Text {
            anchors.fill: parent
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            anchors.topMargin: 18
            anchors.bottomMargin: 18
            wrapMode: Text.Wrap
            color: Theme.textSecondary
            font.pixelSize: 12
            lineHeight: 1.25
            text: "This will soft-delete “" + root.selectedCaseTitle + "” using the existing case controller."
        }
    }

    AppDialog {
        id: createDialog
        objectName: "createInvestigationDialog"
        width: 460
        title: "Create investigation"
        description: "Create a new workspace for entities, evidence, and analysis."
        primaryText: "Create"
        bodyHeight: 226
        onAccepted: {
            if (desktopBridge.createCase(titleInput.text, descriptionInput.text)) {
                titleInput.clear()
                descriptionInput.clear()
            } else {
                open()
                titleInput.forceActiveFocus()
            }
        }

        Column {
            anchors.fill: parent
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            anchors.topMargin: 16
            anchors.bottomMargin: 14
            spacing: 6
            Text { text: "TITLE"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.Medium; font.letterSpacing: 1.2 }
            AppTextField { id: titleInput; objectName: "createInvestigationTitleInput"; width: parent.width; placeholderText: "Investigation title" }
            Item { width: 1; height: 3 }
            Text { text: "DESCRIPTION"; color: Theme.textMuted; font.pixelSize: 9; font.weight: Font.Medium; font.letterSpacing: 1.2 }
            AppTextArea { id: descriptionInput; objectName: "createInvestigationDescriptionInput"; width: parent.width; height: 78; placeholderText: "Description (optional)" }
            Text {
                visible: desktopBridge.message.length > 0
                text: desktopBridge.message
                color: Theme.danger
                font.pixelSize: 10
                wrapMode: Text.Wrap
                width: parent.width
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }
        onOpened: titleInput.forceActiveFocus()
    }
}

import QtQuick
import QtQuick.Controls
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
        MenuItem {
            text: "Rename"
            onTriggered: {
                renameInput.text = root.selectedCaseTitle
                renameDialog.open()
            }
        }
        MenuItem { text: "Delete"; onTriggered: deleteDialog.open() }
    }

    Dialog {
        id: renameDialog
        anchors.centerIn: parent
        width: 420
        modal: true
        title: "Rename investigation"
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: desktopBridge.renameCase(root.selectedCaseId, renameInput.text)
        background: Rectangle { color: Theme.surface; radius: 10; border.color: Theme.borderHover }
        contentItem: TextField { id: renameInput; placeholderText: "Investigation title" }
        onOpened: renameInput.forceActiveFocus()
    }

    Dialog {
        id: deleteDialog
        anchors.centerIn: parent
        width: 440
        modal: true
        title: "Delete investigation?"
        standardButtons: Dialog.Yes | Dialog.Cancel
        onAccepted: desktopBridge.deleteCase(root.selectedCaseId)
        background: Rectangle { color: Theme.surface; radius: 10; border.color: Theme.borderHover }
        contentItem: Text {
            width: parent.width
            wrapMode: Text.Wrap
            color: Theme.textSecondary
            text: "This will soft-delete “" + root.selectedCaseTitle + "” using the existing case controller."
        }
    }

    Dialog {
        id: createDialog
        anchors.centerIn: parent
        width: 460
        modal: true
        title: "Create investigation"
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: {
            if (desktopBridge.createCase(titleInput.text, descriptionInput.text)) {
                titleInput.clear()
                descriptionInput.clear()
            } else {
                open()
                titleInput.forceActiveFocus()
            }
        }
        background: Rectangle { color: Theme.surface; radius: 10; border.color: Theme.borderHover }
        contentItem: Column {
            spacing: 12
            TextField { id: titleInput; width: parent.width; placeholderText: "Investigation title" }
            TextArea { id: descriptionInput; width: parent.width; height: 100; placeholderText: "Description (optional)"; wrapMode: TextEdit.Wrap }
            Text { visible: desktopBridge.message.length > 0; text: desktopBridge.message; color: Theme.danger; font.pixelSize: 11; wrapMode: Text.Wrap; width: parent.width }
        }
        onOpened: titleInput.forceActiveFocus()
    }
}

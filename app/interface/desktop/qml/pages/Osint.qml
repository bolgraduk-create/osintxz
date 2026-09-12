import QtQuick
import QtQuick.Controls
import "../theme"

DataWorkspace {
    id: root
    pageKey: "osint"
    eyebrow: "SOURCE OPERATIONS"
    title: "OSINT"
    subtitle: "Inspect connectors registered by the existing OSINT pipeline."
    iconSource: "../../assets/icons/globe_blue.svg"
    primaryAction: "Run Collection"
    searchPlaceholder: "Filter registered connectors..."
    sectionTitle: "Registered Connectors"
    contextTitle: "Operational Context"
    onPrimaryActionRequested: collectionDialog.open()

    Dialog {
        id: collectionDialog
        anchors.centerIn: parent
        width: 470
        modal: true
        title: "Run OSINT collection"
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: {
            if (!desktopBridge.runOsint(typeBox.currentText, targetInput.text)) {
                open()
                targetInput.forceActiveFocus()
            } else {
                targetInput.clear()
            }
        }
        background: Rectangle { color: Theme.surface; radius: 10; border.color: Theme.borderHover }
        contentItem: Column {
            spacing: 12
            ComboBox {
                id: typeBox
                width: parent.width
                model: ["Email", "Username", "Domain", "IP", "URL", "Phone"]
            }
            TextField {
                id: targetInput
                width: parent.width
                placeholderText: "Collection target"
            }
            Text {
                width: parent.width
                wrapMode: Text.Wrap
                color: Theme.textMuted
                font.pixelSize: 11
                text: "Uses the existing OSINT controller and registered connector pipeline. Collection may take up to 30 seconds."
            }
            Text {
                visible: desktopBridge.message.length > 0
                width: parent.width
                wrapMode: Text.Wrap
                color: Theme.textSecondary
                font.pixelSize: 11
                text: desktopBridge.message
            }
        }
        onOpened: targetInput.forceActiveFocus()
    }
}

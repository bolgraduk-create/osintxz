import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

DataWorkspace {
    id: root

    pageKey: "entities"
    eyebrow: "PERSON INTELLIGENCE"
    title: "People"
    subtitle: desktopBridge.currentCaseTitle
        ? "People being investigated in " + desktopBridge.currentCaseTitle + "."
        : "Select an investigation to view or add people."
    iconSource: "../../assets/icons/users_cyan.svg"
    primaryAction: "Add Person"
    searchPlaceholder: "Filter people by name..."
    sectionTitle: "People"
    contextTitle: "Person Scope"
    selectedCategory: "all"
    categoryItems: []
    emptyTitle: desktopBridge.hasCurrentCase
        ? "No people in this investigation"
        : "No investigation selected"
    emptyDescription: desktopBridge.hasCurrentCase
        ? "Create a person here or from Investigation Search, then assign searches to that person."
        : "Open an investigation before creating a person."

    onPrimaryActionRequested: {
        personName.text = ""
        personDescription.text = ""
        personCreateError.text = ""
        createPersonDialog.open()
        personName.forceActiveFocus()
    }

    onRecordActivated: function(recordId) {
        desktopBridge.activateRecord("entities", recordId)
    }

    Dialog {
        id: createPersonDialog
        modal: true
        anchors.centerIn: parent
        width: Math.min(520, root.width - 80)
        height: 320
        padding: 0
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            radius: 12
            color: Theme.surface
            border.width: 1
            border.color: Theme.border
        }

        contentItem: ColumnLayout {
            spacing: 0

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                color: "transparent"

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: Theme.divider
                }

                Text {
                    x: 20
                    y: 13
                    text: "Add person"
                    color: Theme.textPrimary
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }

                Text {
                    x: 20
                    y: 41
                    width: parent.width - 40
                    text: "Creates a PERSON investigation subject. Technical identifiers will be attached through searches and evidence."
                    color: Theme.textMuted
                    font.pixelSize: 9
                    elide: Text.ElideRight
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: 20
                spacing: 10

                Text {
                    text: "NAME"
                    color: Theme.textMuted
                    font.pixelSize: 8
                    font.letterSpacing: 1.0
                }

                AppTextField {
                    id: personName
                    Layout.fillWidth: true
                    placeholderText: "Full name / investigation label"
                }

                Text {
                    text: "DESCRIPTION"
                    color: Theme.textMuted
                    font.pixelSize: 8
                    font.letterSpacing: 1.0
                }

                AppTextField {
                    id: personDescription
                    Layout.fillWidth: true
                    placeholderText: "Optional note"
                }

                Text {
                    id: personCreateError
                    Layout.fillWidth: true
                    color: Theme.danger
                    font.pixelSize: 9
                    wrapMode: Text.Wrap
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Item { Layout.fillWidth: true }

                    AppButton {
                        text: "Cancel"
                        Layout.preferredWidth: 96
                        onClicked: createPersonDialog.close()
                    }

                    AppButton {
                        text: "Create"
                        primary: true
                        Layout.preferredWidth: 110
                        enabled: personName.text.trim().length > 0
                        onClicked: {
                            personCreateError.text = ""
                            var result = desktopBridge.createPerson(
                                personName.text,
                                personDescription.text
                            )
                            if (result && result.ok) {
                                createPersonDialog.close()
                            } else {
                                personCreateError.text = result && result.error
                                    ? String(result.error)
                                    : "Unable to create person."
                            }
                        }
                    }
                }
            }
        }
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

AppDialog {
    id: root

    width: 620
    title: "Add Map Source"
    description: "Add an analyst-controlled XYZ or WMS source. Credentials in URLs are blocked."
    primaryText: "Add source"
    bodyHeight: sourceType.currentIndex === 1 ? 430 : 338
    primaryEnabled: sourceName.text.trim().length > 0
        && sourceUrl.text.trim().length > 0
        && (sourceType.currentIndex === 0
            || wmsLayers.text.trim().length > 0)

    signal sourceSubmitted(var payload)

    function reset() {
        sourceName.text = ""
        sourceType.currentIndex = 0
        sourceUrl.text = ""
        attribution.text = ""
        termsUrl.text = ""
        minZoom.text = "0"
        maxZoom.text = "19"
        wmsLayers.text = ""
        wmsStyles.text = ""
        wmsVersion.currentIndex = 0
    }

    onAccepted: {
        root.sourceSubmitted({
            name: sourceName.text.trim(),
            kind: sourceType.currentIndex === 1 ? "wms" : "xyz",
            url: sourceUrl.text.trim(),
            attribution: attribution.text.trim(),
            termsUrl: termsUrl.text.trim(),
            minZoom: Number(minZoom.text),
            maxZoom: Number(maxZoom.text),
            wmsLayers: wmsLayers.text.trim(),
            wmsStyles: wmsStyles.text.trim(),
            wmsFormat: "image/png",
            wmsVersion: wmsVersion.currentText,
            wmsTransparent: true
        })
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        anchors.topMargin: 12
        anchors.bottomMargin: 12
        spacing: 9

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            AppTextField {
                id: sourceName
                Layout.fillWidth: true
                placeholderText: "Source name"
            }

            AppComboBox {
                id: sourceType
                Layout.preferredWidth: 120
                model: ["XYZ", "WMS"]
            }
        }

        AppTextField {
            id: sourceUrl
            Layout.fillWidth: true
            placeholderText: sourceType.currentIndex === 1
                ? "https://example.org/wms"
                : "https://example.org/{z}/{x}/{y}.png"
        }

        AppTextField {
            id: attribution
            Layout.fillWidth: true
            placeholderText: "Attribution shown on map"
        }

        AppTextField {
            id: termsUrl
            Layout.fillWidth: true
            placeholderText: "Terms / licence URL (optional)"
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            AppTextField {
                id: minZoom
                Layout.fillWidth: true
                placeholderText: "Min zoom"
                text: "0"
                inputMethodHints: Qt.ImhDigitsOnly
            }

            AppTextField {
                id: maxZoom
                Layout.fillWidth: true
                placeholderText: "Max zoom"
                text: "19"
                inputMethodHints: Qt.ImhDigitsOnly
            }
        }

        Rectangle {
            visible: sourceType.currentIndex === 1
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 1 : 0
            color: Theme.divider
        }

        AppTextField {
            id: wmsLayers
            visible: sourceType.currentIndex === 1
            Layout.fillWidth: true
            placeholderText: "WMS layer(s), comma separated"
        }

        AppTextField {
            id: wmsStyles
            visible: sourceType.currentIndex === 1
            Layout.fillWidth: true
            placeholderText: "WMS style(s), optional"
        }

        AppComboBox {
            id: wmsVersion
            visible: sourceType.currentIndex === 1
            Layout.preferredWidth: 160
            model: ["1.3.0", "1.1.1"]
        }

        Text {
            Layout.fillWidth: true
            text: sourceType.currentIndex === 1
                ? "WMS is requested as 256×256 EPSG:3857 GetMap tiles."
                : "XYZ must contain {z}, {x}, and {y}. Only the visible viewport is requested."
            color: Theme.textMuted
            font.pixelSize: 9
            wrapMode: Text.Wrap
        }
    }
}

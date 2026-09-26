pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../theme"

AppDialog {
    id: root

    width: 620
    title: "Add Map Source"
    description: "Add an analyst-controlled XYZ, WMS, or WMTS source. Credentials in URLs are blocked."
    primaryText: "Add source"
    bodyHeight: sourceType.currentIndex === 0
        ? 338
        : (sourceType.currentIndex === 1 ? 430 : 470)
    primaryEnabled: sourceName.text.trim().length > 0
        && sourceUrl.text.trim().length > 0
        && (sourceType.currentIndex !== 1
            || wmsLayers.text.trim().length > 0)
        && (sourceType.currentIndex !== 2
            || (wmtsLayer.text.trim().length > 0
                && wmtsMatrixSet.text.trim().length > 0))

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
        wmtsLayer.text = ""
        wmtsStyle.text = "default"
        wmtsMatrixSet.text = ""
        wmtsMatrixPrefix.text = ""
    }

    onAccepted: {
        root.sourceSubmitted({
            name: sourceName.text.trim(),
            kind: sourceType.currentIndex === 1
                ? "wms"
                : (sourceType.currentIndex === 2 ? "wmts" : "xyz"),
            url: sourceUrl.text.trim(),
            attribution: attribution.text.trim(),
            termsUrl: termsUrl.text.trim(),
            minZoom: Number(minZoom.text),
            maxZoom: Number(maxZoom.text),
            wmsLayers: wmsLayers.text.trim(),
            wmsStyles: wmsStyles.text.trim(),
            wmsFormat: "image/png",
            wmsVersion: wmsVersion.currentText,
            wmsTransparent: true,
            wmtsLayer: wmtsLayer.text.trim(),
            wmtsStyle: wmtsStyle.text.trim(),
            wmtsFormat: "image/png",
            wmtsMatrixSet: wmtsMatrixSet.text.trim(),
            wmtsMatrixPrefix: wmtsMatrixPrefix.text.trim()
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
                model: ["XYZ", "WMS", "WMTS"]
            }
        }

        AppTextField {
            id: sourceUrl
            Layout.fillWidth: true
            placeholderText: sourceType.currentIndex === 1
                ? "https://example.org/wms"
                : (sourceType.currentIndex === 2
                    ? "https://example.org/wmts"
                    : "https://example.org/{z}/{x}/{y}.png")
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

        AppTextField {
            id: wmtsLayer
            visible: sourceType.currentIndex === 2
            Layout.fillWidth: true
            placeholderText: "WMTS layer"
        }

        RowLayout {
            visible: sourceType.currentIndex === 2
            Layout.fillWidth: true
            spacing: 8

            AppTextField {
                id: wmtsStyle
                Layout.fillWidth: true
                placeholderText: "WMTS style"
                text: "default"
            }

            AppTextField {
                id: wmtsMatrixSet
                Layout.fillWidth: true
                placeholderText: "Tile matrix set"
            }
        }

        AppTextField {
            id: wmtsMatrixPrefix
            visible: sourceType.currentIndex === 2
            Layout.fillWidth: true
            placeholderText: "Tile matrix prefix, optional (example: EPSG:3857:)"
        }

        Text {
            Layout.fillWidth: true
            text: sourceType.currentIndex === 1
                ? "WMS is requested as 256×256 EPSG:3857 GetMap tiles."
                : (sourceType.currentIndex === 2
                    ? "WMTS uses KVP GetTile with the selected matrix set. Prefix is prepended to zoom when the service uses identifiers such as EPSG:3857:0."
                    : "XYZ must contain {z}, {x}, and {y}. Only the visible viewport is requested.")
            color: Theme.textMuted
            font.pixelSize: 9
            wrapMode: Text.Wrap
        }
    }
}

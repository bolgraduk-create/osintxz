import QtQuick
import QtQuick.Effects
import "../theme"

Item {
    id: root

    property url source
    property url fallbackSource
    property color backgroundColor: "#241d38"
    property color borderColor: "#6f5aa8"
    property real borderWidth: 1
    property real inset: 2
    property bool asynchronous: true
    property bool cache: false

    readonly property bool hasImage: source.toString().length > 0

    Rectangle {
        anchors.fill: parent
        radius: Math.min(width, height) / 2
        color: root.backgroundColor
    }

    Image {
        id: sourceImage
        anchors.fill: parent
        anchors.margins: root.inset
        source: root.source
        fillMode: Image.PreserveAspectCrop
        asynchronous: root.asynchronous
        cache: root.cache
        smooth: true
        visible: false
        sourceSize.width: Math.max(64, width * 2)
        sourceSize.height: Math.max(64, height * 2)
    }

    Rectangle {
        id: circleMask
        anchors.fill: sourceImage
        radius: Math.min(width, height) / 2
        color: "white"
        visible: false
        layer.enabled: true
    }

    MultiEffect {
        anchors.fill: sourceImage
        source: sourceImage
        maskEnabled: true
        maskSource: circleMask
        visible: root.hasImage
    }

    Image {
        anchors.centerIn: parent
        width: Math.max(12, parent.width * 0.48)
        height: width
        source: root.fallbackSource
        fillMode: Image.PreserveAspectFit
        smooth: true
        visible: !root.hasImage && root.fallbackSource.toString().length > 0
    }

    Rectangle {
        anchors.fill: parent
        radius: Math.min(width, height) / 2
        color: "transparent"
        border.width: root.borderWidth
        border.color: root.borderColor
    }
}

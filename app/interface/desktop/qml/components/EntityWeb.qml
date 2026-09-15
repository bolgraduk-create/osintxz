pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "../theme"

Item {
    id: root

    property var nodes: []
    property var edges: []
    property real zoom: 1.0
    property real panX: 0
    property real panY: 0
    property bool showEdgeLabels: true
    property bool showTypeLabels: true
    property bool enableNavigation: true
    property string emptyText: "No connected entities"

    signal nodeClicked(string entityId)
    signal nodeDoubleClicked(string entityId)

    function resetView() {
        root.zoom = 1.0
        root.panX = 0
        root.panY = 0
        edgeCanvas.requestPaint()
    }

    function clampZoom(value) {
        return Math.max(0.65, Math.min(1.8, value))
    }

    function zoomBy(delta) {
        root.zoom = clampZoom(root.zoom + delta)
        edgeCanvas.requestPaint()
    }

    function nodeIndex(entityId) {
        var wanted = String(entityId || "")
        for (var i = 0; i < root.nodes.length; ++i) {
            if (String(root.nodes[i].id || "") === wanted) return i
        }
        return -1
    }

    function ringInfo(index, count) {
        if (index === 0 || count <= 1) return { ring: 0, position: 0, count: 1 }
        if (count <= 9) return { ring: 1, position: index - 1, count: count - 1 }
        if (index <= 8) return { ring: 1, position: index - 1, count: 8 }
        return { ring: 2, position: index - 9, count: Math.max(1, count - 9) }
    }

    function nodeX(index, count, width) {
        if (index === 0 || count <= 1) return width * 0.50
        var info = ringInfo(index, count)
        var angle = -Math.PI / 2 + info.position * Math.PI * 2 / info.count
        var radius = info.ring === 1 ? 0.34 : 0.46
        return width * 0.50 + Math.cos(angle) * width * radius
    }

    function nodeY(index, count, height) {
        if (index === 0 || count <= 1) return height * 0.50
        var info = ringInfo(index, count)
        var angle = -Math.PI / 2 + info.position * Math.PI * 2 / info.count
        var radius = info.ring === 1 ? 0.31 : 0.43
        return height * 0.50 + Math.sin(angle) * height * radius
    }

    function nodeIcon(type) {
        var key = String(type || "").toLowerCase()
        if (key === "person") return "../../assets/icons/users_purple.svg"
        if (key === "organization") return "../../assets/icons/building_cyan.svg"
        if (key === "email") return "../../assets/icons/mail_blue.svg"
        if (key === "phone") return "../../assets/icons/phone_green.svg"
        if (key === "location" || key === "address") return "../../assets/icons/pin_purple.svg"
        if (key === "domain" || key === "url" || key === "ip") return "../../assets/icons/globe_blue.svg"
        if (key === "username" || key === "account") return "../../assets/icons/users_cyan.svg"
        return "../../assets/icons/document.svg"
    }

    function nodeColor(type, central, onPath) {
        if (onPath) return "#f0b84f"
        if (central) return Theme.accent
        var key = String(type || "").toLowerCase()
        if (key === "person") return "#9b78e7"
        if (key === "organization") return "#47bfd8"
        if (key === "email") return "#6d8ee8"
        if (key === "phone") return "#36cfa1"
        if (key === "username" || key === "account") return "#6b9df2"
        if (key === "location" || key === "address") return "#a066e5"
        if (key === "domain" || key === "url") return "#51aef0"
        if (key === "ip") return "#e5a84b"
        return "#8094a8"
    }

    Canvas {
        anchors.fill: parent
        opacity: 0.08
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.fillStyle = "#31516b"
            for (var py = 5; py < height; py += 16)
                for (var px = 7; px < width; px += 16)
                    ctx.fillRect(px, py, 1, 1)
        }
    }

    Item {
        id: transformLayer
        width: root.width
        height: root.height
        x: root.panX
        y: root.panY
        scale: root.zoom
        transformOrigin: Item.Center

        Canvas {
            id: edgeCanvas
            anchors.fill: parent
            onPaint: {
                var ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                for (var e = 0; e < root.edges.length; ++e) {
                    var edge = root.edges[e]
                    var a = root.nodeIndex(edge.source)
                    var b = root.nodeIndex(edge.target)
                    if (a < 0 || b < 0) continue
                    ctx.strokeStyle = edge.path ? "#f0b84f" : (edge.profile ? "#58a6ff" : "#7892aa")
                    ctx.lineWidth = edge.path ? 3.0 : (edge.profile ? 1.8 : 1.2)
                    ctx.globalAlpha = edge.path ? 1.0 : 0.78
                    ctx.beginPath()
                    ctx.moveTo(root.nodeX(a, root.nodes.length, width), root.nodeY(a, root.nodes.length, height))
                    ctx.lineTo(root.nodeX(b, root.nodes.length, width), root.nodeY(b, root.nodes.length, height))
                    ctx.stroke()
                }
            }
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
        }

        Repeater {
            model: root.showEdgeLabels ? root.edges : []
            delegate: Item {
                id: edgeBadge
                required property var modelData
                property int sourceIndex: root.nodeIndex(edgeBadge.modelData.source)
                property int targetIndex: root.nodeIndex(edgeBadge.modelData.target)
                visible: sourceIndex >= 0 && targetIndex >= 0
                x: (
                    root.nodeX(sourceIndex, root.nodes.length, transformLayer.width)
                    + root.nodeX(targetIndex, root.nodes.length, transformLayer.width)
                ) / 2 - width / 2
                y: (
                    root.nodeY(sourceIndex, root.nodes.length, transformLayer.height)
                    + root.nodeY(targetIndex, root.nodes.length, transformLayer.height)
                ) / 2 - height / 2
                width: Math.min(132, Math.max(58, edgeText.implicitWidth + 16))
                height: 22

                Rectangle {
                    anchors.fill: parent
                    radius: 6
                    color: edgeBadge.modelData.path ? "#3b3015" : "#132534"
                    border.color: edgeBadge.modelData.path ? "#f0b84f" : "#29465d"
                }
                Text {
                    id: edgeText
                    anchors.centerIn: parent
                    width: parent.width - 10
                    text: String(edgeBadge.modelData.label || "RELATED")
                    color: edgeBadge.modelData.path ? "#f0c96a" : Theme.textSecondary
                    font.pixelSize: 7
                    font.weight: Font.Medium
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                }
            }
        }

        Repeater {
            model: root.nodes
            delegate: Item {
                id: graphNode
                required property var modelData
                required property int index
                anchors.fill: parent
                property bool central: index === 0 || Boolean(modelData.central)
                property bool personNode: String(modelData.type || "").toLowerCase() === "person"
                property bool onPath: Boolean(modelData.path)
                property real nodeSize: central ? 82 : (index <= 8 ? 54 : 46)
                property real cx: root.nodeX(index, root.nodes.length, transformLayer.width)
                property real cy: root.nodeY(index, root.nodes.length, transformLayer.height)
                property color accent: root.nodeColor(modelData.type, central, onPath)

                CircularAvatar {
                    x: graphNode.cx - graphNode.nodeSize / 2
                    y: graphNode.cy - graphNode.nodeSize / 2
                    width: graphNode.nodeSize
                    height: graphNode.nodeSize
                    visible: graphNode.personNode
                    source: String(graphNode.modelData.avatarUrl || "")
                    fallbackSource: "../../assets/icons/users_purple.svg"
                    backgroundColor: graphNode.central ? "#142a43" : "#241d38"
                    borderColor: graphNode.accent
                    borderWidth: graphNode.central || graphNode.onPath ? 3 : 2
                    inset: source.toString().length > 0 ? 2 : 0
                }

                Rectangle {
                    x: graphNode.cx - graphNode.nodeSize / 2
                    y: graphNode.cy - graphNode.nodeSize / 2
                    width: graphNode.nodeSize
                    height: graphNode.nodeSize
                    radius: width / 2
                    visible: !graphNode.personNode
                    color: graphNode.central ? "#142a43" : "#112534"
                    border.width: graphNode.central || graphNode.onPath ? 3 : 2
                    border.color: graphNode.accent
                    Image {
                        anchors.centerIn: parent
                        width: parent.width * 0.46
                        height: width
                        source: root.nodeIcon(graphNode.modelData.type)
                        fillMode: Image.PreserveAspectFit
                    }
                }

                Rectangle {
                    x: graphNode.cx - graphNode.nodeSize / 2
                    y: graphNode.cy - graphNode.nodeSize / 2
                    width: graphNode.nodeSize
                    height: graphNode.nodeSize
                    radius: width / 2
                    color: nodeMouse.containsMouse ? "#16ffffff" : "transparent"
                    border.width: nodeMouse.containsMouse ? 2 : 0
                    border.color: "#d9e8ff"

                    MouseArea {
                        id: nodeMouse
                        anchors.fill: parent
                        anchors.margins: -7
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.nodeClicked(String(graphNode.modelData.id || ""))
                        onDoubleClicked: root.nodeDoubleClicked(String(graphNode.modelData.id || ""))
                    }
                }

                Column {
                    x: graphNode.cx - width / 2
                    y: graphNode.cy + graphNode.nodeSize / 2 + 5
                    width: graphNode.central ? 176 : 112
                    spacing: 1

                    Text {
                        width: parent.width
                        text: String(graphNode.modelData.label || "Unnamed entity")
                        color: Theme.textPrimary
                        font.pixelSize: graphNode.central ? 12 : 9
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                    }
                    Text {
                        width: parent.width
                        visible: root.showTypeLabels
                        text: String(graphNode.modelData.type || "Entity").replace("_", " ")
                        color: graphNode.accent
                        font.pixelSize: 8
                        horizontalAlignment: Text.AlignHCenter
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }

    MouseArea {
        id: panArea
        anchors.fill: parent
        z: 50
        hoverEnabled: true
        acceptedButtons: Qt.MiddleButton | Qt.RightButton
        property real pressX: 0
        property real pressY: 0
        property real startPanX: 0
        property real startPanY: 0
        onPressed: function(mouse) {
            pressX = mouse.x
            pressY = mouse.y
            startPanX = root.panX
            startPanY = root.panY
        }
        onPositionChanged: function(mouse) {
            if (!pressed) return
            root.panX = startPanX + mouse.x - pressX
            root.panY = startPanY + mouse.y - pressY
        }
        onWheel: function(wheel) {
            root.zoom = root.clampZoom(root.zoom + (wheel.angleDelta.y > 0 ? 0.1 : -0.1))
            edgeCanvas.requestPaint()
            wheel.accepted = true
        }
    }

    Text {
        anchors.centerIn: parent
        visible: root.nodes.length === 0
        text: root.emptyText
        color: Theme.textMuted
        font.pixelSize: 12
        horizontalAlignment: Text.AlignHCenter
    }
}

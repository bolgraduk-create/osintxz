pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root

    property var run: analysisBridge.runData || ({})
    property var provider: analysisBridge.providerInfo || ({})
    property var catalog: analysisBridge.catalog || ({})
    property var focusOptions: analysisBridge.focusOptions || []
    property var historyRows: analysisBridge.history || []
    property var stages: run.stages || []
    property var conclusions: run.conclusions || []
    property var facts: run.facts || []
    property var sources: run.sources || []
    property var warnings: run.warnings || []
    property var citationSummary: run.citationSummary || ({})
    property string selectedMode: "standard"
    property string selectedModel: "gpt-5.6-terra"
    property string selectedReasoning: "medium"
    property int selectedFocusIndex: 0
    property string activeView: "overview"
    property string preparedCaseId: ""

    readonly property var layerItems: [
        {key:"overview", label:"Overview", icon:"chart.svg"},
        {key:"facts", label:"Facts", icon:"document_blue.svg"},
        {key:"hypotheses", label:"Hypotheses", icon:"search.svg"},
        {key:"contradictions", label:"Contradictions", icon:"chart.svg"},
        {key:"next_steps", label:"Next Steps", icon:"search.svg"},
        {key:"sources", label:"Sources", icon:"document_blue.svg"},
        {key:"pipeline", label:"Pipeline", icon:"graph_blue.svg"},
        {key:"history", label:"History", icon:"clock.svg"}
    ]

    function reload() {
        root.run = analysisBridge.runData || ({})
        root.provider = analysisBridge.providerInfo || ({})
        root.catalog = analysisBridge.catalog || ({})
        root.focusOptions = analysisBridge.focusOptions || []
        root.historyRows = analysisBridge.history || []
        root.stages = root.run.stages || []
        root.conclusions = root.run.conclusions || []
        root.facts = root.run.facts || []
        root.sources = root.run.sources || []
        root.warnings = root.run.warnings || []
        root.citationSummary = root.run.citationSummary || ({})
    }

    function prepareCase() {
        const caseId = String(desktopBridge.currentCaseId || "")
        if (caseId === root.preparedCaseId)
            return
        root.preparedCaseId = caseId
        root.selectedFocusIndex = 0
        analysisBridge.prepareCase(caseId)
    }

    function modes() {
        return root.catalog.modes || []
    }

    function models() {
        return root.catalog.models || []
    }

    function reasoningEfforts() {
        return root.catalog.reasoningEfforts || ["none", "low", "medium", "high", "xhigh", "max"]
    }

    function modeInfo(key) {
        const values = root.modes()
        for (let i = 0; i < values.length; ++i) {
            if (String(values[i].key) === String(key))
                return values[i]
        }
        return ({})
    }

    function modelLabels() {
        if (String(root.provider.provider || "") !== "openai")
            return [String(root.provider.model || "Local model")]
        const values = root.models()
        const out = []
        for (let i = 0; i < values.length; ++i)
            out.push(String(values[i].label) + " · " + String(values[i].tier))
        return out
    }

    function modelIndex(modelId) {
        const values = root.models()
        for (let i = 0; i < values.length; ++i) {
            if (String(values[i].id) === String(modelId))
                return i
        }
        return 0
    }

    function reasoningIndex(value) {
        const values = root.reasoningEfforts()
        for (let i = 0; i < values.length; ++i) {
            if (String(values[i]) === String(value))
                return i
        }
        return 0
    }

    function focusLabels() {
        const out = []
        for (let i = 0; i < root.focusOptions.length; ++i)
            out.push(String(root.focusOptions[i].label || "Unknown"))
        return out
    }

    function selectedFocus() {
        if (root.selectedFocusIndex < 0 || root.selectedFocusIndex >= root.focusOptions.length)
            return ({ id:"", label:"Entire Investigation", type:"case" })
        return root.focusOptions[root.selectedFocusIndex]
    }

    function applyMode(key) {
        const info = root.modeInfo(key)
        root.selectedMode = String(info.key || key || "standard")
        if (String(root.provider.provider || "") === "openai") {
            if (info.recommendedModel)
                root.selectedModel = String(info.recommendedModel)
            if (info.recommendedReasoning)
                root.selectedReasoning = String(info.recommendedReasoning)
            modelBox.currentIndex = root.modelIndex(root.selectedModel)
            reasoningBox.currentIndex = root.reasoningIndex(root.selectedReasoning)
        } else {
            root.selectedModel = String(root.provider.model || "")
            root.selectedReasoning = ""
            modelBox.currentIndex = 0
            reasoningBox.currentIndex = 0
        }
    }

    function conclusionsFor(kind) {
        const out = []
        for (let i = 0; i < root.conclusions.length; ++i) {
            if (String(root.conclusions[i].kind || "") === String(kind))
                out.push(root.conclusions[i])
        }
        return out
    }

    function navCount(key) {
        if (key === "facts") return root.facts.length
        if (key === "hypotheses") return root.conclusionsFor("hypotheses").length
        if (key === "contradictions") return root.conclusionsFor("contradictions").length
        if (key === "next_steps") return root.conclusionsFor("next_steps").length
        if (key === "sources") return root.sources.length
        if (key === "pipeline") return root.stages.length
        if (key === "history") return root.historyRows.length
        return 0
    }

    function activeViewIndex() {
        for (let i = 0; i < root.layerItems.length; ++i) {
            if (String(root.layerItems[i].key) === root.activeView)
                return i
        }
        return 0
    }

    function statusColor(status) {
        const value = String(status || "").toLowerCase()
        if (value === "success" || value === "completed") return Theme.success
        if (value === "partial" || value === "skipped") return Theme.warning
        if (value === "failed" || value === "cancelled") return Theme.danger
        if (value === "running") return Theme.accent
        return Theme.textMuted
    }

    function runAnalysisNow() {
        const focus = root.selectedFocus()
        analysisBridge.runAnalysis(
            String(desktopBridge.currentCaseId || ""),
            questionInput.text,
            root.selectedMode,
            root.selectedModel,
            root.selectedReasoning,
            String(focus.type || "case"),
            String(focus.id || ""),
            String(focus.label || "Entire Investigation")
        )
    }

    function sourceRefsForSummary() {
        return root.run.summarySourceReferences || []
    }

    function openHistory(id) {
        if (analysisBridge.openHistory(String(id || ""))) {
            root.activeView = "overview"
            root.reload()
        }
    }

    function usePrompt(value) {
        questionInput.text = String(value || "")
        questionInput.forceActiveFocus()
    }

    Connections {
        target: analysisBridge
        function onChanged() { root.reload() }
    }

    Connections {
        target: desktopBridge
        function onChanged() { root.prepareCase() }
    }

    Component.onCompleted: {
        root.reload()
        root.prepareCase()
        root.applyMode("standard")
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        anchors.topMargin: 14
        anchors.bottomMargin: 18
        spacing: 12

        // Compact page header.
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 62

            Column {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Text {
                    text: "ANALYSIS LAB"
                    color: Theme.accent
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.7
                }

                Text {
                    text: "AI Analysis"
                    color: Theme.textPrimary
                    font.pixelSize: 28
                    font.weight: Font.DemiBold
                }

                Text {
                    text: desktopBridge.hasCurrentCase
                        ? ("Grounded reasoning over “" + String(desktopBridge.currentCaseTitle || "Investigation") + "”")
                        : "Select an investigation to begin."
                    color: Theme.textMuted
                    font.pixelSize: 10
                }
            }

            Rectangle {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(330, parent.width * 0.32)
                height: 44
                radius: 22
                color: Theme.surface
                border.width: 1
                border.color: Theme.border

                Rectangle {
                    x: 13
                    anchors.verticalCenter: parent.verticalCenter
                    width: 7
                    height: 7
                    radius: 4
                    color: Boolean(root.provider.configured) ? Theme.success : Theme.danger
                }

                Text {
                    x: 29
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 42
                    text: String(root.provider.label || "AI")
                        + " · " + String(root.provider.model || "No model")
                        + (String(root.provider.provider || "") === "openai" && root.provider.storeResponses === false
                            ? " · storage off"
                            : "")
                    color: Boolean(root.provider.configured) ? Theme.textSecondary : Theme.danger
                    font.pixelSize: 9
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            // Analysis navigation rail.
            Rectangle {
                objectName: "analysisLayerRail"
                Layout.preferredWidth: 188
                Layout.fillHeight: true
                radius: 10
                color: "#0b1a26"
                border.width: 1
                border.color: Theme.border

                Column {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 5

                    Text {
                        width: parent.width
                        height: 30
                        text: "ANALYTIC LAYERS"
                        color: Theme.textMuted
                        font.pixelSize: 8
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.15
                        verticalAlignment: Text.AlignVCenter
                    }

                    Repeater {
                        model: root.layerItems

                        delegate: Rectangle {
                            id: layerRow
                            required property var modelData
                            width: parent.width
                            height: 39
                            radius: 7
                            color: root.activeView === String(layerRow.modelData.key)
                                ? Theme.accentSoft
                                : (layerMouse.containsMouse ? Theme.surfaceHover : "transparent")

                            Rectangle {
                                visible: root.activeView === String(layerRow.modelData.key)
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                width: 3
                                height: 22
                                radius: 2
                                color: Theme.accent
                            }

                            Image {
                                anchors.left: parent.left
                                anchors.leftMargin: 11
                                anchors.verticalCenter: parent.verticalCenter
                                width: 16
                                height: 16
                                source: "../../assets/icons/" + String(layerRow.modelData.icon || "chart.svg")
                                opacity: root.activeView === String(layerRow.modelData.key) ? 1 : 0.72
                            }

                            Text {
                                x: 36
                                anchors.verticalCenter: parent.verticalCenter
                                text: String(layerRow.modelData.label)
                                color: root.activeView === String(layerRow.modelData.key)
                                    ? Theme.textPrimary
                                    : Theme.textSecondary
                                font.pixelSize: 10
                                font.weight: root.activeView === String(layerRow.modelData.key)
                                    ? Font.DemiBold
                                    : Font.Normal
                            }

                            Rectangle {
                                visible: root.navCount(String(layerRow.modelData.key)) > 0
                                anchors.right: parent.right
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.max(23, layerCount.implicitWidth + 10)
                                height: 19
                                radius: 10
                                color: "#0d1c28"

                                Text {
                                    id: layerCount
                                    anchors.centerIn: parent
                                    text: String(root.navCount(String(layerRow.modelData.key)))
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                }
                            }

                            MouseArea {
                                id: layerMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.activeView = String(layerRow.modelData.key)
                            }
                        }
                    }

                    Item {
                        width: parent.width
                        height: 8
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Theme.divider
                    }

                    Column {
                        width: parent.width
                        spacing: 7

                        Text {
                            width: parent.width
                            text: Boolean(root.run.hasRun) ? "CURRENT RUN" : "READY"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.0
                        }

                        Text {
                            width: parent.width
                            text: Boolean(root.run.hasRun) && root.run.runConfig
                                ? (String(root.run.runConfig.modeLabel || "Analysis")
                                    + " · " + String(root.run.runConfig.reasoningEffort || ""))
                                : String(root.selectedMode).toUpperCase() + " MODE"
                            color: Theme.textSecondary
                            font.pixelSize: 9
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            text: Boolean(root.run.hasRun) && root.run.cost
                                ? ("Cost " + String(root.run.cost.display || "—"))
                                : "No analysis started"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            elide: Text.ElideRight
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10

                // Chat-like analysis composer.
                Rectangle {
                    objectName: "analysisComposer"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 206
                    radius: 12
                    color: "#0d1c28"
                    border.width: 1
                    border.color: questionInput.activeFocus ? Theme.borderHover : Theme.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 9

                        Row {
                            id: modeRow
                            objectName: "analysisModeRow"
                            width: parent.width
                            height: 38
                            spacing: 7

                            Repeater {
                                model: root.modes()

                                delegate: Rectangle {
                                    id: modePill
                                    required property var modelData
                                    width: (modeRow.width - 14) / 3
                                    height: 38
                                    radius: 19
                                    color: root.selectedMode === String(modePill.modelData.key)
                                        ? Theme.accentSoft
                                        : "#10202d"
                                    border.width: 1
                                    border.color: root.selectedMode === String(modePill.modelData.key)
                                        ? Theme.accent
                                        : Theme.border

                                    Row {
                                        anchors.centerIn: parent
                                        spacing: 7

                                        Text {
                                            text: String(modePill.modelData.label || "")
                                            color: root.selectedMode === String(modePill.modelData.key)
                                                ? Theme.textPrimary
                                                : Theme.textSecondary
                                            font.pixelSize: 10
                                            font.weight: Font.DemiBold
                                        }

                                        Text {
                                            text: "· " + String(modePill.modelData.requests || 1)
                                                + (Number(modePill.modelData.requests || 1) === 1 ? " call" : " calls")
                                            color: Theme.textMuted
                                            font.pixelSize: 8
                                        }
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: !analysisBridge.busy
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.applyMode(String(modePill.modelData.key || "standard"))
                                    }
                                }
                            }
                        }

                        Rectangle {
                            width: parent.width
                            height: 82
                            radius: 9
                            color: Theme.background
                            border.width: 1
                            border.color: questionInput.activeFocus ? Theme.accent : Theme.divider

                            TextArea {
                                id: questionInput
                                anchors.fill: parent
                                anchors.margins: 7
                                placeholderText: "Ask what you want to understand about this investigation..."
                                wrapMode: TextEdit.Wrap
                                color: Theme.textPrimary
                                placeholderTextColor: Theme.textMuted
                                selectionColor: Theme.accent
                                selectedTextColor: "#ffffff"
                                font.pixelSize: 11
                                enabled: !analysisBridge.busy
                                background: Rectangle { color: "transparent" }
                            }
                        }

                        Row {
                            objectName: "analysisControlRow"
                            width: parent.width
                            height: 48
                            spacing: 8

                            Column {
                                width: Math.max(1, (parent.width - 182) * 0.28)
                                height: 48
                                spacing: 3
                                Text {
                                    text: "SCOPE"
                                    color: Theme.textMuted
                                    font.pixelSize: 7
                                    font.letterSpacing: 0.9
                                }
                                AppComboBox {
                                    id: scopeBox
                                    width: parent.width
                                    height: 32
                                    model: root.focusLabels()
                                    enabled: !analysisBridge.busy
                                    onCurrentIndexChanged: root.selectedFocusIndex = currentIndex
                                }
                            }

                            Column {
                                width: Math.max(1, (parent.width - 182) * 0.44)
                                height: 48
                                spacing: 3
                                Text {
                                    text: "MODEL"
                                    color: Theme.textMuted
                                    font.pixelSize: 7
                                    font.letterSpacing: 0.9
                                }
                                AppComboBox {
                                    id: modelBox
                                    width: parent.width
                                    height: 32
                                    model: root.modelLabels()
                                    enabled: !analysisBridge.busy && String(root.provider.provider || "") === "openai"
                                    onCurrentIndexChanged: {
                                        const values = root.models()
                                        if (currentIndex >= 0 && currentIndex < values.length)
                                            root.selectedModel = String(values[currentIndex].id || root.selectedModel)
                                    }
                                }
                            }

                            Column {
                                width: Math.max(1, (parent.width - 182) * 0.28)
                                height: 48
                                spacing: 3
                                Text {
                                    text: "REASONING"
                                    color: Theme.textMuted
                                    font.pixelSize: 7
                                    font.letterSpacing: 0.9
                                }
                                AppComboBox {
                                    id: reasoningBox
                                    width: parent.width
                                    height: 32
                                    model: String(root.provider.provider || "") === "openai"
                                        ? root.reasoningEfforts()
                                        : ["Local provider"]
                                    enabled: !analysisBridge.busy && String(root.provider.provider || "") === "openai"
                                    onCurrentIndexChanged: {
                                        const values = root.reasoningEfforts()
                                        if (currentIndex >= 0 && currentIndex < values.length)
                                            root.selectedReasoning = String(values[currentIndex])
                                    }
                                }
                            }

                            AppButton {
                                id: runButton
                                y: 5
                                width: 150
                                height: 38
                                text: analysisBridge.busy ? "Analyzing…" : "Run Analysis"
                                primary: true
                                enabled: !analysisBridge.busy
                                    && desktopBridge.hasCurrentCase
                                    && Boolean(root.provider.configured)
                                onClicked: root.runAnalysisNow()
                            }
                        }
                    }
                }

                // Running/completed strip.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: analysisBridge.busy || Boolean(root.run.hasRun) ? 50 : 0
                    visible: analysisBridge.busy || Boolean(root.run.hasRun)
                    radius: 9
                    color: Theme.surface
                    border.width: 1
                    border.color: analysisBridge.busy ? Theme.accent : Theme.border

                    Rectangle {
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        width: 8
                        height: 8
                        radius: 4
                        color: root.statusColor(root.run.status || (analysisBridge.busy ? "running" : ""))
                    }

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 30
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 270
                        text: String(root.run.progressText || root.run.status || "")
                            + (root.run.currentStageLabel ? " · " + String(root.run.currentStageLabel) : "")
                        color: Theme.textSecondary
                        font.pixelSize: 9
                        elide: Text.ElideRight
                    }

                    Text {
                        anchors.right: clearRunButton.left
                        anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        text: Boolean(root.run.hasRun) && root.run.durationText
                            ? String(root.run.durationText)
                            : (root.run.stageCount ? String(root.run.stageIndex || 0) + "/" + String(root.run.stageCount) : "")
                        color: Theme.textMuted
                        font.pixelSize: 8
                    }

                    AppButton {
                        id: clearRunButton
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        width: 92
                        height: 32
                        text: "Clear"
                        quiet: true
                        enabled: !analysisBridge.busy && Boolean(root.run.hasRun)
                        onClicked: analysisBridge.clear()
                    }
                }

                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: root.activeViewIndex()

                    // OVERVIEW
                    Flickable {
                        clip: true
                        contentWidth: width
                        contentHeight: overviewContent.height
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        Column {
                            id: overviewContent
                            width: Math.min(parent.width - 28, 920)
                            x: Math.max(14, (parent.width - width) / 2)
                            spacing: 18

                            Item {
                                width: parent.width
                                height: !Boolean(root.run.hasRun) ? Math.max(330, overviewContent.parent.height - 20) : 0
                                visible: !Boolean(root.run.hasRun)

                                Column {
                                    anchors.centerIn: parent
                                    width: Math.min(parent.width - 40, 720)
                                    spacing: 14

                                    Rectangle {
                                        x: (parent.width - width) / 2
                                        width: 46
                                        height: 46
                                        radius: 23
                                        color: Theme.accentSoft
                                        border.width: 1
                                        border.color: Theme.accent

                                        Text {
                                            anchors.centerIn: parent
                                            text: "AI"
                                            color: Theme.accent
                                            font.pixelSize: 12
                                            font.weight: Font.Bold
                                        }
                                    }

                                    Text {
                                        width: parent.width
                                        text: desktopBridge.hasCurrentCase
                                            ? "What do you want to understand?"
                                            : "Select an investigation first"
                                        color: Theme.textPrimary
                                        font.pixelSize: 22
                                        font.weight: Font.DemiBold
                                        horizontalAlignment: Text.AlignHCenter
                                    }

                                    Text {
                                        width: parent.width
                                        text: desktopBridge.hasCurrentCase
                                            ? "Ask a focused question, or use one of the starting points below. Analysis stays grounded in the investigation’s bounded sources."
                                            : "Analysis needs an active case before it can build grounded context."
                                        color: Theme.textMuted
                                        font.pixelSize: 10
                                        lineHeight: 1.35
                                        wrapMode: Text.Wrap
                                        horizontalAlignment: Text.AlignHCenter
                                    }

                                    Row {
                                        id: suggestionRow
                                        width: parent.width
                                        spacing: 8

                                        Repeater {
                                            model: [
                                                {title:"Summarize the case", prompt:"Summarize the most important findings in this investigation and explain what matters most."},
                                                {title:"Find contradictions", prompt:"Identify the strongest contradictions or inconsistencies in the available investigation data."},
                                                {title:"Plan next steps", prompt:"Based on the available evidence, what should be investigated next and why?"}
                                            ]

                                            delegate: Rectangle {
                                                id: promptCard
                                                required property var modelData
                                                width: (suggestionRow.width - 16) / 3
                                                height: 70
                                                radius: 10
                                                color: promptMouse.containsMouse ? Theme.surfaceHover : Theme.surface
                                                border.width: 1
                                                border.color: promptMouse.containsMouse ? Theme.borderHover : Theme.border
                                                opacity: desktopBridge.hasCurrentCase ? 1 : 0.5

                                                Text {
                                                    x: 12
                                                    y: 12
                                                    width: parent.width - 24
                                                    text: String(promptCard.modelData.title)
                                                    color: Theme.textPrimary
                                                    font.pixelSize: 10
                                                    font.weight: Font.DemiBold
                                                    elide: Text.ElideRight
                                                }

                                                Text {
                                                    x: 12
                                                    y: 36
                                                    width: parent.width - 24
                                                    text: "Use prompt"
                                                    color: Theme.accent
                                                    font.pixelSize: 8
                                                }

                                                MouseArea {
                                                    id: promptMouse
                                                    anchors.fill: parent
                                                    enabled: desktopBridge.hasCurrentCase
                                                    hoverEnabled: true
                                                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                    onClicked: root.usePrompt(String(promptCard.modelData.prompt))
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // Assistant-style response header.
                            Row {
                                visible: Boolean(root.run.hasRun)
                                width: parent.width
                                spacing: 12

                                Rectangle {
                                    width: 34
                                    height: 34
                                    radius: 17
                                    color: Theme.accentSoft
                                    border.width: 1
                                    border.color: Theme.accent
                                    Text {
                                        anchors.centerIn: parent
                                        text: "AI"
                                        color: Theme.accent
                                        font.pixelSize: 9
                                        font.weight: Font.Bold
                                    }
                                }

                                Column {
                                    width: parent.width - 46
                                    spacing: 3

                                    Text {
                                        text: "Analysis"
                                        color: Theme.textPrimary
                                        font.pixelSize: 12
                                        font.weight: Font.DemiBold
                                    }

                                    Text {
                                        width: parent.width
                                        text: String(root.run.scope && root.run.scope.label ? root.run.scope.label : "Entire Investigation")
                                            + " · "
                                            + String(root.run.runConfig && root.run.runConfig.modeLabel ? root.run.runConfig.modeLabel : "Analysis")
                                            + " · "
                                            + String(root.run.runConfig && root.run.runConfig.model ? root.run.runConfig.model : root.provider.model || "")
                                        color: Theme.textMuted
                                        font.pixelSize: 8
                                        elide: Text.ElideRight
                                    }
                                }
                            }

                            // Keep explicit title contracts from R13.28b while rendering minimally.
                            Panel {
                                visible: Boolean(root.run.hasRun)
                                width: parent.width
                                height: Math.max(210, summaryBody.implicitHeight + 105)
                                title: "AI Summary"
                                subtitle: "Grounded response · citations open the underlying source"
                                headerDivider: false
                                color: "transparent"
                                border.width: 0

                                Column {
                                    anchors.fill: parent
                                    anchors.leftMargin: 18
                                    anchors.rightMargin: 18
                                    anchors.bottomMargin: 8
                                    spacing: 12

                                    Text {
                                        id: summaryBody
                                        width: parent.width
                                        text: String(root.run.summary || "No AI summary was produced.")
                                        color: Theme.textPrimary
                                        font.pixelSize: 12
                                        lineHeight: 1.5
                                        wrapMode: Text.Wrap
                                        textFormat: Text.PlainText
                                    }

                                    Flow {
                                        width: parent.width
                                        spacing: 7

                                        Repeater {
                                            model: root.sourceRefsForSummary()

                                            delegate: Rectangle {
                                                id: summaryRef
                                                required property var modelData
                                                width: summaryRefText.implicitWidth + 18
                                                height: 25
                                                radius: 13
                                                color: Theme.accentSoft
                                                border.width: 1
                                                border.color: Theme.accent

                                                Text {
                                                    id: summaryRefText
                                                    anchors.centerIn: parent
                                                    text: String(summaryRef.modelData)
                                                    color: Theme.accent
                                                    font.pixelSize: 8
                                                    font.weight: Font.DemiBold
                                                }

                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: analysisBridge.openSource(String(summaryRef.modelData))
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                visible: Boolean(root.run.hasRun)
                                width: parent.width
                                height: 82
                                radius: 10
                                color: "#0d1c28"
                                border.width: 1
                                border.color: Theme.border

                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 6

                                    Repeater {
                                        model: [
                                            {label:"SOURCES", value:root.sources.length},
                                            {label:"FACTS", value:root.facts.length},
                                            {label:"VALID REFS", value:root.citationSummary.valid || 0},
                                            {label:"AI CALLS", value:root.run.usage ? (root.run.usage.requests || 0) : 0},
                                            {label:"EST. COST", value:root.run.cost ? (root.run.cost.display || "—") : "—"}
                                        ]

                                        delegate: Rectangle {
                                            id: overviewMetric
                                            required property var modelData
                                            width: (parent.width - 24) / 5
                                            height: parent.height
                                            radius: 7
                                            color: Theme.surface

                                            Text {
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                y: 13
                                                text: String(overviewMetric.modelData.value)
                                                color: Theme.textPrimary
                                                font.pixelSize: 17
                                                font.weight: Font.DemiBold
                                            }

                                            Text {
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                y: 41
                                                text: String(overviewMetric.modelData.label)
                                                color: Theme.textMuted
                                                font.pixelSize: 7
                                                font.letterSpacing: 0.65
                                            }
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                visible: Boolean(root.run.hasRun)
                                width: parent.width
                                height: root.run.redactions && root.run.redactions.active ? 80 : 58
                                radius: 9
                                color: Theme.surface
                                border.width: 1
                                border.color: Theme.border

                                Text {
                                    anchors.fill: parent
                                    anchors.margins: 13
                                    text: String(root.run.notice || "AI output is analysis, not Evidence.")
                                        + (root.run.redactions && root.run.redactions.active
                                            ? ("\nSECURITY · " + String(root.run.redactions.count || 0)
                                                + " credential/secret fragment(s) were redacted.")
                                            : "")
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    lineHeight: 1.25
                                    wrapMode: Text.Wrap
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Item { width: parent.width; height: 10 }
                        }
                    }

                    // FACTS
                    Flickable {
                        clip: true
                        contentWidth: width
                        contentHeight: factsContent.height
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        Column {
                            id: factsContent
                            width: Math.min(parent.width - 28, 920)
                            x: Math.max(14, (parent.width - width) / 2)
                            spacing: 10

                            Text {
                                width: parent.width
                                height: 46
                                text: "Facts"
                                color: Theme.textPrimary
                                font.pixelSize: 21
                                font.weight: Font.DemiBold
                                verticalAlignment: Text.AlignVCenter
                            }

                            Text {
                                width: parent.width
                                text: "Source-backed observations selected into the bounded RAG context. They are separated from AI inference and are not automatically independently verified."
                                color: Theme.textMuted
                                font.pixelSize: 9
                                lineHeight: 1.35
                                wrapMode: Text.Wrap
                            }

                            Repeater {
                                model: root.facts

                                delegate: Rectangle {
                                    id: factCard
                                    required property var modelData
                                    width: parent.width
                                    height: Math.max(92, factText.implicitHeight + 48)
                                    radius: 10
                                    color: Theme.surface
                                    border.width: 1
                                    border.color: Theme.border

                                    Rectangle {
                                        x: 12
                                        y: 12
                                        width: 40
                                        height: 23
                                        radius: 12
                                        color: Theme.accentSoft

                                        Text {
                                            anchors.centerIn: parent
                                            text: String(factCard.modelData.reference || "R?")
                                            color: Theme.accent
                                            font.pixelSize: 8
                                            font.weight: Font.DemiBold
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: analysisBridge.openSource(String(factCard.modelData.reference || ""))
                                        }
                                    }

                                    Text {
                                        x: 62
                                        y: 14
                                        width: parent.width - 76
                                        text: String(factCard.modelData.title || "Source observation")
                                        color: Theme.textPrimary
                                        font.pixelSize: 10
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        id: factText
                                        x: 14
                                        y: 45
                                        width: parent.width - 28
                                        text: String(factCard.modelData.text || "")
                                        color: Theme.textSecondary
                                        font.pixelSize: 10
                                        lineHeight: 1.35
                                        wrapMode: Text.Wrap
                                    }
                                }
                            }

                            Text {
                                visible: root.facts.length === 0
                                width: parent.width
                                height: 120
                                text: "No source-backed observations are available for this run."
                                color: Theme.textMuted
                                font.pixelSize: 10
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    // HYPOTHESES
                    Flickable {
                        clip: true
                        contentWidth: width
                        contentHeight: hypothesesContent.height
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        Column {
                            id: hypothesesContent
                            width: Math.min(parent.width - 28, 920)
                            x: Math.max(14, (parent.width - width) / 2)
                            spacing: 10

                            Text {
                                width: parent.width
                                height: 46
                                text: "Hypotheses"
                                color: Theme.textPrimary
                                font.pixelSize: 21
                                font.weight: Font.DemiBold
                                verticalAlignment: Text.AlignVCenter
                            }

                            Text {
                                width: parent.width
                                text: "Candidate explanations generated from the bounded source set. These are analytical inferences, not facts or Evidence."
                                color: Theme.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }

                            Repeater {
                                model: root.conclusionsFor("hypotheses")
                                delegate: Rectangle {
                                    id: hypothesisCard
                                    required property var modelData
                                    width: parent.width
                                    height: Math.max(170, hypothesisText.implicitHeight + 75)
                                    radius: 10
                                    color: Theme.surface
                                    border.width: 1
                                    border.color: Theme.border

                                    Text {
                                        x: 14
                                        y: 13
                                        text: "AI INFERENCE"
                                        color: Theme.accent
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: 0.9
                                    }

                                    Text {
                                        id: hypothesisText
                                        x: 14
                                        y: 39
                                        width: parent.width - 28
                                        text: String(hypothesisCard.modelData.text || "")
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        lineHeight: 1.45
                                        wrapMode: Text.Wrap
                                    }

                                    Flow {
                                        x: 14
                                        y: hypothesisText.y + hypothesisText.implicitHeight + 12
                                        width: parent.width - 28
                                        spacing: 6

                                        Repeater {
                                            model: hypothesisCard.modelData.sourceReferences || []
                                            delegate: Rectangle {
                                                id: hypothesisRef
                                                required property var modelData
                                                width: hypothesisRefText.implicitWidth + 18
                                                height: 24
                                                radius: 12
                                                color: Theme.accentSoft
                                                Text {
                                                    id: hypothesisRefText
                                                    anchors.centerIn: parent
                                                    text: String(hypothesisRef.modelData)
                                                    color: Theme.accent
                                                    font.pixelSize: 8
                                                    font.weight: Font.DemiBold
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: analysisBridge.openSource(String(hypothesisRef.modelData))
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            Text {
                                visible: root.conclusionsFor("hypotheses").length === 0
                                width: parent.width
                                height: 120
                                text: root.run.runConfig && root.run.runConfig.mode === "quick"
                                    ? "Quick mode stops after the grounded summary."
                                    : "No hypotheses were produced."
                                color: Theme.textMuted
                                font.pixelSize: 10
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    // CONTRADICTIONS
                    Flickable {
                        clip: true
                        contentWidth: width
                        contentHeight: contradictionsContent.height
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        Column {
                            id: contradictionsContent
                            width: Math.min(parent.width - 28, 920)
                            x: Math.max(14, (parent.width - width) / 2)
                            spacing: 10

                            Text {
                                width: parent.width
                                height: 46
                                text: "Contradictions"
                                color: Theme.textPrimary
                                font.pixelSize: 21
                                font.weight: Font.DemiBold
                                verticalAlignment: Text.AlignVCenter
                            }

                            Text {
                                width: parent.width
                                text: "Conflicting or difficult-to-reconcile material. A contradiction can result from stale data, ambiguity or source error and does not itself imply deception."
                                color: Theme.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }

                            Repeater {
                                model: root.conclusionsFor("contradictions")
                                delegate: Rectangle {
                                    id: contradictionCard
                                    required property var modelData
                                    width: parent.width
                                    height: Math.max(170, contradictionText.implicitHeight + 75)
                                    radius: 10
                                    color: Theme.surface
                                    border.width: 1
                                    border.color: Theme.border

                                    Text {
                                        x: 14
                                        y: 13
                                        text: "CONFLICT REVIEW"
                                        color: Theme.warning
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: 0.9
                                    }

                                    Text {
                                        id: contradictionText
                                        x: 14
                                        y: 39
                                        width: parent.width - 28
                                        text: String(contradictionCard.modelData.text || "")
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        lineHeight: 1.45
                                        wrapMode: Text.Wrap
                                    }

                                    Flow {
                                        x: 14
                                        y: contradictionText.y + contradictionText.implicitHeight + 12
                                        width: parent.width - 28
                                        spacing: 6

                                        Repeater {
                                            model: contradictionCard.modelData.sourceReferences || []
                                            delegate: Rectangle {
                                                id: contradictionRef
                                                required property var modelData
                                                width: contradictionRefText.implicitWidth + 18
                                                height: 24
                                                radius: 12
                                                color: "#2b2415"
                                                border.width: 1
                                                border.color: Theme.warning
                                                Text {
                                                    id: contradictionRefText
                                                    anchors.centerIn: parent
                                                    text: String(contradictionRef.modelData)
                                                    color: Theme.warning
                                                    font.pixelSize: 8
                                                    font.weight: Font.DemiBold
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: analysisBridge.openSource(String(contradictionRef.modelData))
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            Text {
                                visible: root.conclusionsFor("contradictions").length === 0
                                width: parent.width
                                height: 120
                                text: root.run.runConfig && root.run.runConfig.mode === "quick"
                                    ? "Quick mode does not run contradiction analysis."
                                    : "No contradiction analysis was produced."
                                color: Theme.textMuted
                                font.pixelSize: 10
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    // NEXT STEPS
                    Flickable {
                        clip: true
                        contentWidth: width
                        contentHeight: nextStepsContent.height
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        Column {
                            id: nextStepsContent
                            width: Math.min(parent.width - 28, 920)
                            x: Math.max(14, (parent.width - width) / 2)
                            spacing: 10

                            Text {
                                width: parent.width
                                height: 46
                                text: "Next Steps"
                                color: Theme.textPrimary
                                font.pixelSize: 21
                                font.weight: Font.DemiBold
                                verticalAlignment: Text.AlignVCenter
                            }

                            Text {
                                width: parent.width
                                text: "Suggested investigative directions only. OSINTXZ does not execute these steps automatically."
                                color: Theme.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }

                            Repeater {
                                model: root.conclusionsFor("next_steps")
                                delegate: Rectangle {
                                    id: nextCard
                                    required property var modelData
                                    width: parent.width
                                    height: Math.max(170, nextText.implicitHeight + 75)
                                    radius: 10
                                    color: Theme.surface
                                    border.width: 1
                                    border.color: Theme.border

                                    Text {
                                        x: 14
                                        y: 13
                                        text: "ANALYST QUEUE"
                                        color: Theme.success
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: 0.9
                                    }

                                    Text {
                                        id: nextText
                                        x: 14
                                        y: 39
                                        width: parent.width - 28
                                        text: String(nextCard.modelData.text || "")
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        lineHeight: 1.45
                                        wrapMode: Text.Wrap
                                    }

                                    Flow {
                                        x: 14
                                        y: nextText.y + nextText.implicitHeight + 12
                                        width: parent.width - 28
                                        spacing: 6

                                        Repeater {
                                            model: nextCard.modelData.sourceReferences || []
                                            delegate: Rectangle {
                                                id: nextRef
                                                required property var modelData
                                                width: nextRefText.implicitWidth + 18
                                                height: 24
                                                radius: 12
                                                color: "#173127"
                                                border.width: 1
                                                border.color: Theme.success
                                                Text {
                                                    id: nextRefText
                                                    anchors.centerIn: parent
                                                    text: String(nextRef.modelData)
                                                    color: Theme.success
                                                    font.pixelSize: 8
                                                    font.weight: Font.DemiBold
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: analysisBridge.openSource(String(nextRef.modelData))
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            Text {
                                visible: root.conclusionsFor("next_steps").length === 0
                                width: parent.width
                                height: 120
                                text: root.run.runConfig && root.run.runConfig.mode !== "deep"
                                    ? "Next Steps are generated only in Deep mode."
                                    : "No next-step analysis was produced."
                                color: Theme.textMuted
                                font.pixelSize: 10
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    // SOURCES
                    Panel {
                        title: "RAG Sources"
                        subtitle: String(root.sources.length) + " bounded source(s) · click R# to open the underlying workspace"
                        iconSource: "../../assets/icons/document_blue.svg"

                        ListView {
                            anchors.fill: parent
                            clip: true
                            model: root.sources
                            boundsBehavior: Flickable.StopAtBounds

                            delegate: Rectangle {
                                id: sourceRow
                                required property var modelData
                                width: ListView.view.width
                                height: 72
                                color: sourceMouse.containsMouse ? Theme.surfaceHover : "transparent"

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    color: Theme.divider
                                }

                                Rectangle {
                                    x: 14
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 42
                                    height: 24
                                    radius: 12
                                    color: Theme.accentSoft
                                    Text {
                                        anchors.centerIn: parent
                                        text: String(sourceRow.modelData.reference || "R?")
                                        color: Theme.accent
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                    }
                                }

                                Text {
                                    x: 68
                                    y: 12
                                    width: parent.width - 205
                                    text: String(sourceRow.modelData.title || "Investigation source")
                                    color: Theme.textPrimary
                                    font.pixelSize: 10
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    x: 68
                                    y: 35
                                    width: parent.width - 205
                                    text: String(sourceRow.modelData.snippet || "")
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
                                }

                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 14
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 112
                                    horizontalAlignment: Text.AlignRight
                                    text: String(sourceRow.modelData.objectType || "object").toUpperCase()
                                        + "\n" + Number(sourceRow.modelData.score || 0).toFixed(3)
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                }

                                MouseArea {
                                    id: sourceMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: analysisBridge.openSource(String(sourceRow.modelData.reference || ""))
                                }
                            }

                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        }
                    }

                    // PIPELINE
                    Panel {
                        title: "Analysis Pipeline"
                        subtitle: "Deterministic investigation stages plus bounded RAG and AI generation"
                        iconSource: "../../assets/icons/graph_blue.svg"

                        ListView {
                            anchors.fill: parent
                            clip: true
                            model: root.stages
                            boundsBehavior: Flickable.StopAtBounds

                            delegate: Rectangle {
                                id: stageRow
                                required property var modelData
                                width: ListView.view.width
                                height: 50
                                color: "transparent"

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    color: Theme.divider
                                }

                                Rectangle {
                                    x: 14
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 8
                                    height: 8
                                    radius: 4
                                    color: root.statusColor(stageRow.modelData.status)
                                }

                                Text {
                                    x: 34
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - 240
                                    text: String(stageRow.modelData.label || stageRow.modelData.stage || "Stage")
                                    color: Theme.textPrimary
                                    font.pixelSize: 10
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                }

                                Text {
                                    anchors.right: statusText.left
                                    anchors.rightMargin: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Number(stageRow.modelData.durationSeconds || 0).toFixed(2) + "s"
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                }

                                Text {
                                    id: statusText
                                    anchors.right: parent.right
                                    anchors.rightMargin: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 90
                                    horizontalAlignment: Text.AlignRight
                                    text: String(stageRow.modelData.status || "").toUpperCase()
                                    color: root.statusColor(stageRow.modelData.status)
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
                                }
                            }

                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        }
                    }

                    // HISTORY
                    Panel {
                        title: "Analysis History"
                        subtitle: "Saved AIAnalysis runs for this investigation · never Evidence"
                        iconSource: "../../assets/icons/clock.svg"

                        ListView {
                            anchors.fill: parent
                            clip: true
                            model: root.historyRows
                            boundsBehavior: Flickable.StopAtBounds

                            delegate: Rectangle {
                                id: historyRow
                                required property var modelData
                                width: ListView.view.width
                                height: 72
                                color: historyMouse.containsMouse ? Theme.surfaceHover : "transparent"

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 1
                                    color: Theme.divider
                                }

                                Text {
                                    x: 14
                                    y: 11
                                    width: parent.width - 220
                                    text: String(historyRow.modelData.runConfig && historyRow.modelData.runConfig.modeLabel
                                        ? historyRow.modelData.runConfig.modeLabel
                                        : "Analysis")
                                        + " · "
                                        + String(historyRow.modelData.scope && historyRow.modelData.scope.label
                                            ? historyRow.modelData.scope.label
                                            : "Entire Investigation")
                                    color: Theme.textPrimary
                                    font.pixelSize: 10
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    x: 14
                                    y: 35
                                    width: parent.width - 220
                                    text: String(historyRow.modelData.question || "Standard investigation analysis")
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
                                }

                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 14
                                    y: 13
                                    width: 180
                                    horizontalAlignment: Text.AlignRight
                                    text: String(historyRow.modelData.cost && historyRow.modelData.cost.display
                                        ? historyRow.modelData.cost.display
                                        : "—")
                                        + " · "
                                        + String(historyRow.modelData.historyCreatedAt || "")
                                    color: Theme.accent
                                    font.pixelSize: 8
                                    elide: Text.ElideLeft
                                }

                                MouseArea {
                                    id: historyMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.openHistory(String(historyRow.modelData.historyId || ""))
                                }
                            }

                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: root.historyRows.length === 0
                            text: "No saved analysis runs yet."
                            color: Theme.textMuted
                            font.pixelSize: 10
                        }
                    }
                }
            }
        }
    }
}

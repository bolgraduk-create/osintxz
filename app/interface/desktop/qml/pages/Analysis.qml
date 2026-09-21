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

    function statusColor(status) {
        const value = String(status || "").toLowerCase()
        if (value === "success" || value === "completed") return Theme.success
        if (value === "partial" || value === "skipped") return Theme.warning
        if (value === "failed" || value === "cancelled") return Theme.danger
        if (value === "running") return Theme.accent
        return Theme.textMuted
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
            return ({ id: "", label: "Entire Investigation", type: "case" })
        return root.focusOptions[root.selectedFocusIndex]
    }

    function applyMode(key) {
        const info = root.modeInfo(key)
        root.selectedMode = String(info.key || key || "standard")
        if (info.recommendedModel)
            root.selectedModel = String(info.recommendedModel)
        if (info.recommendedReasoning)
            root.selectedReasoning = String(info.recommendedReasoning)
        modelBox.currentIndex = root.modelIndex(root.selectedModel)
        reasoningBox.currentIndex = root.reasoningIndex(root.selectedReasoning)
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
        anchors.leftMargin: Spacing.page
        anchors.rightMargin: Spacing.page
        anchors.topMargin: 14
        anchors.bottomMargin: 22
        spacing: 10

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 74

            Text {
                x: 2
                y: 0
                text: "ANALYSIS LAB"
                color: Theme.accent
                font.pixelSize: 9
                font.weight: Font.DemiBold
                font.letterSpacing: 1.8
            }

            Text {
                x: 2
                y: 18
                text: "AI Analysis"
                color: Theme.textPrimary
                font.pixelSize: Typography.pageTitle
                font.weight: Font.DemiBold
            }

            Text {
                x: 3
                y: 53
                width: parent.width - 390
                text: desktopBridge.hasCurrentCase
                    ? ("Structured reasoning over “" + String(desktopBridge.currentCaseTitle || "Investigation")
                        + "” · source-bound · provenance-first")
                    : "Select an investigation before running analysis."
                color: Theme.textSecondary
                font.pixelSize: 11
                elide: Text.ElideRight
            }

            Rectangle {
                anchors.right: parent.right
                anchors.top: parent.top
                width: 350
                height: 56
                radius: 8
                color: Theme.surface
                border.width: 1
                border.color: Boolean(root.provider.configured) ? Theme.border : Theme.danger

                Rectangle {
                    x: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: 8
                    height: 8
                    radius: 4
                    color: Boolean(root.provider.configured) ? Theme.success : Theme.danger
                }

                Text {
                    x: 30
                    y: 9
                    width: parent.width - 42
                    text: String(root.provider.label || "AI")
                        + " · " + String(root.provider.model || "No model")
                    color: Theme.textPrimary
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }

                Text {
                    x: 30
                    y: 31
                    width: parent.width - 42
                    text: Boolean(root.provider.configured)
                        ? ("Configured"
                            + (root.provider.reasoningEffort
                                ? " · reasoning " + String(root.provider.reasoningEffort)
                                : "")
                            + (root.provider.storeResponses === false
                                ? " · API storage off"
                                : ""))
                        : "Not configured — add OPENAI_API_KEY to .env"
                    color: Boolean(root.provider.configured) ? Theme.textMuted : Theme.danger
                    font.pixelSize: 9
                    elide: Text.ElideRight
                }
            }
        }

        Panel {
            Layout.fillWidth: true
            Layout.preferredHeight: 252
            title: "Analysis Focus"
            subtitle: "Choose analytical depth, scope and model before execution"
            iconSource: "../../assets/icons/search.svg"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 68
                    spacing: 8

                    Repeater {
                        model: root.modes()

                        delegate: Rectangle {
                            id: modeCard
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 7
                            color: String(root.selectedMode) === String(modeCard.modelData.key)
                                ? Theme.accentSoft
                                : Theme.background
                            border.width: 1
                            border.color: String(root.selectedMode) === String(modeCard.modelData.key)
                                ? Theme.accent
                                : Theme.border

                            Text {
                                x: 12
                                y: 10
                                text: String(modeCard.modelData.label || "")
                                color: String(root.selectedMode) === String(modeCard.modelData.key)
                                    ? Theme.accent
                                    : Theme.textPrimary
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }

                            Text {
                                x: 12
                                y: 30
                                width: parent.width - 24
                                text: String(modeCard.modelData.requests || 1)
                                    + " AI call" + (Number(modeCard.modelData.requests || 1) === 1 ? "" : "s")
                                    + " · " + String(modeCard.modelData.description || "")
                                color: Theme.textMuted
                                font.pixelSize: 8
                                elide: Text.ElideRight
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: !analysisBridge.busy
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.applyMode(String(modeCard.modelData.key || "standard"))
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 56
                    spacing: 10

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Text {
                            text: "SCOPE"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.letterSpacing: 1.0
                        }
                        AppComboBox {
                            id: scopeBox
                            Layout.fillWidth: true
                            model: root.focusLabels()
                            enabled: !analysisBridge.busy
                            onCurrentIndexChanged: root.selectedFocusIndex = currentIndex
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Text {
                            text: "MODEL"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.letterSpacing: 1.0
                        }
                        AppComboBox {
                            id: modelBox
                            Layout.fillWidth: true
                            model: root.modelLabels()
                            enabled: !analysisBridge.busy && String(root.provider.provider || "") === "openai"
                            onCurrentIndexChanged: {
                                const values = root.models()
                                if (currentIndex >= 0 && currentIndex < values.length)
                                    root.selectedModel = String(values[currentIndex].id || root.selectedModel)
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.preferredWidth: 190
                        spacing: 4
                        Text {
                            text: "REASONING"
                            color: Theme.textMuted
                            font.pixelSize: 8
                            font.letterSpacing: 1.0
                        }
                        AppComboBox {
                            id: reasoningBox
                            Layout.fillWidth: true
                            model: root.reasoningEfforts()
                            enabled: !analysisBridge.busy && String(root.provider.provider || "") === "openai"
                            onCurrentIndexChanged: {
                                const values = root.reasoningEfforts()
                                if (currentIndex >= 0 && currentIndex < values.length)
                                    root.selectedReasoning = String(values[currentIndex])
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 10

                    TextArea {
                        id: questionInput
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        placeholderText: "Optional analyst question. Leave blank for the standard investigation question."
                        wrapMode: TextEdit.Wrap
                        color: Theme.textPrimary
                        placeholderTextColor: Theme.textMuted
                        selectionColor: Theme.accent
                        selectedTextColor: "#ffffff"
                        font.pixelSize: 10
                        enabled: !analysisBridge.busy
                        background: Rectangle {
                            radius: 7
                            color: Theme.background
                            border.width: 1
                            border.color: questionInput.activeFocus ? Theme.accent : Theme.border
                        }
                    }

                    ColumnLayout {
                        Layout.preferredWidth: 170
                        Layout.fillHeight: true
                        spacing: 8

                        AppButton {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            text: analysisBridge.busy ? "Analyzing…" : "Run Analysis"
                            primary: true
                            enabled: !analysisBridge.busy
                                && desktopBridge.hasCurrentCase
                                && Boolean(root.provider.configured)
                            onClicked: root.runAnalysisNow()
                        }

                        AppButton {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 34
                            text: "Clear result"
                            enabled: !analysisBridge.busy && Boolean(root.run.hasRun)
                            onClicked: analysisBridge.clear()
                        }

                        Text {
                            Layout.fillWidth: true
                            text: "AI output is analysis, not Evidence."
                            color: Theme.textMuted
                            font.pixelSize: 8
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: analysisBridge.busy || Boolean(root.run.hasRun) ? 66 : 0
            visible: analysisBridge.busy || Boolean(root.run.hasRun)
            radius: 8
            color: Theme.surface
            border.width: 1
            border.color: analysisBridge.busy ? Theme.accent : Theme.border

            ProgressBar {
                id: progressBar
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.right: statusBadge.left
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                from: 0
                to: 1
                value: Number(root.run.progress || (root.run.status === "success" ? 1 : 0))
            }

            Text {
                anchors.left: progressBar.left
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
                width: progressBar.width
                text: String(root.run.progressText || root.run.status || "")
                    + (root.run.currentStageLabel
                        ? " · " + String(root.run.currentStageLabel)
                        : "")
                color: Theme.textMuted
                font.pixelSize: 8
                elide: Text.ElideRight
            }

            Rectangle {
                id: statusBadge
                anchors.right: parent.right
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                width: 116
                height: 30
                radius: 15
                color: "transparent"
                border.width: 1
                border.color: root.statusColor(root.run.status || (analysisBridge.busy ? "running" : ""))

                Text {
                    anchors.centerIn: parent
                    text: String(root.run.status || (analysisBridge.busy ? "RUNNING" : "—")).toUpperCase()
                    color: root.statusColor(root.run.status || (analysisBridge.busy ? "running" : ""))
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            Rectangle {
                Layout.preferredWidth: 176
                Layout.fillHeight: true
                radius: 8
                color: Theme.surface
                border.width: 1
                border.color: Theme.border

                Column {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4

                    Text {
                        width: parent.width
                        height: 30
                        text: "ANALYTIC LAYERS"
                        color: Theme.textMuted
                        font.pixelSize: 8
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.1
                        verticalAlignment: Text.AlignVCenter
                    }

                    Repeater {
                        model: [
                            {key:"overview", label:"Overview"},
                            {key:"facts", label:"Facts"},
                            {key:"hypotheses", label:"Hypotheses"},
                            {key:"contradictions", label:"Contradictions"},
                            {key:"next_steps", label:"Next Steps"},
                            {key:"sources", label:"Sources"},
                            {key:"pipeline", label:"Pipeline"},
                            {key:"history", label:"History"}
                        ]

                        delegate: Rectangle {
                            id: navRow
                            required property var modelData
                            width: parent.width
                            height: 38
                            radius: 6
                            color: String(root.activeView) === String(navRow.modelData.key)
                                ? Theme.accentSoft
                                : "transparent"

                            Rectangle {
                                visible: String(root.activeView) === String(navRow.modelData.key)
                                width: 3
                                height: 20
                                radius: 2
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                color: Theme.accent
                            }

                            Text {
                                x: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: String(navRow.modelData.label)
                                color: String(root.activeView) === String(navRow.modelData.key)
                                    ? Theme.textPrimary
                                    : Theme.textSecondary
                                font.pixelSize: 10
                                font.weight: String(root.activeView) === String(navRow.modelData.key)
                                    ? Font.DemiBold
                                    : Font.Normal
                            }

                            Rectangle {
                                visible: root.navCount(String(navRow.modelData.key)) > 0
                                anchors.right: parent.right
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.max(24, countText.implicitWidth + 10)
                                height: 20
                                radius: 10
                                color: Theme.background

                                Text {
                                    id: countText
                                    anchors.centerIn: parent
                                    text: String(root.navCount(String(navRow.modelData.key)))
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.activeView = String(navRow.modelData.key)
                            }
                        }
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Theme.divider
                    }

                    Text {
                        width: parent.width
                        text: root.run.runConfig
                            ? (String(root.run.runConfig.modeLabel || "").toUpperCase()
                                + "\n" + String(root.run.runConfig.model || "")
                                + "\n" + String(root.run.runConfig.reasoningEffort || "").toUpperCase())
                            : "NO ACTIVE RUN"
                        color: Theme.textMuted
                        font.pixelSize: 8
                        lineHeight: 1.35
                        wrapMode: Text.Wrap
                    }
                }
            }

            StackLayout {
                id: views
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: {
                    const keys = ["overview","facts","hypotheses","contradictions","next_steps","sources","pipeline","history"]
                    const idx = keys.indexOf(root.activeView)
                    return idx >= 0 ? idx : 0
                }

                // OVERVIEW
                Flickable {
                    clip: true
                    contentWidth: width
                    contentHeight: overviewColumn.height
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    Column {
                        id: overviewColumn
                        width: parent.width
                        spacing: 10

                        Item {
                            width: parent.width
                            height: Boolean(root.run.hasRun) ? 86 : 170

                            Text {
                                anchors.centerIn: parent
                                visible: !Boolean(root.run.hasRun)
                                width: Math.min(parent.width - 80, 680)
                                text: desktopBridge.hasCurrentCase
                                    ? "Ready. Choose scope and analytical depth, then run the case through the deterministic analysis pipeline and bounded RAG."
                                    : "Select an investigation to enable Analysis."
                                color: Theme.textMuted
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                                horizontalAlignment: Text.AlignHCenter
                            }

                            Row {
                                visible: Boolean(root.run.hasRun)
                                width: parent.width
                                height: 86
                                spacing: 8

                                Repeater {
                                    model: [
                                        {label:"SOURCES", value: root.sources.length},
                                        {label:"FACTS", value: root.facts.length},
                                        {label:"VALID REFS", value: root.citationSummary.valid || 0},
                                        {label:"AI CALLS", value: root.run.usage ? (root.run.usage.requests || 0) : 0},
                                        {label:"EST. COST", value: root.run.cost ? (root.run.cost.display || "—") : "—"}
                                    ]

                                    delegate: Rectangle {
                                        id: metric
                                        required property var modelData
                                        width: (overviewColumn.width - 32) / 5
                                        height: 86
                                        radius: 8
                                        color: Theme.surface
                                        border.width: 1
                                        border.color: Theme.border

                                        Text {
                                            x: 12
                                            y: 12
                                            width: parent.width - 24
                                            text: String(metric.modelData.label)
                                            color: Theme.textMuted
                                            font.pixelSize: 8
                                            font.letterSpacing: 0.8
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            x: 12
                                            y: 39
                                            width: parent.width - 24
                                            text: String(metric.modelData.value)
                                            color: Theme.textPrimary
                                            font.pixelSize: 20
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                    }
                                }
                            }
                        }

                        Panel {
                            visible: Boolean(root.run.hasRun)
                            width: overviewColumn.width
                            height: Math.min(520, Math.max(230, summaryText.implicitHeight + 118))
                            title: "AI Summary"
                            subtitle: String(root.run.scope && root.run.scope.label ? root.run.scope.label : "Entire Investigation")
                                + " · "
                                + String(root.run.runConfig && root.run.runConfig.modeLabel ? root.run.runConfig.modeLabel : "Analysis")
                            iconSource: "../../assets/icons/chart.svg"

                            Flickable {
                                anchors.fill: parent
                                anchors.margins: 16
                                clip: true
                                contentWidth: width
                                contentHeight: summaryText.implicitHeight + 42
                                boundsBehavior: Flickable.StopAtBounds

                                Column {
                                    width: parent.width
                                    spacing: 10

                                    Text {
                                        id: summaryText
                                        width: parent.width
                                        text: String(root.run.summary || "No AI summary was produced.")
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        lineHeight: 1.45
                                        wrapMode: Text.Wrap
                                        textFormat: Text.PlainText
                                    }

                                    Flow {
                                        width: parent.width
                                        spacing: 6

                                        Repeater {
                                            model: root.sourceRefsForSummary()
                                            delegate: Rectangle {
                                                id: summaryRef
                                                required property var modelData
                                                width: refText.implicitWidth + 18
                                                height: 26
                                                radius: 13
                                                color: Theme.accentSoft
                                                border.width: 1
                                                border.color: Theme.accent

                                                Text {
                                                    id: refText
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

                                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            }
                        }

                        Panel {
                            visible: Boolean(root.run.hasRun)
                            width: overviewColumn.width
                            height: 174
                            title: "Run Telemetry"
                            subtitle: "Actual provider-reported usage · cost is approximate"
                            iconSource: "../../assets/icons/chart.svg"

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 8

                                Repeater {
                                    model: [
                                        {label:"INPUT", value: root.run.usage ? (root.run.usage.inputTokens || 0) : 0},
                                        {label:"CACHED", value: root.run.usage ? (root.run.usage.cachedInputTokens || 0) : 0},
                                        {label:"OUTPUT", value: root.run.usage ? (root.run.usage.outputTokens || 0) : 0},
                                        {label:"REASONING", value: root.run.usage ? (root.run.usage.reasoningTokens || 0) : 0}
                                    ]
                                    delegate: Rectangle {
                                        id: tokenMetric
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        radius: 7
                                        color: Theme.background
                                        border.width: 1
                                        border.color: Theme.border

                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            y: 23
                                            text: String(tokenMetric.modelData.value)
                                            color: Theme.textPrimary
                                            font.pixelSize: 18
                                            font.weight: Font.DemiBold
                                        }
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            y: 52
                                            text: String(tokenMetric.modelData.label)
                                            color: Theme.textMuted
                                            font.pixelSize: 8
                                            font.letterSpacing: 0.7
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.preferredWidth: 230
                                    Layout.fillHeight: true
                                    radius: 7
                                    color: Theme.background
                                    border.width: 1
                                    border.color: Theme.border

                                    Text {
                                        x: 12
                                        y: 13
                                        text: "ESTIMATED API COST"
                                        color: Theme.textMuted
                                        font.pixelSize: 8
                                        font.letterSpacing: 0.7
                                    }
                                    Text {
                                        x: 12
                                        y: 40
                                        text: root.run.cost ? String(root.run.cost.display || "—") : "—"
                                        color: Theme.accent
                                        font.pixelSize: 20
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        x: 12
                                        y: 72
                                        width: parent.width - 24
                                        text: root.run.cost
                                            ? ("pricing " + String(root.run.cost.pricingEffectiveDate || root.catalog.pricingEffectiveDate || "")
                                                + " · " + String(root.run.cost.notice || "approximate"))
                                            : ""
                                        color: Theme.textMuted
                                        font.pixelSize: 8
                                        wrapMode: Text.Wrap
                                    }
                                }
                            }
                        }

                        Rectangle {
                            visible: Boolean(root.run.hasRun)
                            width: overviewColumn.width
                            height: root.run.redactions && root.run.redactions.active ? 82 : 64
                            radius: 8
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.border

                            Text {
                                anchors.fill: parent
                                anchors.margins: 14
                                text: String(root.run.notice || "AI-generated analysis is analytical assistance, not Evidence or an independently verified fact.")
                                    + (root.run.redactions && root.run.redactions.active
                                        ? ("\n\nSECURITY · " + String(root.run.redactions.count || 0)
                                            + " credential/secret fragment(s) were redacted before display and history.")
                                        : "")
                                color: Theme.textMuted
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                // FACTS
                Flickable {
                    clip: true
                    contentWidth: width
                    contentHeight: factsColumn.height
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    Column {
                        id: factsColumn
                        width: parent.width
                        spacing: 8

                        Text {
                            width: parent.width
                            height: 42
                            text: "FACTS · SOURCE-BACKED OBSERVATIONS"
                            color: Theme.textPrimary
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            verticalAlignment: Text.AlignVCenter
                        }

                        Text {
                            width: parent.width
                            text: "These rows come directly from bounded RAG source material. They are separated from AI hypotheses, but are not automatically independently verified."
                            color: Theme.textMuted
                            font.pixelSize: 9
                            wrapMode: Text.Wrap
                        }

                        Repeater {
                            model: root.facts
                            delegate: Rectangle {
                                id: factRow
                                required property var modelData
                                width: factsColumn.width
                                height: Math.max(104, factText.implicitHeight + 56)
                                radius: 8
                                color: Theme.surface
                                border.width: 1
                                border.color: Theme.border

                                Rectangle {
                                    x: 12
                                    y: 12
                                    width: 42
                                    height: 24
                                    radius: 12
                                    color: Theme.background
                                    border.width: 1
                                    border.color: Theme.accent
                                    Text {
                                        anchors.centerIn: parent
                                        text: String(factRow.modelData.reference || "R?")
                                        color: Theme.accent
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: analysisBridge.openSource(String(factRow.modelData.reference || ""))
                                    }
                                }

                                Text {
                                    x: 64
                                    y: 13
                                    width: parent.width - 78
                                    text: String(factRow.modelData.title || "Source observation")
                                    color: Theme.textPrimary
                                    font.pixelSize: 10
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    id: factText
                                    x: 14
                                    y: 46
                                    width: parent.width - 28
                                    text: String(factRow.modelData.text || "No source text.")
                                    color: Theme.textSecondary
                                    font.pixelSize: 10
                                    lineHeight: 1.35
                                    wrapMode: Text.Wrap
                                }
                            }
                        }
                    }
                }

                // HYPOTHESES
                Flickable {
                    clip: true
                    contentWidth: width
                    contentHeight: hypothesisColumn.height
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    Column {
                        id: hypothesisColumn
                        width: parent.width
                        spacing: 10

                        Panel {
                            width: hypothesisColumn.width
                            height: 150
                            title: "Hypotheses"
                            subtitle: "AI inference · must be tested against evidence"
                            iconSource: "../../assets/icons/search.svg"

                            Text {
                                anchors.fill: parent
                                anchors.margins: 16
                                text: "Hypotheses are candidate explanations generated from the bounded source set. They are not identity claims, facts, or Evidence until independently supported."
                                color: Theme.textSecondary
                                font.pixelSize: 10
                                wrapMode: Text.Wrap
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Repeater {
                            model: root.conclusionsFor("hypotheses")
                            delegate: Panel {
                                id: hypothesisPanel
                                required property var modelData
                                width: hypothesisColumn.width
                                height: Math.min(500, Math.max(220, hypothesisText.implicitHeight + 125))
                                title: "Hypothesis Analysis"
                                subtitle: String(hypothesisPanel.modelData.workflow || "hypothesis_generation")
                                iconSource: "../../assets/icons/search.svg"

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 10

                                    Text {
                                        id: hypothesisText
                                        width: parent.width
                                        text: String(hypothesisPanel.modelData.text || "")
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        lineHeight: 1.45
                                        wrapMode: Text.Wrap
                                    }

                                    Flow {
                                        width: parent.width
                                        spacing: 6
                                        Repeater {
                                            model: hypothesisPanel.modelData.sourceReferences || []
                                            delegate: Rectangle {
                                                id: hRef
                                                required property var modelData
                                                width: hRefText.implicitWidth + 18
                                                height: 25
                                                radius: 12
                                                color: Theme.accentSoft
                                                Text {
                                                    id: hRefText
                                                    anchors.centerIn: parent
                                                    text: String(hRef.modelData)
                                                    color: Theme.accent
                                                    font.pixelSize: 8
                                                    font.weight: Font.DemiBold
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: analysisBridge.openSource(String(hRef.modelData))
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            visible: root.conclusionsFor("hypotheses").length === 0
                            width: parent.width
                            height: 90
                            text: root.run.runConfig && root.run.runConfig.mode === "quick"
                                ? "Quick mode intentionally does not generate hypotheses."
                                : "No hypotheses were produced."
                            color: Theme.textMuted
                            font.pixelSize: 11
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                // CONTRADICTIONS
                Flickable {
                    clip: true
                    contentWidth: width
                    contentHeight: contradictionColumn.height
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    Column {
                        id: contradictionColumn
                        width: parent.width
                        spacing: 10

                        Panel {
                            width: contradictionColumn.width
                            height: 150
                            title: "Contradictions"
                            subtitle: "Conflict review · inconsistency does not imply deception"
                            iconSource: "../../assets/icons/chart.svg"

                            Text {
                                anchors.fill: parent
                                anchors.margins: 16
                                text: "This layer highlights conflicting or difficult-to-reconcile source material. A contradiction can come from stale data, source error, ambiguity, or genuine conflict."
                                color: Theme.textSecondary
                                font.pixelSize: 10
                                wrapMode: Text.Wrap
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Repeater {
                            model: root.conclusionsFor("contradictions")
                            delegate: Panel {
                                id: contradictionPanel
                                required property var modelData
                                width: contradictionColumn.width
                                height: Math.min(500, Math.max(220, contradictionText.implicitHeight + 125))
                                title: "Contradiction Analysis"
                                subtitle: String(contradictionPanel.modelData.workflow || "contradiction_analysis")
                                iconSource: "../../assets/icons/chart.svg"

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 10
                                    Text {
                                        id: contradictionText
                                        width: parent.width
                                        text: String(contradictionPanel.modelData.text || "")
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        lineHeight: 1.45
                                        wrapMode: Text.Wrap
                                    }
                                    Flow {
                                        width: parent.width
                                        spacing: 6
                                        Repeater {
                                            model: contradictionPanel.modelData.sourceReferences || []
                                            delegate: Rectangle {
                                                id: cRef
                                                required property var modelData
                                                width: cRefText.implicitWidth + 18
                                                height: 25
                                                radius: 12
                                                color: Theme.background
                                                border.width: 1
                                                border.color: Theme.warning
                                                Text {
                                                    id: cRefText
                                                    anchors.centerIn: parent
                                                    text: String(cRef.modelData)
                                                    color: Theme.warning
                                                    font.pixelSize: 8
                                                    font.weight: Font.DemiBold
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: analysisBridge.openSource(String(cRef.modelData))
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            visible: root.conclusionsFor("contradictions").length === 0
                            width: parent.width
                            height: 90
                            text: root.run.runConfig && root.run.runConfig.mode === "quick"
                                ? "Quick mode intentionally does not run contradiction analysis."
                                : "No contradiction analysis was produced."
                            color: Theme.textMuted
                            font.pixelSize: 11
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                // NEXT STEPS
                Flickable {
                    clip: true
                    contentWidth: width
                    contentHeight: nextStepsColumn.height
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    Column {
                        id: nextStepsColumn
                        width: parent.width
                        spacing: 10

                        Panel {
                            width: nextStepsColumn.width
                            height: 150
                            title: "Next Investigation Steps"
                            subtitle: "Analytical suggestions · no automatic execution"
                            iconSource: "../../assets/icons/search.svg"

                            Text {
                                anchors.fill: parent
                                anchors.margins: 16
                                text: "Suggested next steps are an analyst queue only. OSINTXZ does not automatically execute them, modify Evidence, or assert that they are necessary."
                                color: Theme.textSecondary
                                font.pixelSize: 10
                                wrapMode: Text.Wrap
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Repeater {
                            model: root.conclusionsFor("next_steps")
                            delegate: Panel {
                                id: nextPanel
                                required property var modelData
                                width: nextStepsColumn.width
                                height: Math.min(500, Math.max(220, nextText.implicitHeight + 125))
                                title: "Next Steps"
                                subtitle: String(nextPanel.modelData.workflow || "next_investigation_steps")
                                iconSource: "../../assets/icons/search.svg"

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 16
                                    spacing: 10
                                    Text {
                                        id: nextText
                                        width: parent.width
                                        text: String(nextPanel.modelData.text || "")
                                        color: Theme.textPrimary
                                        font.pixelSize: 11
                                        lineHeight: 1.45
                                        wrapMode: Text.Wrap
                                    }
                                    Flow {
                                        width: parent.width
                                        spacing: 6
                                        Repeater {
                                            model: nextPanel.modelData.sourceReferences || []
                                            delegate: Rectangle {
                                                id: nRef
                                                required property var modelData
                                                width: nRefText.implicitWidth + 18
                                                height: 25
                                                radius: 12
                                                color: Theme.accentSoft
                                                Text {
                                                    id: nRefText
                                                    anchors.centerIn: parent
                                                    text: String(nRef.modelData)
                                                    color: Theme.accent
                                                    font.pixelSize: 8
                                                    font.weight: Font.DemiBold
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: analysisBridge.openSource(String(nRef.modelData))
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            visible: root.conclusionsFor("next_steps").length === 0
                            width: parent.width
                            height: 90
                            text: root.run.runConfig && root.run.runConfig.mode !== "deep"
                                ? "Next Steps are generated only in Deep mode."
                                : "No next-step analysis was produced."
                            color: Theme.textMuted
                            font.pixelSize: 11
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                // SOURCES
                Item {
                    Panel {
                        anchors.fill: parent
                        title: "RAG Sources"
                        subtitle: String(root.sources.length)
                            + " bounded investigation source(s) supplied to the AI context · click R# to navigate"
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
                                height: Math.max(72, sourceSnippet.implicitHeight + 49)
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
                                    y: 12
                                    width: 44
                                    height: 26
                                    radius: 13
                                    color: Theme.accentSoft
                                    border.width: 1
                                    border.color: Theme.accent
                                    Text {
                                        anchors.centerIn: parent
                                        text: String(sourceRow.modelData.reference || "R?")
                                        color: Theme.accent
                                        font.pixelSize: 8
                                        font.weight: Font.DemiBold
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: analysisBridge.openSource(String(sourceRow.modelData.reference || ""))
                                    }
                                }

                                Text {
                                    x: 70
                                    y: 10
                                    width: parent.width - 190
                                    text: String(sourceRow.modelData.title || "Investigation source")
                                    color: Theme.textPrimary
                                    font.pixelSize: 10
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    id: sourceSnippet
                                    x: 70
                                    y: 31
                                    width: parent.width - 190
                                    text: String(sourceRow.modelData.snippet || "")
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                    wrapMode: Text.Wrap
                                }

                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 16
                                    y: 11
                                    width: 105
                                    horizontalAlignment: Text.AlignRight
                                    text: String(sourceRow.modelData.objectType || "object").toUpperCase()
                                    color: Theme.textSecondary
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
                                }

                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 16
                                    y: 33
                                    width: 105
                                    horizontalAlignment: Text.AlignRight
                                    text: "score " + Number(sourceRow.modelData.score || 0).toFixed(3)
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                }
                            }

                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                        }
                    }
                }

                // PIPELINE
                Item {
                    Panel {
                        anchors.fill: parent
                        title: "Analysis Pipeline"
                        subtitle: "Canonical deterministic stages plus bounded RAG / AI generation"
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
                                height: 54
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
                                    width: parent.width - 250
                                    text: String(stageRow.modelData.label || stageRow.modelData.stage || "Stage")
                                    color: Theme.textPrimary
                                    font.pixelSize: 10
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                }

                                Text {
                                    anchors.right: stageStatus.left
                                    anchors.rightMargin: 18
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Number(stageRow.modelData.durationSeconds || 0).toFixed(2) + "s"
                                    color: Theme.textMuted
                                    font.pixelSize: 9
                                }

                                Text {
                                    id: stageStatus
                                    anchors.right: parent.right
                                    anchors.rightMargin: 16
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 92
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
                }

                // HISTORY
                Item {
                    Panel {
                        anchors.fill: parent
                        title: "Analysis History"
                        subtitle: "Saved AIAnalysis runs for the selected investigation · never Evidence"
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
                                height: 76
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
                                    y: 10
                                    width: parent.width - 210
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
                                    y: 33
                                    width: parent.width - 210
                                    text: String(historyRow.modelData.question || "Standard investigation analysis")
                                        + " · "
                                        + String(historyRow.modelData.runConfig && historyRow.modelData.runConfig.model
                                            ? historyRow.modelData.runConfig.model
                                            : historyRow.modelData.historyModel || "")
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
                                }

                                Text {
                                    x: 14
                                    y: 52
                                    width: parent.width - 210
                                    text: String(historyRow.modelData.historyCreatedAt || "")
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    elide: Text.ElideRight
                                }

                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 16
                                    y: 15
                                    width: 170
                                    horizontalAlignment: Text.AlignRight
                                    text: String(historyRow.modelData.cost && historyRow.modelData.cost.display
                                        ? historyRow.modelData.cost.display
                                        : "—")
                                        + " · "
                                        + String(historyRow.modelData.usage && historyRow.modelData.usage.requests
                                            ? historyRow.modelData.usage.requests + " calls"
                                            : "no usage")
                                    color: Theme.accent
                                    font.pixelSize: 9
                                }

                                Text {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 16
                                    y: 40
                                    width: 170
                                    horizontalAlignment: Text.AlignRight
                                    text: "OPEN"
                                    color: Theme.textSecondary
                                    font.pixelSize: 8
                                    font.weight: Font.DemiBold
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
                            text: "No Analysis Workspace history for this investigation yet."
                            color: Theme.textMuted
                            font.pixelSize: 10
                        }
                    }
                }
            }
        }
    }
}

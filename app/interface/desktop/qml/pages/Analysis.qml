pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../theme"

Item {
    id: root
    // Legacy contract: placeholderText: "Ask what you want to understand about this investigation..."
    // Legacy run contract: desktopBridge.hasCurrentCase ? "Run Analysis" : "Select Case"

    property var run: analysisBridge.runData || ({})
    property var provider: analysisBridge.providerInfo || ({})
    property var providerOptions: analysisBridge.providerCatalog || []
    property var catalog: analysisBridge.catalog || ({})
    property var focusOptions: analysisBridge.focusOptions || []
    property var historyRows: analysisBridge.history || []
    property var chatMessages: analysisBridge.chatMessages || []
    property var stages: run.stages || []
    property var conclusions: run.conclusions || []
    property var facts: run.facts || []
    property var sources: run.sources || []
    property var explainability: run.explainability || []
    property var warnings: run.warnings || []
    property bool whyDrawerOpen: false
    property var whyExplanations: []
    property string whyTitle: "Explainability"
    property var citationSummary: run.citationSummary || ({})
    property string selectedMode: "standard"
    property string selectedProvider: ""
    property string selectedModel: "gpt-5.6-terra"
    property string selectedReasoning: "medium"
    property int selectedFocusIndex: 0
    property string activeView: "assistant"
    property string preparedCaseId: ""

    readonly property var layerItems: [
        {key:"assistant", label:"Assistant", icon:"search.svg"},
        {key:"overview", label:"Overview", icon:"chart.svg"},
        {key:"facts", label:"Facts", icon:"document_blue.svg"},
        {key:"hypotheses", label:"Hypotheses", icon:"search.svg"},
        {key:"contradictions", label:"Contradictions", icon:"chart.svg"},
        {key:"next_steps", label:"Next Steps", icon:"search.svg"},
        {key:"sources", label:"Sources", icon:"document_blue.svg"},
        {key:"explainability", label:"Why", icon:"search.svg"},
        {key:"pipeline", label:"Pipeline", icon:"graph_blue.svg"},
        {key:"history", label:"History", icon:"clock.svg"}
    ]

    function reload() {
        root.run = analysisBridge.runData || ({})
        root.provider = analysisBridge.providerInfo || ({})
        root.providerOptions = analysisBridge.providerCatalog || []
        root.catalog = analysisBridge.catalog || ({})
        root.focusOptions = analysisBridge.focusOptions || []
        root.historyRows = analysisBridge.history || []
        root.chatMessages = analysisBridge.chatMessages || []
        root.stages = root.run.stages || []
        root.conclusions = root.run.conclusions || []
        root.facts = root.run.facts || []
        root.sources = root.run.sources || []
        root.explainability = root.run.explainability || []
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

    function providers() {
        return root.providerOptions || []
    }

    function providerInfoById(providerId) {
        const values = root.providers()
        for (let i = 0; i < values.length; ++i) {
            if (String(values[i].provider || "") === String(providerId || ""))
                return values[i]
        }
        return ({})
    }

    function selectedProviderInfo() {
        const info = root.providerInfoById(root.selectedProvider)
        if (String(info.provider || "") !== "")
            return info
        return root.provider || ({})
    }

    function providerLabels() {
        const values = root.providers()
        const out = []
        for (let i = 0; i < values.length; ++i) {
            const item = values[i]
            let suffix = ""
            if (String(item.provider || "") === "openai") {
                if (!Boolean(item.configured))
                    suffix = " · API key missing"
                else if (root.providerRuntimeStatusText(item))
                    suffix = " · " + root.providerRuntimeStatusText(item)
            } else if (String(item.provider || "") === "ollama") {
                if (String(item.status || "") === "online_no_models")
                    suffix = " · no installed models"
                else if (item.online === true)
                    suffix = " · online"
                else if (item.online === false)
                    suffix = " · offline"
                else
                    suffix = " · checking"
            }
            out.push(String(item.label || item.provider || "AI") + suffix)
        }
        return out
    }

    function providerIndex(providerId) {
        const values = root.providers()
        for (let i = 0; i < values.length; ++i) {
            if (String(values[i].provider || "") === String(providerId || ""))
                return i
        }
        return 0
    }

    function selectedProviderReady() {
        const info = root.selectedProviderInfo()
        if (!Boolean(info.configured))
            return false
        if (String(info.provider || "") === "ollama")
            return info.online === true && root.models().length > 0
        return root.models().length > 0
    }

    function ollamaReady() {
        const info = root.providerInfoById("ollama")
        return Boolean(info.configured)
            && info.online === true
            && (info.models || []).length > 0
    }

    function providerHasRuntimeError(info) {
        const status = String((info || {}).status || "")
        return status === "quota_exhausted"
            || status === "authentication"
            || status === "permission"
    }

    function providerRuntimeStatusText(info) {
        const status = String((info || {}).status || "")
        if (status === "quota_exhausted") return "credits exhausted"
        if (status === "authentication") return "API key error"
        if (status === "permission") return "access denied"
        return ""
    }

    function recoverWithOllama(messageData) {
        if (!root.ollamaReady()) {
            analysisBridge.refreshProviders()
            return
        }
        root.applyProvider("ollama")
        questionInput.text = String((messageData || {}).userMessage || "")
        questionInput.forceActiveFocus()
    }

    function models() {
        const info = root.selectedProviderInfo()
        return info.models || []
    }

    function reasoningEfforts() {
        if (String(root.selectedProvider || "") !== "openai")
            return ["Local provider"]
        const info = root.selectedProviderInfo()
        return info.reasoningEfforts || root.catalog.reasoningEfforts || ["none", "low", "medium", "high", "xhigh", "max"]
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
        for (let i = 0; i < values.length; ++i) {
            const label = String(values[i].label || values[i].id || "Model")
            const tier = String(values[i].tier || "")
            out.push(tier ? label + " · " + tier : label)
        }
        if (out.length === 0)
            return [String(root.provider.model || "Local model")]
        return out
    }

    function modelIndex(modelId) {
        const values = root.models()
        for (let i = 0; i < values.length; ++i) {
            if (String(values[i].id || "") === String(modelId || ""))
                return i
        }
        return 0
    }

    function modelIdAt(index) {
        const values = root.models()
        if (index >= 0 && index < values.length)
            return String(values[index].id || "")
        return ""
    }

    function reasoningIndex(value) {
        const values = root.reasoningEfforts()
        for (let i = 0; i < values.length; ++i) {
            if (String(values[i]) === String(value))
                return i
        }
        return 0
    }

    function applyProvider(providerId) {
        const normalized = String(providerId || root.provider.provider || "ollama")
        root.selectedProvider = normalized
        const info = root.selectedProviderInfo()
        const values = root.models()
        const mode = root.modeInfo(root.selectedMode)

        if (normalized === "openai") {
            let wanted = String(mode.recommendedModel || info.defaultModel || info.model || "")
            let found = false
            for (let i = 0; i < values.length; ++i) {
                if (String(values[i].id || "") === wanted) {
                    found = true
                    break
                }
            }
            if (!found)
                wanted = String(info.defaultModel || (values.length ? values[0].id : "gpt-5.6"))
            root.selectedModel = wanted
            root.selectedReasoning = String(mode.recommendedReasoning || info.reasoningEffort || "medium")
        } else {
            root.selectedModel = String(info.defaultModel || info.model || (values.length ? values[0].id : ""))
            root.selectedReasoning = ""
        }

        providerBox.currentIndex = root.providerIndex(root.selectedProvider)
        modelBox.currentIndex = root.modelIndex(root.selectedModel)
        reasoningBox.currentIndex = root.reasoningIndex(root.selectedReasoning)
    }

    function ensureProviderSelection() {
        if (!root.selectedProvider)
            root.selectedProvider = String(root.provider.provider || "ollama")

        const info = root.selectedProviderInfo()
        const values = root.models()
        let exists = false
        for (let i = 0; i < values.length; ++i) {
            if (String(values[i].id || "") === String(root.selectedModel || "")) {
                exists = true
                break
            }
        }
        if (!exists) {
            root.selectedModel = String(info.defaultModel || info.model || (values.length ? values[0].id : ""))
            modelBox.currentIndex = root.modelIndex(root.selectedModel)
        }
    }

    function focusLabels() {
        const out = []
        for (let i = 0; i < root.focusOptions.length; ++i)
            out.push(String(root.focusOptions[i].label || "Unknown"))
        if (out.length === 0)
            out.push(desktopBridge.hasCurrentCase ? "Entire Investigation" : "Select an investigation")
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
        if (String(root.selectedProvider || "") === "openai") {
            if (info.recommendedModel)
                root.selectedModel = String(info.recommendedModel)
            if (info.recommendedReasoning)
                root.selectedReasoning = String(info.recommendedReasoning)
        } else {
            const providerInfo = root.selectedProviderInfo()
            root.selectedModel = String(providerInfo.defaultModel || providerInfo.model || root.selectedModel || "")
            root.selectedReasoning = ""
        }
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
        if (key === "explainability") return root.explainability.length
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

    function hasUnitScore(value) {
        if (value === null || value === undefined || value === "")
            return false
        const numeric = Number(value)
        return isFinite(numeric) && numeric >= 0 && numeric <= 1
    }

    function hasEvidenceConfidence(item) {
        return item
            && root.hasUnitScore(item.evidenceConfidence)
    }

    function scorePercent(value) {
        if (!root.hasUnitScore(value))
            return "—"
        return String(Math.round(Number(value) * 100)) + "%"
    }

    function evidenceConfidenceColor(item) {
        if (!root.hasEvidenceConfidence(item))
            return Theme.textMuted

        const details = item.evidenceConfidenceDetails || ({})
        if (Boolean(details.hardConflict))
            return Theme.danger

        const coverage = root.hasUnitScore(item.evidenceConfidenceCoverage)
            ? Number(item.evidenceConfidenceCoverage)
            : 0
        const confidence = Number(item.evidenceConfidence)

        if (coverage < 0.5)
            return Theme.warning
        if (confidence >= 0.8)
            return Theme.success
        if (confidence >= 0.55)
            return Theme.warning
        return Theme.danger
    }

    function evidenceConfidenceFactors(item) {
        if (!root.hasEvidenceConfidence(item))
            return ""

        const details = item.evidenceConfidenceDetails || ({})
        const parts = []

        if (root.hasUnitScore(details.intrinsicStrength))
            parts.push("intrinsic " + root.scorePercent(details.intrinsicStrength))
        if (root.hasUnitScore(details.sourceReliability))
            parts.push("source " + root.scorePercent(details.sourceReliability))
        if (root.hasUnitScore(details.corroboration))
            parts.push("corroboration " + root.scorePercent(details.corroboration))
        if (root.hasUnitScore(details.independence))
            parts.push("independence " + root.scorePercent(details.independence))
        if (root.hasUnitScore(details.contradiction))
            parts.push("contradiction " + root.scorePercent(details.contradiction))
        if (Boolean(details.hardConflict))
            parts.push("hard conflict")

        return parts.join(" · ")
    }

    function evidenceExplanation(item) {
        if (!item || !item.evidenceConfidenceExplanation)
            return ({})
        return item.evidenceConfidenceExplanation
    }

    function hasEvidenceExplanation(item) {
        const explanation = root.evidenceExplanation(item)
        return String(explanation.summary || "") !== ""
            || (explanation.reasons || []).length > 0
            || (explanation.limitations || []).length > 0
    }

    function evidenceExplanationText(item) {
        const explanation = root.evidenceExplanation(item)
        const rows = []

        const reasons = explanation.reasons || []
        for (let i = 0; i < Math.min(reasons.length, 4); ++i) {
            const message = String(reasons[i].message || "")
            if (message)
                rows.push("• " + message)
        }

        const limitations = explanation.limitations || []
        for (let i = 0; i < Math.min(limitations.length, 4); ++i) {
            const message = String(limitations[i].message || "")
            if (message)
                rows.push("! " + message)
        }

        return rows.join("\n")
    }

    function unifiedExplanations(item) {
        if (!item)
            return []
        const rows = item.investigationExplainability || []
        return Array.isArray(rows) ? rows : []
    }

    function hasUnifiedWhy(item) {
        return root.unifiedExplanations(item).length > 0
    }

    function whyQuestionLabel(value) {
        const key = String(value || "").toLowerCase()
        if (key === "why_found") return "WHY FOUND"
        if (key === "why_ranked") return "WHY RANKED"
        if (key === "why_confident") return "WHY CONFIDENT"
        if (key === "why_linked") return "WHY LINKED"
        if (key === "why_resolved") return "WHY RESOLVED"
        if (key === "why_merged") return "WHY MERGED"
        if (key === "why_contradicted") return "WHY CONTRADICTED"
        return "WHY"
    }

    function whyDomainLabel(value) {
        const key = String(value || "").toLowerCase()
        if (key === "entity_resolution") return "ENTITY RESOLUTION"
        if (key === "entity_merge") return "ENTITY MERGE"
        return key ? key.replace("_", " ").toUpperCase() : "INVESTIGATION"
    }

    function whyEffectColor(value) {
        const key = String(value || "").toLowerCase()
        if (key === "support") return Theme.success
        if (key === "contradict") return Theme.danger
        if (key === "limitation") return Theme.warning
        if (key === "context") return Theme.accent
        return Theme.textMuted
    }

    function shortObjectId(value) {
        const text = String(value || "")
        if (text.length <= 18)
            return text
        return text.slice(0, 8) + "…" + text.slice(-6)
    }

    function explanationSubjectText(explanation) {
        const subject = (explanation || {}).subject || ({})
        const leftType = String(subject.objectType || "object").toUpperCase()
        const leftId = root.shortObjectId(subject.objectId)
        const rightId = String(subject.relatedObjectId || "")
        if (!rightId)
            return leftType + " · " + leftId
        const rightType = String(subject.relatedObjectType || "object").toUpperCase()
        return leftType + " · " + leftId + "  ↔  "
            + rightType + " · " + root.shortObjectId(rightId)
    }

    function openWhyPayload(rows, title) {
        const values = Array.isArray(rows) ? rows : []
        if (values.length === 0)
            return
        root.whyExplanations = values
        root.whyTitle = String(title || "Explainability")
        root.whyDrawerOpen = true
    }

    function openWhyForItem(item, title) {
        root.openWhyPayload(
            root.unifiedExplanations(item),
            title
        )
    }

    function closeWhy() {
        root.whyDrawerOpen = false
        root.whyExplanations = []
        root.whyTitle = "Explainability"
    }

    function runAnalysisNow() {
        const focus = root.selectedFocus()
        const started = analysisBridge.runAnalysis(
            String(desktopBridge.currentCaseId || ""),
            questionInput.text,
            root.selectedMode,
            root.selectedModel,
            root.selectedReasoning,
            String(focus.type || "case"),
            String(focus.id || ""),
            String(focus.label || "Entire Investigation"),
            root.selectedProvider
        )
        if (started)
            root.activeView = "overview"
    }

    function sendChatNow() {
        const text = String(questionInput.text || "").trim()
        if (!text)
            return

        if (!desktopBridge.hasCurrentCase) {
            desktopBridge.navigateTo("cases")
            return
        }

        const focus = root.selectedFocus()
        const started = analysisBridge.sendMessage(
            String(desktopBridge.currentCaseId || ""),
            text,
            root.selectedProvider,
            root.selectedModel,
            root.selectedReasoning,
            root.selectedMode,
            String(focus.type || "case"),
            String(focus.id || ""),
            String(focus.label || "Entire Investigation")
        )
        if (started) {
            questionInput.text = ""
            root.activeView = "assistant"
            Qt.callLater(root.scrollChatToBottom)
        }
    }

    function scrollChatToBottom() {
        chatFlick.contentY = Math.max(
            0,
            chatFlick.contentHeight - chatFlick.height
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
        function onChanged() {
            root.reload()
            root.ensureProviderSelection()
            Qt.callLater(root.scrollChatToBottom)
        }
    }

    Connections {
        target: desktopBridge
        function onChanged() { root.prepareCase() }
    }

    Component.onCompleted: {
        root.reload()
        root.prepareCase()
        root.selectedProvider = String(root.provider.provider || "ollama")
        root.applyProvider(root.selectedProvider)
        root.applyMode("standard")
        analysisBridge.refreshProviders()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 22
        anchors.rightMargin: 22
        anchors.topMargin: 14
        anchors.bottomMargin: 16
        spacing: 10

        // Compact analytical header. The global application sidebar already
        // provides primary navigation, so Analysis does not add a second rail.
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 58

            Column {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2

                Text {
                    text: "ANALYSIS LAB"
                    color: Theme.accent
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.6
                }

                Text {
                    text: "AI Analysis"
                    color: Theme.textPrimary
                    font.pixelSize: 26
                    font.weight: Font.DemiBold
                }

                Text {
                    width: Math.max(260, parent.parent.width - providerPill.width - 42)
                    text: desktopBridge.hasCurrentCase
                        ? ("Grounded assistant for “" + String(desktopBridge.currentCaseTitle || "Investigation") + "”")
                        : "Select an investigation to begin."
                    color: Theme.textMuted
                    font.pixelSize: 9
                    elide: Text.ElideRight
                }
            }

            Rectangle {
                id: providerPill
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(390, Math.max(260, parent.width * 0.32))
                height: 38
                radius: 19
                color: "#0d1c28"
                border.width: 1
                border.color: (
                    Boolean(root.selectedProviderInfo().configured)
                    && !root.providerHasRuntimeError(root.selectedProviderInfo())
                ) ? Theme.border : Theme.danger

                Rectangle {
                    x: 12
                    anchors.verticalCenter: parent.verticalCenter
                    width: 7
                    height: 7
                    radius: 4
                    color: {
                        const info = root.selectedProviderInfo()
                        if (!Boolean(info.configured)) return Theme.danger
                        if (root.providerHasRuntimeError(info)) return Theme.danger
                        if (String(info.provider || "") === "ollama" && info.online === false) return Theme.danger
                        if (String(info.provider || "") === "ollama" && info.online !== true) return Theme.warning
                        return Theme.success
                    }
                }

                Text {
                    x: 28
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 40
                    text: {
                        const info = root.selectedProviderInfo()
                        let status = ""
                        const runtimeStatus = root.providerRuntimeStatusText(info)
                        if (runtimeStatus)
                            status = " · " + runtimeStatus
                        else if (String(info.provider || "") === "openai" && info.storeResponses === false)
                            status = " · " + "storage off"
                        else if (String(info.provider || "") === "ollama")
                            status = String(info.status || "") === "online_no_models"
                                ? " · no installed models"
                                : (info.online === true ? " · online" : (info.online === false ? " · offline" : " · checking"))
                        return String(info.label || "AI") + " · " + String(root.selectedModel || info.model || "No model") + status
                    }
                    color: (
                        Boolean(root.selectedProviderInfo().configured)
                        && !root.providerHasRuntimeError(root.selectedProviderInfo())
                    ) ? Theme.textSecondary : Theme.danger
                    font.pixelSize: 9
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                }
            }
        }

        // One compact analytical tab strip instead of a second full-height sidebar.
        Rectangle {
            id: analysisTabs
            objectName: "analysisLayerRail"
            Layout.fillWidth: true
            Layout.preferredHeight: 44
            radius: 10
            color: "#0b1a26"
            border.width: 1
            border.color: Theme.border

            RowLayout {
                anchors.fill: parent
                anchors.margins: 5
                spacing: 4

                Repeater {
                    model: root.layerItems

                    delegate: Rectangle {
                        id: layerTab
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumWidth: 72
                        radius: 7
                        color: root.activeView === String(layerTab.modelData.key)
                            ? Theme.accentSoft
                            : (layerTabMouse.containsMouse ? Theme.surfaceHover : "transparent")
                        border.width: root.activeView === String(layerTab.modelData.key) ? 1 : 0
                        border.color: Theme.accent

                        Row {
                            anchors.centerIn: parent
                            spacing: 6

                            Text {
                                text: String(layerTab.modelData.label)
                                color: root.activeView === String(layerTab.modelData.key)
                                    ? Theme.textPrimary
                                    : Theme.textSecondary
                                font.pixelSize: 9
                                font.weight: root.activeView === String(layerTab.modelData.key)
                                    ? Font.DemiBold
                                    : Font.Normal
                            }

                            Rectangle {
                                visible: root.navCount(String(layerTab.modelData.key)) > 0
                                width: Math.max(20, layerTabCount.implicitWidth + 8)
                                height: 18
                                radius: 9
                                color: "#0d1c28"

                                Text {
                                    id: layerTabCount
                                    anchors.centerIn: parent
                                    text: String(root.navCount(String(layerTab.modelData.key)))
                                    color: Theme.textMuted
                                    font.pixelSize: 7
                                }
                            }
                        }

                        MouseArea {
                            id: layerTabMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activeView = String(layerTab.modelData.key)
                        }
                    }
                }
            }
        }

        // Small run-status bar. It never competes with the result workspace.
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: analysisBridge.busy || Boolean(root.run.hasRun) ? 40 : 0
            visible: analysisBridge.busy || Boolean(root.run.hasRun)
            radius: 8
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
                anchors.right: clearRunButton.left
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: String(root.run.progressText || root.run.status || "")
                    + (root.run.currentStageLabel ? " · " + String(root.run.currentStageLabel) : "")
                    + (Boolean(root.run.hasRun) && root.run.cost
                        ? " · " + String(root.run.cost.display || "—")
                        : "")
                color: Theme.textSecondary
                font.pixelSize: 9
                elide: Text.ElideRight
            }

            AppButton {
                id: clearRunButton
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                width: 78
                height: 28
                text: "Clear"
                quiet: true
                enabled: !analysisBridge.busy && Boolean(root.run.hasRun)
                onClicked: analysisBridge.clear()
            }
        }

        Rectangle {
            id: analysisWorkspace
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 12
            color: "#091722"
            border.width: 1
            border.color: Theme.border
            clip: true

            StackLayout {
                    anchors.fill: parent
                    anchors.margins: 1
                currentIndex: root.activeViewIndex()
    
                // ASSISTANT
                Flickable {
                    id: chatFlick
                    clip: true
                    contentWidth: width
                    contentHeight: chatContent.height
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    Column {
                        id: chatContent
                        width: Math.min(parent.width - 28, 980)
                        x: Math.max(14, (parent.width - width) / 2)
                        spacing: 10

                        Item {
                            width: parent.width
                            height: 50

                            Column {
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2

                                Text {
                                    text: "Investigation Assistant"
                                    color: Theme.textPrimary
                                    font.pixelSize: 18
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: "Multi-turn, case-grounded conversation · R# references open the underlying source"
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                }
                            }

                            AppButton {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                width: 92
                                height: 30
                                text: "New chat"
                                quiet: true
                                enabled: !analysisBridge.busy && !analysisBridge.chatBusy
                                onClicked: analysisBridge.newChat()
                            }
                        }

                        Item {
                            width: parent.width
                            height: root.chatMessages.length === 0
                                ? Math.max(250, chatFlick.height - 86)
                                : 0
                            visible: root.chatMessages.length === 0

                            Column {
                                anchors.centerIn: parent
                                width: Math.min(parent.width - 40, 680)
                                spacing: 13

                                Rectangle {
                                    x: (parent.width - width) / 2
                                    width: 48
                                    height: 48
                                    radius: 24
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
                                    text: "Ask anything about this investigation"
                                    color: Theme.textPrimary
                                    font.pixelSize: 21
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                }

                                Text {
                                    width: parent.width
                                    text: desktopBridge.hasCurrentCase
                                        ? "I can follow the conversation, answer follow-up questions, reason over bounded case sources, and cite the material used."
                                        : "Select an investigation first. The assistant is intentionally case-scoped so investigation claims stay grounded."
                                    color: Theme.textMuted
                                    font.pixelSize: 10
                                    lineHeight: 1.35
                                    wrapMode: Text.Wrap
                                    horizontalAlignment: Text.AlignHCenter
                                }

                                Row {
                                    width: parent.width
                                    spacing: 8

                                    Repeater {
                                        model: [
                                            "What are the most important findings?",
                                            "What does the evidence suggest?",
                                            "What should I investigate next?"
                                        ]

                                        delegate: Rectangle {
                                            id: chatPrompt
                                            required property var modelData
                                            width: (parent.width - 16) / 3
                                            height: 58
                                            radius: 10
                                            color: chatPromptMouse.containsMouse
                                                ? Theme.surfaceHover
                                                : Theme.surface
                                            border.width: 1
                                            border.color: chatPromptMouse.containsMouse
                                                ? Theme.borderHover
                                                : Theme.border
                                            opacity: desktopBridge.hasCurrentCase ? 1 : 0.5

                                            Text {
                                                anchors.fill: parent
                                                anchors.margins: 10
                                                text: String(chatPrompt.modelData)
                                                color: Theme.textSecondary
                                                font.pixelSize: 9
                                                wrapMode: Text.Wrap
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }

                                            MouseArea {
                                                id: chatPromptMouse
                                                anchors.fill: parent
                                                enabled: desktopBridge.hasCurrentCase
                                                hoverEnabled: true
                                                cursorShape: enabled
                                                    ? Qt.PointingHandCursor
                                                    : Qt.ArrowCursor
                                                onClicked: {
                                                    questionInput.text = String(chatPrompt.modelData)
                                                    questionInput.forceActiveFocus()
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Repeater {
                            model: root.chatMessages

                            delegate: Item {
                                id: chatMessageRow
                                required property var modelData
                                property bool isUser: String(modelData.role || "") === "user"
                                width: chatContent.width
                                height: chatBubble.height + 6

                                Rectangle {
                                    id: chatBubble
                                    anchors.right: chatMessageRow.isUser ? parent.right : undefined
                                    anchors.left: chatMessageRow.isUser ? undefined : parent.left
                                    width: chatMessageRow.isUser
                                        ? Math.min(parent.width * 0.74, 720)
                                        : parent.width
                                    height: Math.max(54, messageColumn.implicitHeight + 24)
                                    radius: 12
                                    color: chatMessageRow.isUser
                                        ? Theme.accentSoft
                                        : Theme.surface
                                    border.width: 1
                                    border.color: chatMessageRow.isUser
                                        ? Theme.accent
                                        : (Boolean(chatMessageRow.modelData.error) ? Theme.danger : Theme.border)

                                    Column {
                                        id: messageColumn
                                        x: 14
                                        y: 11
                                        width: parent.width - 28
                                        spacing: 7

                                        Text {
                                            width: parent.width
                                            text: chatMessageRow.isUser
                                                ? "YOU"
                                                : (
                                                    Boolean(chatMessageRow.modelData.error)
                                                    ? (
                                                        String(chatMessageRow.modelData.provider || "AI").toUpperCase()
                                                        + " · ACTION REQUIRED"
                                                    )
                                                    : (
                                                        "OSINTXZ AI"
                                                        + (
                                                            String(chatMessageRow.modelData.model || "")
                                                            ? " · " + String(chatMessageRow.modelData.model)
                                                            : ""
                                                        )
                                                    )
                                                )
                                            color: chatMessageRow.isUser
                                                ? Theme.accent
                                                : (Boolean(chatMessageRow.modelData.error) ? Theme.danger : Theme.textMuted)
                                            font.pixelSize: 7
                                            font.weight: Font.DemiBold
                                            font.letterSpacing: 0.8
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            width: parent.width
                                            text: String(chatMessageRow.modelData.text || "")
                                            color: Theme.textPrimary
                                            font.pixelSize: 11
                                            lineHeight: 1.45
                                            wrapMode: Text.Wrap
                                            textFormat: chatMessageRow.isUser
                                                ? Text.PlainText
                                                : Text.MarkdownText
                                            onLinkActivated: function(link) {
                                                Qt.openUrlExternally(link)
                                            }
                                        }

                                        Row {
                                            width: parent.width
                                            height: visible ? 30 : 0
                                            visible: Boolean(chatMessageRow.modelData.error)
                                            spacing: 8

                                            AppButton {
                                                width: 126
                                                height: 30
                                                text: root.ollamaReady()
                                                    ? "Use Ollama"
                                                    : "Check Ollama"
                                                primary: root.ollamaReady()
                                                quiet: !root.ollamaReady()
                                                visible: (
                                                    String(chatMessageRow.modelData.suggestedAction || "") === "switch_to_ollama"
                                                    || String(chatMessageRow.modelData.suggestedAction || "") === "retry_or_ollama"
                                                )
                                                onClicked: root.recoverWithOllama(
                                                    chatMessageRow.modelData
                                                )
                                            }

                                            AppButton {
                                                width: 132
                                                height: 30
                                                text: "Open API billing"
                                                quiet: true
                                                visible: String(chatMessageRow.modelData.errorKind || "") === "quota_exhausted"
                                                onClicked: Qt.openUrlExternally(
                                                    "https://platform.openai.com/settings/organization/billing/"
                                                )
                                            }

                                            Text {
                                                height: 30
                                                verticalAlignment: Text.AlignVCenter
                                                text: String(chatMessageRow.modelData.errorCode || "")
                                                color: Theme.textMuted
                                                font.pixelSize: 7
                                                visible: String(chatMessageRow.modelData.errorCode || "") !== ""
                                            }
                                        }

                                        Flow {
                                            width: parent.width
                                            height: visible ? childrenRect.height : 0
                                            visible: !chatMessageRow.isUser
                                                && (chatMessageRow.modelData.sourceReferences || []).length > 0
                                            spacing: 6

                                            Repeater {
                                                model: chatMessageRow.modelData.sourceReferences || []

                                                delegate: Rectangle {
                                                    id: chatRef
                                                    required property var modelData
                                                    width: chatRefText.implicitWidth + 18
                                                    height: 24
                                                    radius: 12
                                                    color: Theme.accentSoft
                                                    border.width: 1
                                                    border.color: Theme.accent

                                                    Text {
                                                        id: chatRefText
                                                        anchors.centerIn: parent
                                                        text: String(chatRef.modelData)
                                                        color: Theme.accent
                                                        font.pixelSize: 8
                                                        font.weight: Font.DemiBold
                                                    }

                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: analysisBridge.openChatSource(
                                                            String(chatMessageRow.modelData.id || ""),
                                                            String(chatRef.modelData || "")
                                                        )
                                                    }
                                                }
                                            }
                                        }

                                        Text {
                                            width: parent.width
                                            visible: !chatMessageRow.isUser
                                                && chatMessageRow.modelData.cost
                                                && String(chatMessageRow.modelData.cost.display || "") !== ""
                                            text: (
                                                String(chatMessageRow.modelData.provider || "").toUpperCase()
                                                + (
                                                    chatMessageRow.modelData.cost
                                                    ? " · " + String(chatMessageRow.modelData.cost.display || "")
                                                    : ""
                                                )
                                            )
                                            color: Theme.textMuted
                                            font.pixelSize: 7
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            visible: analysisBridge.chatBusy
                            width: Math.min(parent.width, 280)
                            height: 46
                            radius: 12
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.border

                            Row {
                                anchors.centerIn: parent
                                spacing: 8

                                BusyIndicator {
                                    width: 18
                                    height: 18
                                    running: analysisBridge.chatBusy
                                }

                                Text {
                                    text: "Thinking…"
                                    color: Theme.textSecondary
                                    font.pixelSize: 10
                                }
                            }
                        }

                        Item {
                            width: parent.width
                            height: 8
                        }
                    }
                }

                // OVERVIEW
                Flickable {
                    id: overviewFlick
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
                            height: !Boolean(root.run.hasRun) ? Math.max(330, overviewFlick.height - 20) : 0
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
                                    text: "What do you want to understand?"
                                    color: Theme.textPrimary
                                    font.pixelSize: 22
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                }
    
                                Text {
                                    width: parent.width
                                    text: desktopBridge.hasCurrentCase
                                        ? "Ask a focused question, or use one of the starting points below. Analysis stays grounded in the investigation’s bounded sources."
                                        : "Select an investigation first. Once a case is active, ask a focused question or use one of the starting points below."
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
                            text: "Source-backed observations selected into the bounded RAG context. Evidence confidence is shown only when M024 can reconstruct a persisted proposition; coverage shows how much of that assessment was observable."
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
                                property bool explanationOpen: false
                                width: parent.width
                                height: Math.max(
                                    92,
                                    factText.implicitHeight
                                        + (root.hasEvidenceConfidence(factCard.modelData) ? 112 : 48)
                                        + (
                                            factCard.explanationOpen
                                            ? factExplanationText.implicitHeight + 38
                                            : 0
                                        )
                                )
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
                                    width: parent.width
                                        - (root.hasEvidenceConfidence(factCard.modelData) ? 220 : 76)
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

                                Rectangle {
                                    visible: root.hasEvidenceConfidence(factCard.modelData)
                                    anchors.right: parent.right
                                    anchors.rightMargin: 14
                                    y: 10
                                    width: 136
                                    height: 27
                                    radius: 13
                                    color: Theme.surfaceRaised
                                    border.width: 1
                                    border.color: root.evidenceConfidenceColor(factCard.modelData)

                                    Text {
                                        anchors.centerIn: parent
                                        text: "EVIDENCE "
                                            + root.scorePercent(factCard.modelData.evidenceConfidence)
                                            + " · COV "
                                            + root.scorePercent(factCard.modelData.evidenceConfidenceCoverage)
                                        color: root.evidenceConfidenceColor(factCard.modelData)
                                        font.pixelSize: 7
                                        font.weight: Font.DemiBold
                                    }
                                }

                                Text {
                                    id: factFactors
                                    visible: root.hasEvidenceConfidence(factCard.modelData)
                                    x: 14
                                    y: factText.y + factText.implicitHeight + 10
                                    width: parent.width - 100
                                    text: root.evidenceConfidenceFactors(factCard.modelData)
                                    color: Theme.textMuted
                                    font.pixelSize: 8
                                    wrapMode: Text.Wrap
                                }

                                Rectangle {
                                    id: factWhyButton
                                    visible: root.hasUnifiedWhy(factCard.modelData)
                                        || root.hasEvidenceExplanation(factCard.modelData)
                                    anchors.right: parent.right
                                    anchors.rightMargin: 14
                                    y: factText.y + factText.implicitHeight + 5
                                    width: 68
                                    height: 23
                                    radius: 11
                                    color: factWhyMouse.containsMouse
                                        ? Theme.surfaceHover
                                        : Theme.surfaceRaised
                                    border.width: 1
                                    border.color: Theme.border

                                    Text {
                                        anchors.centerIn: parent
                                        text: root.hasUnifiedWhy(factCard.modelData)
                                            ? "WHY"
                                            : (factCard.explanationOpen ? "WHY ▲" : "WHY ▼")
                                        color: Theme.accent
                                        font.pixelSize: 7
                                        font.weight: Font.DemiBold
                                    }

                                    MouseArea {
                                        id: factWhyMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (root.hasUnifiedWhy(factCard.modelData)) {
                                                root.openWhyForItem(
                                                    factCard.modelData,
                                                    String(factCard.modelData.reference || "Fact")
                                                        + " · "
                                                        + String(factCard.modelData.title || "Source observation")
                                                )
                                            } else {
                                                factCard.explanationOpen = !factCard.explanationOpen
                                            }
                                        }
                                    }
                                }

                                Rectangle {
                                    id: factExplanation
                                    visible: factCard.explanationOpen
                                        && !root.hasUnifiedWhy(factCard.modelData)
                                        && root.hasEvidenceExplanation(factCard.modelData)
                                    x: 14
                                    y: Math.max(
                                        factFactors.y + factFactors.implicitHeight,
                                        factWhyButton.y + factWhyButton.height
                                    ) + 10
                                    width: parent.width - 28
                                    height: factExplanationText.implicitHeight + 22
                                    radius: 8
                                    color: Theme.surfaceRaised
                                    border.width: 1
                                    border.color: Theme.border

                                    Text {
                                        id: factExplanationText
                                        x: 10
                                        y: 10
                                        width: parent.width - 20
                                        text: {
                                            const explanation = root.evidenceExplanation(factCard.modelData)
                                            const summary = String(explanation.summary || "")
                                            const details = root.evidenceExplanationText(factCard.modelData)
                                            if (summary && details)
                                                return summary + "\n\n" + details
                                            return summary || details
                                        }
                                        color: Theme.textSecondary
                                        font.pixelSize: 8
                                        lineHeight: 1.35
                                        wrapMode: Text.Wrap
                                    }
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
                    subtitle: String(root.sources.length) + " bounded source(s) · Search relevance and Evidence confidence are separate signals · click R# to open source"
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
                            height: (
                                root.hasEvidenceConfidence(sourceRow.modelData)
                                || root.hasUnifiedWhy(sourceRow.modelData)
                            ) ? 104 : 72
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
                                width: parent.width - 245
                                text: String(sourceRow.modelData.title || "Investigation source")
                                color: Theme.textPrimary
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
    
                            Text {
                                x: 68
                                y: 35
                                width: parent.width - 245
                                text: String(sourceRow.modelData.snippet || "")
                                color: Theme.textMuted
                                font.pixelSize: 8
                                elide: Text.ElideRight
                            }
    
                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                y: 10
                                width: 154
                                horizontalAlignment: Text.AlignRight
                                text: String(sourceRow.modelData.objectType || "object").toUpperCase()
                                    + "\nSEARCH " + Number(sourceRow.modelData.score || 0).toFixed(3)
                                    + (
                                        root.hasEvidenceConfidence(sourceRow.modelData)
                                        ? "\nEVIDENCE "
                                            + root.scorePercent(sourceRow.modelData.evidenceConfidence)
                                            + " · COV "
                                            + root.scorePercent(sourceRow.modelData.evidenceConfidenceCoverage)
                                        : "\nEVIDENCE —"
                                    )
                                color: root.hasEvidenceConfidence(sourceRow.modelData)
                                    ? root.evidenceConfidenceColor(sourceRow.modelData)
                                    : Theme.textMuted
                                font.pixelSize: 8
                            }

                            Text {
                                visible: root.hasEvidenceConfidence(sourceRow.modelData)
                                x: 68
                                y: 57
                                width: parent.width - 245
                                text: root.evidenceConfidenceFactors(sourceRow.modelData)
                                color: Theme.textMuted
                                font.pixelSize: 7
                                elide: Text.ElideRight
                            }
    
                            MouseArea {
                                id: sourceMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: analysisBridge.openSource(String(sourceRow.modelData.reference || ""))
                            }

                            Rectangle {
                                id: sourceWhyButton
                                visible: root.hasUnifiedWhy(sourceRow.modelData)
                                z: 2
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 9
                                width: 58
                                height: 22
                                radius: 11
                                color: sourceWhyMouse.containsMouse
                                    ? Theme.surfaceHover
                                    : Theme.surfaceRaised
                                border.width: 1
                                border.color: Theme.border

                                Text {
                                    anchors.centerIn: parent
                                    text: "WHY"
                                    color: Theme.accent
                                    font.pixelSize: 7
                                    font.weight: Font.DemiBold
                                }

                                MouseArea {
                                    id: sourceWhyMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.openWhyForItem(
                                        sourceRow.modelData,
                                        String(sourceRow.modelData.reference || "Source")
                                            + " · "
                                            + String(sourceRow.modelData.title || "Investigation source")
                                    )
                                }
                            }
                        }
    
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    }
                }
    
                // UNIFIED EXPLAINABILITY
                Panel {
                    title: "Explainability"
                    subtitle: String(root.explainability.length)
                        + " deterministic WHY answer(s) · Search, Evidence, Entity Resolution and Graph remain separate domains"
                    iconSource: "../../assets/icons/search.svg"

                    ListView {
                        anchors.fill: parent
                        clip: true
                        model: root.explainability
                        boundsBehavior: Flickable.StopAtBounds

                        delegate: Rectangle {
                            id: whyRow
                            required property var modelData
                            width: ListView.view.width
                            height: 92
                            color: whyRowMouse.containsMouse
                                ? Theme.surfaceHover
                                : "transparent"

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
                                width: Math.max(92, whyQuestionText.implicitWidth + 18)
                                height: 24
                                radius: 12
                                color: Theme.accentSoft
                                border.width: 1
                                border.color: Theme.accent

                                Text {
                                    id: whyQuestionText
                                    anchors.centerIn: parent
                                    text: root.whyQuestionLabel(whyRow.modelData.question)
                                    color: Theme.accent
                                    font.pixelSize: 7
                                    font.weight: Font.DemiBold
                                }
                            }

                            Text {
                                x: 124
                                y: 14
                                width: parent.width - 280
                                text: root.explanationSubjectText(whyRow.modelData)
                                color: Theme.textPrimary
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                y: 14
                                width: 130
                                horizontalAlignment: Text.AlignRight
                                text: root.whyDomainLabel(whyRow.modelData.domain)
                                color: Theme.textMuted
                                font.pixelSize: 7
                                elide: Text.ElideLeft
                            }

                            Text {
                                x: 14
                                y: 46
                                width: parent.width - 28
                                text: String(whyRow.modelData.summary || "")
                                color: Theme.textSecondary
                                font.pixelSize: 8
                                elide: Text.ElideRight
                            }

                            Text {
                                x: 14
                                y: 68
                                width: parent.width - 28
                                text: String((whyRow.modelData.reasons || []).length)
                                    + " reason(s) · "
                                    + String((whyRow.modelData.limitations || []).length)
                                    + " limitation(s) · click to inspect"
                                color: Theme.textMuted
                                font.pixelSize: 7
                                elide: Text.ElideRight
                            }

                            MouseArea {
                                id: whyRowMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.openWhyPayload(
                                    [whyRow.modelData],
                                    root.whyQuestionLabel(whyRow.modelData.question)
                                        + " · "
                                        + root.explanationSubjectText(whyRow.modelData)
                                )
                            }
                        }

                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: root.explainability.length === 0
                        text: Boolean(root.run.hasRun)
                            ? "No deterministic WHY explanations are available for this run."
                            : "Run an investigation analysis to build deterministic WHY explanations."
                        color: Theme.textMuted
                        font.pixelSize: 10
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

        // Assistant-style composer stays at the bottom, like a chat workspace.
        // Its children fit inside the fixed height at real desktop sizes.
        Rectangle {
            objectName: "analysisComposer"
            Layout.fillWidth: true
            Layout.preferredHeight: 206
            radius: 14
            color: "#0d1c28"
            border.width: 1
            border.color: questionInput.activeFocus ? Theme.borderHover : Theme.border

            Column {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

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
                                enabled: !analysisBridge.busy && !analysisBridge.chatBusy
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.applyMode(String(modePill.modelData.key || "standard"))
                            }
                        }
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 68
                    radius: 9
                    color: Theme.background
                    border.width: 1
                    border.color: questionInput.activeFocus ? Theme.accent : Theme.divider

                    TextArea {
                        id: questionInput
                        anchors.fill: parent
                        anchors.margins: 7
                        placeholderText: "Message the AI assistant about this investigation..."
                        wrapMode: TextEdit.Wrap
                        color: Theme.textPrimary
                        placeholderTextColor: Theme.textMuted
                        selectionColor: Theme.accent
                        selectedTextColor: "#ffffff"
                        font.pixelSize: 11
                        enabled: !analysisBridge.busy && !analysisBridge.chatBusy
                        Keys.onPressed: function(event) {
                            if (
                                (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                                && !(event.modifiers & Qt.ShiftModifier)
                            ) {
                                root.sendChatNow()
                                event.accepted = true
                            }
                        }
                        background: Rectangle { color: "transparent" }
                    }
                }

                Row {
                    objectName: "analysisControlRow"
                    width: parent.width
                    height: 48
                    spacing: 8

                    Column {
                        width: Math.max(1, (parent.width - 350) * 0.24)
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
                            enabled: !analysisBridge.busy && !analysisBridge.chatBusy && desktopBridge.hasCurrentCase
                            onCurrentIndexChanged: root.selectedFocusIndex = currentIndex
                        }
                    }

                    Column {
                        width: Math.max(1, (parent.width - 350) * 0.18)
                        height: 48
                        spacing: 3

                        Text {
                            text: "PROVIDER"
                            color: Theme.textMuted
                            font.pixelSize: 7
                            font.letterSpacing: 0.9
                        }

                        AppComboBox {
                            id: providerBox
                            width: parent.width
                            height: 32
                            model: root.providerLabels()
                            enabled: !analysisBridge.busy && !analysisBridge.chatBusy
                            onActivated: function(index) {
                                const values = root.providers()
                                if (index >= 0 && index < values.length) {
                                    const providerId = String(values[index].provider || "ollama")
                                    root.applyProvider(providerId)
                                    if (providerId === "ollama")
                                        analysisBridge.refreshProviders()
                                }
                            }
                        }
                    }

                    Column {
                        width: Math.max(1, (parent.width - 350) * 0.34)
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
                            enabled: !analysisBridge.busy
                                && !analysisBridge.chatBusy
                                && Boolean(root.selectedProviderInfo().configured)
                                && root.models().length > 0
                            onActivated: function(index) {
                                const value = root.modelIdAt(index)
                                if (value)
                                    root.selectedModel = value
                            }
                        }
                    }

                    Column {
                        width: Math.max(1, (parent.width - 350) * 0.24)
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
                            model: String(root.selectedProvider || "") === "openai"
                                ? root.reasoningEfforts()
                                : ["Local provider"]
                            enabled: !analysisBridge.busy
                                && !analysisBridge.chatBusy
                                && String(root.selectedProvider || "") === "openai"
                                && Boolean(root.selectedProviderInfo().configured)
                            onActivated: function(index) {
                                const values = root.reasoningEfforts()
                                if (index >= 0 && index < values.length)
                                    root.selectedReasoning = String(values[index])
                            }
                        }
                    }

                    AppButton {
                        id: runButton
                        y: 5
                        width: 154
                        height: 38
                        text: analysisBridge.busy
                            ? "Analyzing…"
                            : "Run Analysis"
                        quiet: true
                        enabled: !analysisBridge.busy
                            && !analysisBridge.chatBusy
                            && desktopBridge.hasCurrentCase
                            && root.selectedProviderReady()
                        onClicked: root.runAnalysisNow()
                    }

                    AppButton {
                        id: sendButton
                        y: 5
                        width: 154
                        height: 38
                        text: analysisBridge.chatBusy
                            ? "Thinking…"
                            : (desktopBridge.hasCurrentCase ? "Send" : "Select Case")
                        primary: true
                        enabled: !analysisBridge.busy
                            && !analysisBridge.chatBusy
                            && (!desktopBridge.hasCurrentCase || root.selectedProviderReady())
                        onClicked: root.sendChatNow()
                    }
                }
            }
        }
    }
}

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
    property var stages: run.stages || []
    property var conclusions: run.conclusions || []
    property var sources: run.sources || []
    property var warnings: run.warnings || []
    property var citationSummary: run.citationSummary || ({})

    function reload() {
        root.run = analysisBridge.runData || ({})
        root.provider = analysisBridge.providerInfo || ({})
        root.stages = root.run.stages || []
        root.conclusions = root.run.conclusions || []
        root.sources = root.run.sources || []
        root.warnings = root.run.warnings || []
        root.citationSummary = root.run.citationSummary || ({})
    }

    function statusColor(status) {
        var value = String(status || "").toLowerCase()
        if (value === "success" || value === "completed") return Theme.success
        if (value === "partial" || value === "skipped") return Theme.warning
        if (value === "failed" || value === "cancelled") return Theme.danger
        if (value === "running") return Theme.accent
        return Theme.textMuted
    }

    Connections {
        target: analysisBridge
        function onChanged() { root.reload() }
    }

    Component.onCompleted: root.reload()

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Spacing.page
        anchors.rightMargin: Spacing.page
        anchors.topMargin: 16
        anchors.bottomMargin: 24
        spacing: Spacing.panelGap

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 82

            Text {
                x: 2
                y: 0
                text: "INVESTIGATION ANALYSIS"
                color: Theme.textMuted
                font.pixelSize: 9
                font.weight: Font.Medium
                font.letterSpacing: 1.7
            }

            Text {
                x: 2
                y: 19
                text: "AI Analysis"
                color: Theme.textPrimary
                font.pixelSize: Typography.pageTitle
                font.weight: Font.DemiBold
            }

            Text {
                x: 3
                y: 55
                width: parent.width - 390
                text: desktopBridge.hasCurrentCase
                    ? "Analyze " + String(desktopBridge.currentCaseTitle || "the selected investigation")
                        + " using the existing graph, temporal, evidence and RAG pipeline."
                    : "Select an investigation before running analysis."
                color: Theme.textSecondary
                font.pixelSize: 12
                elide: Text.ElideRight
            }

            Rectangle {
                anchors.right: parent.right
                anchors.top: parent.top
                width: 330
                height: 56
                radius: 8
                color: Theme.surface
                border.width: 1
                border.color: Boolean(root.provider.configured) ? Theme.border : Theme.danger

                Text {
                    x: 14
                    y: 9
                    width: parent.width - 28
                    text: String(root.provider.label || "AI")
                        + " · " + String(root.provider.model || "No model")
                    color: Theme.textPrimary
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }

                Text {
                    x: 14
                    y: 31
                    width: parent.width - 28
                    text: Boolean(root.provider.configured)
                        ? ("Configured"
                            + (root.provider.reasoningEffort
                                ? " · reasoning " + String(root.provider.reasoningEffort)
                                : "")
                            + (root.provider.storeResponses === false
                                ? " · API storage off"
                                : ""))
                        : "Not configured — add OPENAI_API_KEY to .env"
                    color: Boolean(root.provider.configured) ? Theme.success : Theme.danger
                    font.pixelSize: 9
                    elide: Text.ElideRight
                }
            }
        }

        Panel {
            Layout.fillWidth: true
            Layout.preferredHeight: 196
            title: "Analysis Focus"
            subtitle: "Optional question · leave blank for the standard full-investigation analysis"
            iconSource: "../../assets/icons/search.svg"

            TextArea {
                id: questionInput
                anchors.left: parent.left
                anchors.right: runButton.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.margins: 14
                anchors.rightMargin: 12
                placeholderText: "Example: What are the strongest relationships, contradictions and unresolved questions in this investigation?"
                wrapMode: TextEdit.Wrap
                color: Theme.textPrimary
                placeholderTextColor: Theme.textMuted
                selectionColor: Theme.accent
                selectedTextColor: "#ffffff"
                font.pixelSize: 11
                enabled: !analysisBridge.busy
                background: Rectangle {
                    radius: 7
                    color: Theme.background
                    border.width: 1
                    border.color: questionInput.activeFocus ? Theme.accent : Theme.border
                }
            }

            AppButton {
                id: runButton
                anchors.right: parent.right
                anchors.rightMargin: 14
                anchors.top: parent.top
                anchors.topMargin: 14
                width: 166
                height: 40
                text: analysisBridge.busy ? "Analyzing…" : "Run Analysis"
                primary: true
                enabled: !analysisBridge.busy
                    && desktopBridge.hasCurrentCase
                    && Boolean(root.provider.configured)
                onClicked: analysisBridge.runAnalysis(
                    String(desktopBridge.currentCaseId || ""),
                    questionInput.text
                )
            }

            AppButton {
                anchors.right: parent.right
                anchors.rightMargin: 14
                anchors.top: runButton.bottom
                anchors.topMargin: 10
                width: 166
                height: 36
                text: "Clear result"
                enabled: !analysisBridge.busy && Boolean(root.run.hasRun)
                onClicked: analysisBridge.clear()
            }

            Text {
                anchors.right: parent.right
                anchors.rightMargin: 14
                anchors.top: runButton.bottom
                anchors.topMargin: 58
                width: 166
                text: "AI output is analysis, not Evidence."
                color: Theme.textMuted
                font.pixelSize: 8
                wrapMode: Text.Wrap
            }
        }

        Panel {
            Layout.fillWidth: true
            Layout.preferredHeight: analysisBridge.busy || Boolean(root.run.hasRun) ? 112 : 0
            visible: analysisBridge.busy || Boolean(root.run.hasRun)
            title: analysisBridge.busy ? "Analysis Running" : "Last Analysis"
            subtitle: String(root.run.progressText || root.run.status || "")
            iconSource: "../../assets/icons/chart.svg"

            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12

                ProgressBar {
                    Layout.fillWidth: true
                    from: 0
                    to: 1
                    value: Number(root.run.progress || (root.run.status === "success" ? 1 : 0))
                }

                Text {
                    Layout.preferredWidth: 250
                    text: root.run.currentStageLabel
                        ? String(root.run.currentStageLabel)
                            + " · " + String(root.run.stageIndex || 0)
                            + "/" + String(root.run.stageCount || 0)
                        : (root.run.durationText ? String(root.run.durationText) : "")
                    color: Theme.textSecondary
                    font.pixelSize: 10
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideRight
                }

                Rectangle {
                    Layout.preferredWidth: 92
                    Layout.preferredHeight: 28
                    radius: 14
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
        }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: width
            contentHeight: resultColumn.height
            boundsBehavior: Flickable.StopAtBounds
            visible: Boolean(root.run.hasRun) && !analysisBridge.busy

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
            }

            Column {
                id: resultColumn
                width: parent.width
                spacing: Spacing.panelGap

                Row {
                    width: parent.width
                    height: 94
                    spacing: 10

                    Repeater {
                        model: [
                            {label: "SUCCESSFUL STAGES", value: root.run.successfulStages || 0},
                            {label: "FAILED STAGES", value: root.run.failedStages || 0},
                            {label: "RAG SOURCES", value: root.sources.length},
                            {label: "VALID CITATIONS", value: root.citationSummary.valid || 0},
                            {label: "WARNINGS", value: root.warnings.length}
                        ]

                        delegate: Rectangle {
                            id: metricCard
                            required property var modelData
                            width: (resultColumn.width - 40) / 5
                            height: 94
                            radius: 8
                            color: Theme.surface
                            border.width: 1
                            border.color: Theme.border

                            Text {
                                x: 12
                                y: 13
                                width: parent.width - 24
                                text: String(metricCard.modelData.label)
                                color: Theme.textMuted
                                font.pixelSize: 8
                                font.letterSpacing: 0.8
                                elide: Text.ElideRight
                            }

                            Text {
                                x: 12
                                y: 42
                                text: String(metricCard.modelData.value)
                                color: Theme.textPrimary
                                font.pixelSize: 24
                                font.weight: Font.DemiBold
                            }
                        }
                    }
                }

                Panel {
                    width: resultColumn.width
                    height: Math.min(520, Math.max(240, summaryText.implicitHeight + 112))
                    title: "AI Summary"
                    subtitle: String(root.run.modelInfo && root.run.modelInfo.model
                        ? root.run.modelInfo.model
                        : root.provider.model || "")
                        + (root.run.summarySourceReferences && root.run.summarySourceReferences.length
                            ? " · sources " + root.run.summarySourceReferences.join(", ")
                            : "")
                    iconSource: "../../assets/icons/chart.svg"

                    Flickable {
                        anchors.fill: parent
                        anchors.margins: 16
                        clip: true
                        contentWidth: width
                        contentHeight: summaryText.implicitHeight
                        boundsBehavior: Flickable.StopAtBounds

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

                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                        }
                    }
                }

                Repeater {
                    model: root.conclusions

                    delegate: Panel {
                        id: conclusionPanel
                        required property var modelData
                        width: resultColumn.width
                        height: Math.min(440, Math.max(210, conclusionText.implicitHeight + 112))
                        title: String(conclusionPanel.modelData.label || "Analysis")
                        subtitle: String(conclusionPanel.modelData.workflow || "")
                            + ((conclusionPanel.modelData.sourceReferences || []).length
                                ? " · " + conclusionPanel.modelData.sourceReferences.join(", ")
                                : "")
                        iconSource: "../../assets/icons/search.svg"

                        Flickable {
                            anchors.fill: parent
                            anchors.margins: 16
                            clip: true
                            contentWidth: width
                            contentHeight: conclusionText.implicitHeight
                            boundsBehavior: Flickable.StopAtBounds

                            Text {
                                id: conclusionText
                                width: parent.width
                                text: String(conclusionPanel.modelData.text || "")
                                color: Theme.textPrimary
                                font.pixelSize: 11
                                lineHeight: 1.45
                                wrapMode: Text.Wrap
                                textFormat: Text.PlainText
                                }

                            ScrollBar.vertical: ScrollBar {
                                policy: ScrollBar.AsNeeded
                            }
                        }
                    }
                }

                Panel {
                    width: resultColumn.width
                    height: Math.min(430, Math.max(210, 88 + root.sources.length * 58))
                    title: "RAG Sources"
                    subtitle: String(root.sources.length)
                        + " bounded investigation source(s) supplied to the AI context"
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
                            height: 58
                            color: "transparent"

                            Rectangle {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 1
                                color: Theme.divider
                            }

                            Text {
                                x: 16
                                y: 9
                                width: parent.width - 150
                                text: String(sourceRow.modelData.reference || "R?")
                                    + " · " + String(sourceRow.modelData.title || "Investigation source")
                                color: Theme.textPrimary
                                font.pixelSize: 10
                                font.weight: Font.Medium
                                elide: Text.ElideRight
                            }

                            Text {
                                x: 16
                                y: 31
                                width: parent.width - 150
                                text: String(sourceRow.modelData.objectType || "object")
                                    + " · score " + Number(sourceRow.modelData.score || 0).toFixed(3)
                                    + ((sourceRow.modelData.matchedMethods || []).length
                                        ? " · " + sourceRow.modelData.matchedMethods.join(", ")
                                        : "")
                                color: Theme.textMuted
                                font.pixelSize: 8
                                elide: Text.ElideRight
                            }

                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 16
                                anchors.verticalCenter: parent.verticalCenter
                                text: String(sourceRow.modelData.status || "").toUpperCase()
                                color: Theme.accent
                                font.pixelSize: 8
                                font.weight: Font.DemiBold
                            }
                        }

                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                        }
                    }
                }

                Panel {
                    width: resultColumn.width
                    height: Math.min(520, Math.max(230, 90 + root.stages.length * 50))
                    title: "Analysis Pipeline"
                    subtitle: "Canonical stages executed by InvestigationAnalysisOrchestrator"
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

                            Text {
                                x: 16
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 230
                                text: String(stageRow.modelData.label || stageRow.modelData.stage || "Stage")
                                color: Theme.textPrimary
                                font.pixelSize: 10
                                font.weight: Font.Medium
                                elide: Text.ElideRight
                            }

                            Text {
                                anchors.right: stageStatus.left
                                anchors.rightMargin: 16
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

                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                        }
                    }
                }

                Panel {
                    width: resultColumn.width
                    height: Math.min(300, Math.max(160, 76 + root.warnings.length * 42))
                    visible: root.warnings.length > 0 || String(root.run.error || "").length > 0
                    title: "Warnings"
                    subtitle: "Partial or failed analysis information"
                    iconSource: "../../assets/icons/settings.svg"

                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8

                        Text {
                            width: parent.width
                            visible: String(root.run.error || "").length > 0
                            text: String(root.run.error || "")
                            color: Theme.danger
                            font.pixelSize: 10
                            wrapMode: Text.Wrap
                        }

                        Repeater {
                            model: root.warnings
                            delegate: Text {
                                required property var modelData
                                width: parent.width
                                text: "• " + String(modelData)
                                color: Theme.warning
                                font.pixelSize: 9
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }

                Rectangle {
                    width: resultColumn.width
                    height: 62
                    radius: 8
                    color: "#10202d"
                    border.width: 1
                    border.color: Theme.border

                    Text {
                        anchors.fill: parent
                        anchors.margins: 14
                        text: String(root.run.notice
                            || "AI-generated analysis is analytical assistance, not Evidence or an independently verified fact.")
                        color: Theme.textMuted
                        font.pixelSize: 9
                        wrapMode: Text.Wrap
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !Boolean(root.run.hasRun) && !analysisBridge.busy

            Text {
                anchors.centerIn: parent
                width: Math.min(parent.width - 80, 620)
                text: desktopBridge.hasCurrentCase
                    ? (Boolean(root.provider.configured)
                        ? "Ready to analyze the selected investigation. The existing deterministic analysis stages run first; OpenAI receives only the bounded RAG context used for the AI summary and conclusions."
                        : "OpenAI is selected but not configured. Add OPENAI_API_KEY to the local .env file, restart OSINTXZ, then return here.")
                    : "Select an investigation to enable Analysis."
                color: Theme.textMuted
                font.pixelSize: 12
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
}

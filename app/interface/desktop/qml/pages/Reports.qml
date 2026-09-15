import QtQuick
import "../components"
import "../theme"

DataWorkspace {
    id: root
    pageKey: "reports"
    eyebrow: "INTELLIGENCE REPORTING"
    title: "Reports"
    subtitle: desktopBridge.hasCurrentCase
        ? "Reports in " + desktopBridge.currentCaseTitle + "."
        : "Stored investigation reports."
    iconSource: "../../assets/icons/document_blue.svg"
    primaryAction: "New Report"
    searchPlaceholder: "Filter reports..."
    sectionTitle: "Report Library"
    contextTitle: "Report Scope"
    emptyTitle: "No reports yet"
    emptyDescription: "Generated investigation reports will appear here."
    recordsInteractive: true
    onRecordActivated: function(recordId) { desktopBridge.openReport(recordId) }
}

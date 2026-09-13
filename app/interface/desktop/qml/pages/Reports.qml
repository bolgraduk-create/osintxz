import QtQuick

DataWorkspace {
    pageKey: "reports"
    eyebrow: "INTELLIGENCE REPORTING"
    title: "Reports"
    subtitle: desktopBridge.currentCaseTitle ? "Reports in " + desktopBridge.currentCaseTitle + "." : "Review reports stored across investigations."
    iconSource: "../../assets/icons/chart.svg"
    primaryAction: "New Report"
    searchPlaceholder: "Filter reports..."
    sectionTitle: "Report Library"
    contextTitle: "Report Scope"
    emptyTitle: desktopBridge.hasCurrentCase ? "No reports for this investigation yet" : "No reports yet"
    emptyDescription: desktopBridge.hasCurrentCase
        ? "Reports created through the existing investigation workflow will appear here."
        : "Reports from stored investigations will appear here."
}

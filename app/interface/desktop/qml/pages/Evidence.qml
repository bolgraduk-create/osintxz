import QtQuick

DataWorkspace {
    pageKey: "evidence"
    eyebrow: "EVIDENCE CONTROL"
    title: "Evidence"
    subtitle: desktopBridge.currentCaseTitle ? "Evidence in " + desktopBridge.currentCaseTitle + "." : "Review evidence stored across investigations."
    iconSource: "../../assets/icons/document_blue.svg"
    primaryAction: "Add Evidence"
    searchPlaceholder: "Filter evidence..."
    sectionTitle: "Evidence Register"
    contextTitle: "Evidence Scope"
}

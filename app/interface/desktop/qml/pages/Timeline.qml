import QtQuick

DataWorkspace {
    pageKey: "timeline"
    eyebrow: "TEMPORAL ANALYSIS"
    title: "Timeline"
    subtitle: desktopBridge.currentCaseTitle ? "Events in " + desktopBridge.currentCaseTitle + "." : "Review stored investigation events."
    iconSource: "../../assets/icons/clock.svg"
    primaryAction: "Add Event"
    searchPlaceholder: "Filter events..."
    sectionTitle: "Investigation Events"
    contextTitle: "Timeline Scope"
}

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
    emptyTitle: desktopBridge.hasCurrentCase ? "No events in this investigation yet" : "No timeline events yet"
    emptyDescription: desktopBridge.hasCurrentCase
        ? "Events recorded for this investigation will appear here in time order."
        : "Timeline events from stored investigations will appear here."
}

import QtQuick

DataWorkspace {
    id: root
    pageKey: "graph"
    eyebrow: "RELATIONSHIP ANALYSIS"
    title: "Graph"
    subtitle: desktopBridge.currentCaseTitle ? "Relationship data for " + desktopBridge.currentCaseTitle + "." : "Open a case to inspect its relationship graph."
    iconSource: "../../assets/icons/graph_blue.svg"
    primaryAction: "New Graph"
    searchPlaceholder: "Filter graph entities..."
    sectionTitle: "Graph Entities"
    contextTitle: "Graph Context"
    emptyTitle: desktopBridge.hasCurrentCase
        ? "No entities in this investigation yet"
        : "No investigation selected"
    emptyDescription: desktopBridge.hasCurrentCase
        ? "Add entities or run an OSINT collection to start building the graph."
        : "Select an investigation to explore its entity graph."
}

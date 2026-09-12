import QtQuick

DataWorkspace {
    pageKey: "search"
    eyebrow: "UNIFIED DISCOVERY"
    title: "Search"
    subtitle: desktopBridge.currentCaseTitle ? "Searching stored intelligence in " + desktopBridge.currentCaseTitle + "." : "Search stored intelligence across investigations."
    iconSource: "../../assets/icons/search.svg"
    primaryAction: "New Search"
    searchPlaceholder: "Enter a query and press Enter..."
    sectionTitle: "Search Results"
    contextTitle: "Search Scope"
}

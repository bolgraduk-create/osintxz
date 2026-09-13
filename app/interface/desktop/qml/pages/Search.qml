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
    emptyTitle: "Search stored intelligence"
    emptyDescription: "Enter a query above and press Enter to search across available investigations."
    filteredEmptyTitle: "No search results"
    filteredEmptyDescription: "No stored intelligence matches this query. Try a different search term."
}

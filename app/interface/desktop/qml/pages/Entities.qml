import QtQuick

DataWorkspace {
    id: root

    property var categoryCounts: desktopBridge.entityCategoryCounts || ({})

    pageKey: "entities"
    eyebrow: "ENTITY INTELLIGENCE"
    title: "Entity Directory"
    subtitle: desktopBridge.currentCaseTitle
        ? "People, organizations and identifiers in " + desktopBridge.currentCaseTitle + "."
        : "Browse people, organizations, profiles, links and identifiers across investigations."
    iconSource: "../../assets/icons/users_cyan.svg"
    primaryAction: "Add Entity"
    searchPlaceholder: "Filter the loaded category by value or type..."
    sectionTitle: desktopBridge.entityCategory === "all"
        ? "All Entities"
        : (String(desktopBridge.entityCategory || "all").charAt(0).toUpperCase()
            + String(desktopBridge.entityCategory || "all").slice(1).replace(/_/g, " "))
    contextTitle: "Entity Scope"
    selectedCategory: desktopBridge.entityCategory
    categoryItems: [
        { key: "all", label: "All", count: Number(root.categoryCounts.all || 0) },
        { key: "people", label: "People", count: Number(root.categoryCounts.people || 0) },
        { key: "organizations", label: "Organizations", count: Number(root.categoryCounts.organizations || 0) },
        { key: "profiles", label: "Profiles", count: Number(root.categoryCounts.profiles || 0) },
        { key: "links", label: "Links", count: Number(root.categoryCounts.links || 0) },
        { key: "contacts", label: "Contacts", count: Number(root.categoryCounts.contacts || 0) },
        { key: "network", label: "Network", count: Number(root.categoryCounts.network || 0) },
        { key: "locations", label: "Locations", count: Number(root.categoryCounts.locations || 0) },
        { key: "documents", label: "Documents", count: Number(root.categoryCounts.documents || 0) },
        { key: "other", label: "Other", count: Number(root.categoryCounts.other || 0) }
    ]
    emptyTitle: desktopBridge.hasCurrentCase ? "No entities in this category" : "No entities in this category yet"
    emptyDescription: desktopBridge.hasCurrentCase
        ? "Run OSINT or add intelligence to this investigation to populate the selected entity category."
        : "Entities from stored investigations will appear here."

    onCategoryRequested: function(categoryKey) {
        desktopBridge.setEntityCategory(categoryKey)
    }

    onRecordActivated: function(recordId) {
        desktopBridge.activateRecord("entities", recordId)
    }
}

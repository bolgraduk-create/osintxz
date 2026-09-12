import QtQuick

DataWorkspace {
    pageKey: "entities"
    eyebrow: "ENTITY INTELLIGENCE"
    title: "Entities"
    subtitle: desktopBridge.currentCaseTitle ? "Entities in " + desktopBridge.currentCaseTitle + "." : "Review entities stored across investigations."
    iconSource: "../../assets/icons/users_cyan.svg"
    primaryAction: "Add Entity"
    searchPlaceholder: "Filter entities by value or type..."
    sectionTitle: "Stored Entities"
    contextTitle: "Entity Scope"
}

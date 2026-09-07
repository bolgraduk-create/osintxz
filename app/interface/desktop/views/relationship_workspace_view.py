"""
Relationship workspace view.

Responsible for:

- displaying entity relationships
- filtering relationships
- showing relationship details
- displaying empty and filtered states
- reacting to application language changes

Does NOT:

- access database
- execute business logic
- analyze relationships
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    Qt,
)

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.interface.desktop.localization import (
    TranslatableMixin,
)

from app.localization import (
    TranslationManager,
    get_translation_manager,
)

from app.interface.desktop.widgets import (
    Badge,
    Card,
    EmptyState,
    SearchBox,
    Section,
    Toolbar,
)


class RelationshipWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Relationship tab workspace.

    The view automatically updates all visible interface text
    when the active application language changes.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self.relationships: list[
            dict[str, Any]
        ] = []

        self.filtered_relationships: list[
            dict[str, Any]
        ] = []

        self._search_text = ""

        self._selected_relationship: (
            dict[str, Any] | None
        ) = None

        self._setup_ui()

        active_translation_manager = (
            translation_manager
            if translation_manager is not None
            else get_translation_manager()
        )

        self.initialize_translations(
            active_translation_manager
        )

        self._update_workspace_state()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create relationship workspace interface.
        """

        self.setObjectName(
            "RelationshipWorkspaceView"
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        self.main_layout.setSpacing(
            16
        )

        self._create_section()
        self._create_toolbar()
        self._create_content()
        self._create_connections()

    def _create_section(
        self,
    ) -> None:
        """
        Create main relationship section.
        """

        self.relationship_section = Section(
            title="Entity Relationships",
            description=(
                "Review connections discovered between investigation "
                "entities and inspect their available metadata."
            ),
            parent=self,
        )

        self.relationship_section.setObjectName(
            "RelationshipSection"
        )

        self.relationship_section.set_variant(
            "default"
        )

        self.relationship_section.set_content_spacing(
            14
        )

        self.relationship_section.set_content_margins(
            0,
            0,
            0,
            0,
        )

        self.relationship_section.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.main_layout.addWidget(
            self.relationship_section,
            1,
        )

    def _create_toolbar(
        self,
    ) -> None:
        """
        Create relationship search and statistics toolbar.
        """

        self.toolbar = Toolbar(
            parent=self.relationship_section
        )

        self.toolbar.setObjectName(
            "RelationshipToolbar"
        )

        self.toolbar.set_variant(
            "default"
        )

        self.search_box = SearchBox(
            placeholder=(
                "Search by type, source, target or identifier..."
            ),
            debounce_interval=200,
            parent=self.toolbar,
        )

        self.search_box.setObjectName(
            "RelationshipSearchBox"
        )

        self.search_box.setMinimumWidth(
            320
        )

        self.search_box.setMaximumWidth(
            680
        )

        self.count_badge = Badge(
            text="0 relationships",
            variant="neutral",
            size="medium",
            outlined=True,
            rounded=True,
            parent=self.toolbar,
        )

        self.count_badge.setObjectName(
            "RelationshipCountBadge"
        )

        self.toolbar.add_left_widget(
            self.search_box,
            stretch=1,
        )

        self.toolbar.add_right_widget(
            self.count_badge
        )

        self.relationship_section.add_widget(
            self.toolbar
        )

    def _create_content(
        self,
    ) -> None:
        """
        Create relationship list, details and empty state.
        """

        self.content_container = QFrame(
            self.relationship_section
        )

        self.content_container.setObjectName(
            "RelationshipContentContainer"
        )

        self.content_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.content_layout = QVBoxLayout(
            self.content_container
        )

        self.content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.content_layout.setSpacing(
            0
        )

        self._create_splitter()
        self._create_empty_state()

        self.relationship_section.add_widget(
            self.content_container,
            stretch=1,
        )

    def _create_splitter(
        self,
    ) -> None:
        """
        Create relationship list and details splitter.
        """

        self.splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self.content_container,
        )

        self.splitter.setObjectName(
            "RelationshipSplitter"
        )

        self.splitter.setChildrenCollapsible(
            False
        )

        self._create_relationship_list()
        self._create_details_card()

        self.splitter.addWidget(
            self.list
        )

        self.splitter.addWidget(
            self.details_card
        )

        self.splitter.setStretchFactor(
            0,
            2,
        )

        self.splitter.setStretchFactor(
            1,
            3,
        )

        self.splitter.setSizes(
            [
                420,
                580,
            ]
        )

        self.content_layout.addWidget(
            self.splitter,
            1,
        )

    def _create_relationship_list(
        self,
    ) -> None:
        """
        Create relationship list.
        """

        self.list = QListWidget(
            self.splitter
        )

        self.list.setObjectName(
            "RelationshipList"
        )

        self.list.setSelectionBehavior(
            QAbstractItemView
            .SelectionBehavior
            .SelectRows
        )

        self.list.setSelectionMode(
            QAbstractItemView
            .SelectionMode
            .SingleSelection
        )

        self.list.setEditTriggers(
            QAbstractItemView
            .EditTrigger
            .NoEditTriggers
        )

        self.list.setAlternatingRowColors(
            True
        )

        self.list.setUniformItemSizes(
            True
        )

        self.list.setVerticalScrollMode(
            QAbstractItemView
            .ScrollMode
            .ScrollPerPixel
        )

        self.list.setHorizontalScrollMode(
            QAbstractItemView
            .ScrollMode
            .ScrollPerPixel
        )

        self.list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def _create_details_card(
        self,
    ) -> None:
        """
        Create selected relationship details panel.
        """

        self.details_card = Card(
            title="Relationship Details",
            subtitle=(
                "Select a relationship to inspect its endpoints, "
                "type and available metadata."
            ),
            parent=self.splitter,
        )

        self.details_card.setObjectName(
            "RelationshipDetailsCard"
        )

        self.details_card.set_variant(
            "default"
        )

        self.details = QPlainTextEdit(
            self.details_card
        )

        self.details.setObjectName(
            "RelationshipDetailsView"
        )

        self.details.setReadOnly(
            True
        )

        self.details.setPlaceholderText(
            "Select a relationship to view its details."
        )

        self.details.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.details_card.add_widget(
            self.details
        )

    def _create_empty_state(
        self,
    ) -> None:
        """
        Create relationship empty state.
        """

        self.empty_state = EmptyState(
            title="No relationships discovered",
            description=(
                "Relationships between investigation entities "
                "will appear here."
            ),
            marker="⇄",
            parent=self.content_container,
        )

        self.empty_state.setObjectName(
            "RelationshipEmptyState"
        )

        self.empty_state.set_variant(
            "panel"
        )

        self.empty_state.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.content_layout.addWidget(
            self.empty_state,
            1,
        )

        self.empty_state.hide()

    def _create_connections(
        self,
    ) -> None:
        """
        Connect relationship workspace interactions.
        """

        self.search_box.search_changed.connect(
            self._filter_relationships
        )

        self.search_box.search_submitted.connect(
            self._filter_relationships
        )

        self.list.currentRowChanged.connect(
            self._show_details_by_row
        )

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply the active application language.
        """

        self.relationship_section.set_title(
            self.translate(
                "relationship.section.title",
                default="Entity Relationships",
            )
        )

        self.relationship_section.set_description(
            self.translate(
                "relationship.section.description",
                default=(
                    "Review connections discovered between investigation "
                    "entities and inspect their available metadata."
                ),
            )
        )

        self.search_box.set_placeholder(
            self.translate(
                "relationship.search.placeholder",
                default=(
                    "Search by type, source, target or identifier..."
                ),
            )
        )

        self.details_card.set_title(
            self.translate(
                "relationship.details.title",
                default="Relationship Details",
            )
        )

        self.details_card.set_subtitle(
            self.translate(
                "relationship.details.subtitle",
                default=(
                    "Select a relationship to inspect its endpoints, "
                    "type and available metadata."
                ),
            )
        )

        self.details.setPlaceholderText(
            self.translate(
                "relationship.details.placeholder",
                default=(
                    "Select a relationship to view its details."
                ),
            )
        )

        current_row = (
            self.list.currentRow()
        )

        self._populate_list()

        if (
            0
            <= current_row
            < len(self.filtered_relationships)
        ):

            self.list.setCurrentRow(
                current_row
            )

        self._update_workspace_state()
        self._refresh_selected_relationship_details()

            # ==========================================================
    # Public API
    # ==========================================================

    def set_relationships(
        self,
        relationships: list,
    ) -> None:
        """
        Display relationships.
        """

        normalized_relationships = [
            relationship
            for relationship in relationships
            if isinstance(
                relationship,
                dict,
            )
        ] if isinstance(
            relationships,
            list,
        ) else []

        self.relationships = (
            normalized_relationships
        )

        self._selected_relationship = None

        self.details.clear()

        self.list.clearSelection()

        self._apply_filter()

    def clear_relationships(
        self,
    ) -> None:
        """
        Remove all displayed relationships.
        """

        self.relationships = []

        self.filtered_relationships = []

        self._selected_relationship = None

        self.list.clear()

        self.details.clear()

        self._update_workspace_state()

    # ==========================================================
    # Filtering
    # ==========================================================

    def _filter_relationships(
        self,
        text: str,
    ) -> None:
        """
        Filter visible relationships.
        """

        normalized_text = (
            text.strip().casefold()
        )

        if (
            normalized_text
            == self._search_text
        ):

            return

        self._search_text = (
            normalized_text
        )

        self._selected_relationship = None

        self.details.clear()

        self._apply_filter()

    def _apply_filter(
        self,
    ) -> None:
        """
        Apply current relationship search filter.
        """

        if not self._search_text:

            self.filtered_relationships = list(
                self.relationships
            )

        else:

            self.filtered_relationships = [
                relationship
                for relationship in self.relationships
                if self._matches_search(
                    relationship
                )
            ]

        self._selected_relationship = None

        self._populate_list()

        self._update_workspace_state()

        if self.filtered_relationships:

            self.list.setCurrentRow(
                0
            )

    def _matches_search(
        self,
        relationship: dict[str, Any],
    ) -> bool:
        """
        Check whether a relationship matches current search.
        """

        searchable_values = (
            relationship.get("type"),
            relationship.get("source"),
            relationship.get("target"),
            relationship.get("source_id"),
            relationship.get("target_id"),
            relationship.get("id"),
            relationship.get("description"),
            relationship.get("label"),
            relationship.get("source_type"),
            relationship.get("target_type"),
        )

        combined_text = " ".join(
            str(
                value
            )
            for value in searchable_values
            if value is not None
        ).casefold()

        return (
            self._search_text
            in combined_text
        )

    def _populate_list(
        self,
    ) -> None:
        """
        Fill list with currently visible relationships.
        """

        self.list.clear()

        unknown_type = self.translate(
            "relationship.item.unknown_type",
            default="Unknown",
        )

        for relationship in self.filtered_relationships:

            relationship_type = str(
                relationship.get(
                    "type"
                )
                or unknown_type
            )

            source = self._get_endpoint_text(
                relationship=relationship,
                endpoint="source",
            )

            target = self._get_endpoint_text(
                relationship=relationship,
                endpoint="target",
            )

            item = QListWidgetItem(
                (
                    f"{relationship_type.upper()}  |  "
                    f"{source}  →  {target}"
                )
            )

            item.setToolTip(
                self._build_item_tooltip(
                    relationship
                )
            )

            self.list.addItem(
                item
            )

    # ==========================================================
    # Workspace state
    # ==========================================================

    def _update_workspace_state(
        self,
    ) -> None:
        """
        Update counters and empty states.
        """

        total_count = len(
            self.relationships
        )

        visible_count = len(
            self.filtered_relationships
        )

        self._update_count_badge(
            visible_count=visible_count,
            total_count=total_count,
        )

        has_visible_relationships = (
            visible_count > 0
        )

        self.splitter.setVisible(
            has_visible_relationships
        )

        self.empty_state.setVisible(
            not has_visible_relationships
        )

        if has_visible_relationships:

            return

        if (
            total_count > 0
            and self._search_text
        ):

            self.empty_state.set_marker(
                "⌕"
            )

            self.empty_state.set_title(
                self.translate(
                    "relationship.empty.search.title",
                    default="No matching relationships",
                )
            )

            self.empty_state.set_description(
                self.translate(
                    "relationship.empty.search.description",
                    default=(
                        "No relationships match the current search. "
                        "Try another type, source, target or identifier."
                    ),
                )
            )

            return

        self.empty_state.set_marker(
            "⇄"
        )

        self.empty_state.set_title(
            self.translate(
                "relationship.empty.title",
                default="No relationships discovered",
            )
        )

        self.empty_state.set_description(
            self.translate(
                "relationship.empty.description",
                default=(
                    "Relationships between investigation entities "
                    "will appear here."
                ),
            )
        )

    def _update_count_badge(
        self,
        visible_count: int,
        total_count: int,
    ) -> None:
        """
        Update relationship count badge.
        """

        if visible_count == total_count:

            if total_count == 1:

                badge_text = self.translate(
                    "relationship.count.single",
                    default="{count} relationship",
                    count=total_count,
                )

            else:

                badge_text = self.translate(
                    "relationship.count.multiple",
                    default="{count} relationships",
                    count=total_count,
                )

            self.count_badge.set_text(
                badge_text
            )

            return

        self.count_badge.set_text(
            self.translate(
                "relationship.count.filtered",
                default=(
                    "{visible} of {total} relationships"
                ),
                visible=visible_count,
                total=total_count,
            )
        )

            # ==========================================================
    # Details
    # ==========================================================

    def _show_details_by_row(
        self,
        index: int,
    ) -> None:
        """
        Display selected relationship details.
        """

        if (
            index < 0
            or index >= len(
                self.filtered_relationships
            )
        ):

            self._selected_relationship = None

            self.details.clear()

            return

        self._selected_relationship = (
            self.filtered_relationships[
                index
            ]
        )

        self._refresh_selected_relationship_details()

    def _refresh_selected_relationship_details(
        self,
    ) -> None:
        """
        Refresh selected relationship after language change.
        """

        if self._selected_relationship is None:

            self.details.clear()

            return

        self.details.setPlainText(
            self._build_details_text(
                self._selected_relationship
            )
        )

    @staticmethod
    def _get_endpoint_text(
        relationship: dict[str, Any],
        endpoint: str,
    ) -> str:
        """
        Extract readable relationship endpoint.
        """

        value = relationship.get(
            endpoint
        )

        if isinstance(
            value,
            dict,
        ):

            endpoint_value = (
                value.get("value")
                or value.get("name")
                or value.get("label")
                or value.get("id")
            )

            return str(
                endpoint_value
                or "?"
            )

        if value is not None:

            return str(
                value
            )

        endpoint_id = relationship.get(
            f"{endpoint}_id"
        )

        return str(
            endpoint_id
            or "?"
        )

    def _build_item_tooltip(
        self,
        relationship: dict[str, Any],
    ) -> str:
        """
        Build compact relationship tooltip.
        """

        relationship_type = str(
            relationship.get("type")
            or self.translate(
                "relationship.item.unknown_type",
                default="Unknown",
            )
        )

        source = self._get_endpoint_text(
            relationship,
            "source",
        )

        target = self._get_endpoint_text(
            relationship,
            "target",
        )

        confidence = relationship.get(
            "confidence"
        )

        tooltip_parts = [

            (
                f"{self.translate('relationship.details.label.type', default='Type')}: "
                f"{relationship_type}"
            ),

            (
                f"{self.translate('relationship.details.label.source', default='Source')}: "
                f"{source}"
            ),

            (
                f"{self.translate('relationship.details.label.target', default='Target')}: "
                f"{target}"
            ),

        ]

        if confidence is not None:

            tooltip_parts.append(

                (
                    f"{self.translate('relationship.details.label.confidence', default='Confidence')}: "
                    f"{confidence}"
                )

            )

        return "\n".join(
            tooltip_parts
        )

    def _build_details_text(
        self,
        relationship: dict[str, Any],
    ) -> str:
        """
        Build readable relationship details.
        """

        unavailable = self.translate(
            "relationship.details.unavailable",
            default="Unavailable",
        )

        relationship_type = str(
            relationship.get("type")
            or unavailable
        )

        source = self._get_endpoint_text(
            relationship,
            "source",
        )

        target = self._get_endpoint_text(
            relationship,
            "target",
        )

        details = [

            (
                self.translate(
                    "relationship.details.label.type",
                    default="Type",
                ),
                relationship_type,
            ),

            (
                self.translate(
                    "relationship.details.label.source",
                    default="Source",
                ),
                source,
            ),

            (
                self.translate(
                    "relationship.details.label.target",
                    default="Target",
                ),
                target,
            ),

        ]

        fields = [

            (
                "id",
                "relationship.details.label.id",
                "ID",
            ),

            (
                "source_id",
                "relationship.details.label.source_id",
                "Source ID",
            ),

            (
                "target_id",
                "relationship.details.label.target_id",
                "Target ID",
            ),

            (
                "source_type",
                "relationship.details.label.source_type",
                "Source Type",
            ),

            (
                "target_type",
                "relationship.details.label.target_type",
                "Target Type",
            ),

            (
                "label",
                "relationship.details.label.label",
                "Label",
            ),

            (
                "description",
                "relationship.details.label.description",
                "Description",
            ),

            (
                "confidence",
                "relationship.details.label.confidence",
                "Confidence",
            ),

            (
                "weight",
                "relationship.details.label.weight",
                "Weight",
            ),

            (
                "source_name",
                "relationship.details.label.data_source",
                "Data Source",
            ),

            (
                "created_at",
                "relationship.details.label.created_at",
                "Created At",
            ),

            (
                "updated_at",
                "relationship.details.label.updated_at",
                "Updated At",
            ),

        ]

        for field_name, key, default in fields:

            value = relationship.get(
                field_name
            )

            if value in (
                None,
                "",
            ):

                continue

            details.append(

                (
                    self.translate(
                        key,
                        default=default,
                    ),
                    str(value),
                )

            )

        return "\n\n".join(

            f"{title}\n{value}"

            for title, value in details

        )
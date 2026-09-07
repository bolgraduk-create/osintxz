"""
Entity workspace view.

Responsible for:

- displaying extracted entities
- filtering entities
- showing entity details
- displaying empty and filtered states
- reacting to application language changes

Does NOT:

- access database
- execute business logic
- resolve entities
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


class EntityWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Entity tab workspace.

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

        self.entities: list[
            dict[str, Any]
        ] = []

        self.filtered_entities: list[
            dict[str, Any]
        ] = []

        self._search_text = ""

        self._selected_entity: (
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
        Create entity workspace interface.
        """

        self.setObjectName(
            "EntityWorkspaceView"
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
        Create main entity section.
        """

        self.entity_section = Section(
            title="Extracted Entities",
            description=(
                "Review people, accounts, locations, organizations "
                "and other entities extracted from investigation data."
            ),
            parent=self,
        )

        self.entity_section.setObjectName(
            "EntitySection"
        )

        self.entity_section.set_variant(
            "default"
        )

        self.entity_section.set_content_spacing(
            14
        )

        self.entity_section.set_content_margins(
            0,
            0,
            0,
            0,
        )

        self.entity_section.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.main_layout.addWidget(
            self.entity_section,
            1,
        )

    def _create_toolbar(
        self,
    ) -> None:
        """
        Create search and statistics toolbar.
        """

        self.toolbar = Toolbar(
            parent=self.entity_section
        )

        self.toolbar.setObjectName(
            "EntityToolbar"
        )

        self.toolbar.set_variant(
            "default"
        )

        self.search_box = SearchBox(
            placeholder=(
                "Search by type, value, label or identifier..."
            ),
            debounce_interval=200,
            parent=self.toolbar,
        )

        self.search_box.setObjectName(
            "EntitySearchBox"
        )

        self.search_box.setMinimumWidth(
            320
        )

        self.search_box.setMaximumWidth(
            680
        )

        self.count_badge = Badge(
            text="0 entities",
            variant="neutral",
            size="medium",
            outlined=True,
            rounded=True,
            parent=self.toolbar,
        )

        self.count_badge.setObjectName(
            "EntityCountBadge"
        )

        self.toolbar.add_left_widget(
            self.search_box,
            stretch=1,
        )

        self.toolbar.add_right_widget(
            self.count_badge
        )

        self.entity_section.add_widget(
            self.toolbar
        )

    def _create_content(
        self,
    ) -> None:
        """
        Create entity list, details and empty state.
        """

        self.content_container = QFrame(
            self.entity_section
        )

        self.content_container.setObjectName(
            "EntityContentContainer"
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

        self.entity_section.add_widget(
            self.content_container,
            stretch=1,
        )

    def _create_splitter(
        self,
    ) -> None:
        """
        Create entity list and details splitter.
        """

        self.splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self.content_container,
        )

        self.splitter.setObjectName(
            "EntitySplitter"
        )

        self.splitter.setChildrenCollapsible(
            False
        )

        self._create_entity_list()
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
                380,
                620,
            ]
        )

        self.content_layout.addWidget(
            self.splitter,
            1,
        )

    def _create_entity_list(
        self,
    ) -> None:
        """
        Create extracted entity list.
        """

        self.list = QListWidget(
            self.splitter
        )

        self.list.setObjectName(
            "EntityList"
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
        Create selected entity details panel.
        """

        self.details_card = Card(
            title="Entity Details",
            subtitle=(
                "Select an entity to inspect its extracted value, "
                "type and available metadata."
            ),
            parent=self.splitter,
        )

        self.details_card.setObjectName(
            "EntityDetailsCard"
        )

        self.details_card.set_variant(
            "default"
        )

        self.details = QPlainTextEdit(
            self.details_card
        )

        self.details.setObjectName(
            "EntityDetailsView"
        )

        self.details.setReadOnly(
            True
        )

        self.details.setPlaceholderText(
            "Select an entity to view its details."
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
        Create entity empty state.
        """

        self.empty_state = EmptyState(
            title="No entities extracted",
            description=(
                "Entities extracted from imported investigation data "
                "will appear here."
            ),
            marker="◎",
            parent=self.content_container,
        )

        self.empty_state.setObjectName(
            "EntityEmptyState"
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
        Connect entity workspace interactions.
        """

        self.search_box.search_changed.connect(
            self._filter_entities
        )

        self.search_box.search_submitted.connect(
            self._filter_entities
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

        self.entity_section.set_title(
            self.translate(
                "entity.section.title",
                default="Extracted Entities",
            )
        )

        self.entity_section.set_description(
            self.translate(
                "entity.section.description",
                default=(
                    "Review people, accounts, locations, organizations "
                    "and other entities extracted from investigation data."
                ),
            )
        )

        self.search_box.set_placeholder(
            self.translate(
                "entity.search.placeholder",
                default=(
                    "Search by type, value, label or identifier..."
                ),
            )
        )

        self.details_card.set_title(
            self.translate(
                "entity.details.title",
                default="Entity Details",
            )
        )

        self.details_card.set_subtitle(
            self.translate(
                "entity.details.subtitle",
                default=(
                    "Select an entity to inspect its extracted value, "
                    "type and available metadata."
                ),
            )
        )

        self.details.setPlaceholderText(
            self.translate(
                "entity.details.placeholder",
                default=(
                    "Select an entity to view its details."
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
            < len(self.filtered_entities)
        ):

            self.list.setCurrentRow(
                current_row
            )

        self._update_workspace_state()
        self._refresh_selected_entity_details()

    # ==========================================================
    # Public API
    # ==========================================================

    def set_entities(
        self,
        entities: list,
    ) -> None:
        """
        Display entities.
        """

        normalized_entities = [
            entity
            for entity in entities
            if isinstance(
                entity,
                dict,
            )
        ] if isinstance(
            entities,
            list,
        ) else []

        self.entities = (
            normalized_entities
        )

        self._selected_entity = None

        self.details.clear()

        self.list.clearSelection()

        self._apply_filter()

    def clear_entities(
        self,
    ) -> None:
        """
        Remove all displayed entities.
        """

        self.entities = []
        self.filtered_entities = []

        self._selected_entity = None

        self.list.clear()
        self.details.clear()

        self._update_workspace_state()

    # ==========================================================
    # Filtering
    # ==========================================================

    def _filter_entities(
        self,
        text: str,
    ) -> None:
        """
        Filter visible entities.
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

        self._selected_entity = None

        self.details.clear()

        self._apply_filter()

    def _apply_filter(
        self,
    ) -> None:
        """
        Apply current entity search filter.
        """

        if not self._search_text:

            self.filtered_entities = list(
                self.entities
            )

        else:

            self.filtered_entities = [
                entity
                for entity in self.entities
                if self._matches_search(
                    entity
                )
            ]

        self._selected_entity = None

        self._populate_list()

        self._update_workspace_state()

        if self.filtered_entities:

            self.list.setCurrentRow(
                0
            )

    def _matches_search(
        self,
        entity: dict[str, Any],
    ) -> bool:
        """
        Check whether an entity matches current search.
        """

        searchable_values = (
            entity.get("type"),
            entity.get("value"),
            entity.get("label"),
            entity.get("name"),
            entity.get("id"),
            entity.get("normalized_value"),
            entity.get("description"),
            entity.get("source"),
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
        Fill list with currently visible entities.
        """

        self.list.clear()

        unknown_type = self.translate(
            "entity.item.unknown_type",
            default="unknown",
        )

        unnamed_entity = self.translate(
            "entity.item.unnamed",
            default="Unnamed entity",
        )

        for entity in self.filtered_entities:

            entity_type = str(
                entity.get(
                    "type"
                )
                or unknown_type
            )

            entity_value = str(
                entity.get(
                    "value"
                )
                or entity.get(
                    "name"
                )
                or entity.get(
                    "label"
                )
                or unnamed_entity
            )

            item = QListWidgetItem(
                (
                    f"{entity_type.upper()}  |  "
                    f"{entity_value}"
                )
            )

            item.setToolTip(
                self._build_item_tooltip(
                    entity
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
            self.entities
        )

        visible_count = len(
            self.filtered_entities
        )

        self._update_count_badge(
            visible_count=visible_count,
            total_count=total_count,
        )

        has_visible_entities = (
            visible_count > 0
        )

        self.splitter.setVisible(
            has_visible_entities
        )

        self.empty_state.setVisible(
            not has_visible_entities
        )

        if has_visible_entities:

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
                    "entity.empty.search.title",
                    default="No matching entities",
                )
            )

            self.empty_state.set_description(
                self.translate(
                    "entity.empty.search.description",
                    default=(
                        "No entities match the current search. "
                        "Try another type, value, label or identifier."
                    ),
                )
            )

            return

        self.empty_state.set_marker(
            "◎"
        )

        self.empty_state.set_title(
            self.translate(
                "entity.empty.title",
                default="No entities extracted",
            )
        )

        self.empty_state.set_description(
            self.translate(
                "entity.empty.description",
                default=(
                    "Entities extracted from imported investigation data "
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
        Update entity count badge.
        """

        if visible_count == total_count:

            if total_count == 1:

                badge_text = self.translate(
                    "entity.count.single",
                    default="{count} entity",
                    count=total_count,
                )

            else:

                badge_text = self.translate(
                    "entity.count.multiple",
                    default="{count} entities",
                    count=total_count,
                )

            self.count_badge.set_text(
                badge_text
            )

            return

        self.count_badge.set_text(
            self.translate(
                "entity.count.filtered",
                default=(
                    "{visible} of {total} entities"
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
        Display selected entity details.
        """

        if index < 0:

            self._selected_entity = None

            self.details.clear()

            return

        if index >= len(
            self.filtered_entities
        ):

            self._selected_entity = None

            self.details.clear()

            return

        self._selected_entity = (
            self.filtered_entities[
                index
            ]
        )

        self._refresh_selected_entity_details()

    def _refresh_selected_entity_details(
        self,
    ) -> None:
        """
        Refresh selected entity details using active language.
        """

        if self._selected_entity is None:

            return

        self.details.setPlainText(
            self._build_details_text(
                self._selected_entity
            )
        )

    def _build_item_tooltip(
        self,
        entity: dict[str, Any],
    ) -> str:
        """
        Build compact entity tooltip.
        """

        unknown_type = self.translate(
            "entity.item.unknown_type",
            default="unknown",
        )

        unnamed_entity = self.translate(
            "entity.item.unnamed",
            default="Unnamed entity",
        )

        entity_type = str(
            entity.get(
                "type"
            )
            or unknown_type
        )

        entity_value = str(
            entity.get(
                "value"
            )
            or entity.get(
                "name"
            )
            or entity.get(
                "label"
            )
            or unnamed_entity
        )

        normalized_value = str(
            entity.get(
                "normalized_value"
            )
            or ""
        )

        type_label = self.translate(
            "entity.details.label.type",
            default="Type",
        )

        value_label = self.translate(
            "entity.details.label.value",
            default="Value",
        )

        normalized_label = self.translate(
            "entity.details.label.normalized_value",
            default="Normalized",
        )

        tooltip_parts = [
            f"{type_label}: {entity_type}",
            f"{value_label}: {entity_value}",
        ]

        if normalized_value:

            tooltip_parts.append(
                (
                    f"{normalized_label}: "
                    f"{normalized_value}"
                )
            )

        return "\n".join(
            tooltip_parts
        )

    def _build_details_text(
        self,
        entity: dict[str, Any],
    ) -> str:
        """
        Build readable entity details.
        """

        unavailable = self.translate(
            "entity.details.unavailable",
            default="Unavailable",
        )

        entity_type = str(
            entity.get(
                "type"
            )
            or ""
        )

        entity_value = str(
            entity.get(
                "value"
            )
            or ""
        )

        entity_id = str(
            entity.get(
                "id"
            )
            or ""
        )

        label = str(
            entity.get(
                "label"
            )
            or ""
        )

        name = str(
            entity.get(
                "name"
            )
            or ""
        )

        normalized_value = str(
            entity.get(
                "normalized_value"
            )
            or ""
        )

        description = str(
            entity.get(
                "description"
            )
            or ""
        )

        source = str(
            entity.get(
                "source"
            )
            or ""
        )

        confidence = str(
            entity.get(
                "confidence"
            )
            or ""
        )

        created_at = str(
            entity.get(
                "created_at"
            )
            or ""
        )

        type_label = self.translate(
            "entity.details.label.type",
            default="Type",
        )

        value_label = self.translate(
            "entity.details.label.value",
            default="Value",
        )

        id_label = self.translate(
            "entity.details.label.id",
            default="ID",
        )

        label_label = self.translate(
            "entity.details.label.label",
            default="Label",
        )

        name_label = self.translate(
            "entity.details.label.name",
            default="Name",
        )

        normalized_value_label = self.translate(
            "entity.details.label.normalized_value",
            default="Normalized Value",
        )

        description_label = self.translate(
            "entity.details.label.description",
            default="Description",
        )

        source_label = self.translate(
            "entity.details.label.source",
            default="Source",
        )

        confidence_label = self.translate(
            "entity.details.label.confidence",
            default="Confidence",
        )

        created_at_label = self.translate(
            "entity.details.label.created_at",
            default="Created At",
        )

        details_parts = [
            (
                f"{type_label}\n"
                f"{entity_type or unavailable}"
            ),
            (
                f"{value_label}\n"
                f"{entity_value or name or label or unavailable}"
            ),
            (
                f"{id_label}\n"
                f"{entity_id or unavailable}"
            ),
        ]

        if label:

            details_parts.append(
                (
                    f"{label_label}\n"
                    f"{label}"
                )
            )

        if name:

            details_parts.append(
                (
                    f"{name_label}\n"
                    f"{name}"
                )
            )

        if normalized_value:

            details_parts.append(
                (
                    f"{normalized_value_label}\n"
                    f"{normalized_value}"
                )
            )

        if description:

            details_parts.append(
                (
                    f"{description_label}\n"
                    f"{description}"
                )
            )

        if source:

            details_parts.append(
                (
                    f"{source_label}\n"
                    f"{source}"
                )
            )

        if confidence:

            details_parts.append(
                (
                    f"{confidence_label}\n"
                    f"{confidence}"
                )
            )

        if created_at:

            details_parts.append(
                (
                    f"{created_at_label}\n"
                    f"{created_at}"
                )
            )

        return "\n\n".join(
            details_parts
        )
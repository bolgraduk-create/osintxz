"""
Timeline workspace view.

Responsible for:

- displaying investigation timeline events
- filtering timeline events
- showing event details
- displaying empty and filtered states
- reacting to application language changes

Does NOT:

- access database
- execute business logic
- analyze events
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


class TimelineWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Timeline tab workspace.

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

        self.events: list[
            dict[str, Any]
        ] = []

        self.filtered_events: list[
            dict[str, Any]
        ] = []

        self._search_text = ""

        self._selected_event: (
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
        Create timeline workspace interface.
        """

        self.setObjectName(
            "TimelineWorkspaceView"
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
        Create main timeline section.
        """

        self.timeline_section = Section(
            title="Investigation Timeline",
            description=(
                "Review investigation events in chronological order "
                "and inspect their available details."
            ),
            parent=self,
        )

        self.timeline_section.setObjectName(
            "TimelineSection"
        )

        self.timeline_section.set_variant(
            "default"
        )

        self.timeline_section.set_content_spacing(
            14
        )

        self.timeline_section.set_content_margins(
            0,
            0,
            0,
            0,
        )

        self.timeline_section.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.main_layout.addWidget(
            self.timeline_section,
            1,
        )

    def _create_toolbar(
        self,
    ) -> None:
        """
        Create timeline search and statistics toolbar.
        """

        self.toolbar = Toolbar(
            parent=self.timeline_section
        )

        self.toolbar.setObjectName(
            "TimelineToolbar"
        )

        self.toolbar.set_variant(
            "default"
        )

        self.search_box = SearchBox(
            placeholder=(
                "Search by date, title, type, description or identifier..."
            ),
            debounce_interval=200,
            parent=self.toolbar,
        )

        self.search_box.setObjectName(
            "TimelineSearchBox"
        )

        self.search_box.setMinimumWidth(
            320
        )

        self.search_box.setMaximumWidth(
            680
        )

        self.count_badge = Badge(
            text="0 events",
            variant="neutral",
            size="medium",
            outlined=True,
            rounded=True,
            parent=self.toolbar,
        )

        self.count_badge.setObjectName(
            "TimelineCountBadge"
        )

        self.toolbar.add_left_widget(
            self.search_box,
            stretch=1,
        )

        self.toolbar.add_right_widget(
            self.count_badge
        )

        self.timeline_section.add_widget(
            self.toolbar
        )

    def _create_content(
        self,
    ) -> None:
        """
        Create timeline list, details and empty state.
        """

        self.content_container = QFrame(
            self.timeline_section
        )

        self.content_container.setObjectName(
            "TimelineContentContainer"
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

        self.timeline_section.add_widget(
            self.content_container,
            stretch=1,
        )

    def _create_splitter(
        self,
    ) -> None:
        """
        Create event list and details splitter.
        """

        self.splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self.content_container,
        )

        self.splitter.setObjectName(
            "TimelineSplitter"
        )

        self.splitter.setChildrenCollapsible(
            False
        )

        self._create_event_list()
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

    def _create_event_list(
        self,
    ) -> None:
        """
        Create timeline event list.
        """

        self.list = QListWidget(
            self.splitter
        )

        self.list.setObjectName(
            "TimelineEventList"
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
        Create selected event details panel.
        """

        self.details_card = Card(
            title="Timeline Event Details",
            subtitle=(
                "Select an event to inspect its date, type, "
                "description and related metadata."
            ),
            parent=self.splitter,
        )

        self.details_card.setObjectName(
            "TimelineEventDetailsCard"
        )

        self.details_card.set_variant(
            "default"
        )

        self.details = QPlainTextEdit(
            self.details_card
        )

        self.details.setObjectName(
            "TimelineEventDetailsView"
        )

        self.details.setReadOnly(
            True
        )

        self.details.setPlaceholderText(
            "Select a timeline event to view its details."
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
        Create timeline empty state.
        """

        self.empty_state = EmptyState(
            title="No timeline events",
            description=(
                "Chronological events connected to this investigation "
                "will appear here."
            ),
            marker="◷",
            parent=self.content_container,
        )

        self.empty_state.setObjectName(
            "TimelineEmptyState"
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
        Connect timeline workspace interactions.
        """

        self.search_box.search_changed.connect(
            self._filter_events
        )

        self.search_box.search_submitted.connect(
            self._filter_events
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

        self.timeline_section.set_title(
            self.translate(
                "timeline.section.title",
                default="Investigation Timeline",
            )
        )

        self.timeline_section.set_description(
            self.translate(
                "timeline.section.description",
                default=(
                    "Review investigation events in chronological order "
                    "and inspect their available details."
                ),
            )
        )

        self.search_box.set_placeholder(
            self.translate(
                "timeline.search.placeholder",
                default=(
                    "Search by date, title, type, description or identifier..."
                ),
            )
        )

        self.details_card.set_title(
            self.translate(
                "timeline.details.title",
                default="Timeline Event Details",
            )
        )

        self.details_card.set_subtitle(
            self.translate(
                "timeline.details.subtitle",
                default=(
                    "Select an event to inspect its date, type, "
                    "description and related metadata."
                ),
            )
        )

        self.details.setPlaceholderText(
            self.translate(
                "timeline.details.placeholder",
                default=(
                    "Select a timeline event to view its details."
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
            < len(self.filtered_events)
        ):

            self.list.setCurrentRow(
                current_row
            )

        self._update_workspace_state()
        self._refresh_selected_event_details()

            # ==========================================================
    # Public API
    # ==========================================================

    def set_events(
        self,
        events: list,
    ) -> None:
        """
        Display timeline events.
        """

        normalized_events = [
            event
            for event in events
            if isinstance(
                event,
                dict,
            )
        ] if isinstance(
            events,
            list,
        ) else []

        self.events = sorted(
            normalized_events,
            key=self._event_sort_key,
        )

        self._selected_event = None

        self.details.clear()

        self.list.clearSelection()

        self._apply_filter()

    def clear_events(
        self,
    ) -> None:
        """
        Remove all displayed timeline events.
        """

        self.events = []

        self.filtered_events = []

        self._selected_event = None

        self.list.clear()

        self.details.clear()

        self._update_workspace_state()

    # ==========================================================
    # Filtering
    # ==========================================================

    def _filter_events(
        self,
        text: str,
    ) -> None:
        """
        Filter visible timeline events.
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

        self._selected_event = None

        self.details.clear()

        self._apply_filter()

    def _apply_filter(
        self,
    ) -> None:
        """
        Apply current timeline search filter.
        """

        if not self._search_text:

            self.filtered_events = list(
                self.events
            )

        else:

            self.filtered_events = [

                event

                for event in self.events

                if self._matches_search(
                    event
                )

            ]

        self._selected_event = None

        self._populate_list()

        self._update_workspace_state()

        if self.filtered_events:

            self.list.setCurrentRow(
                0
            )

    def _matches_search(
        self,
        event: dict[str, Any],
    ) -> bool:
        """
        Check whether an event matches current search.
        """

        searchable_values = (

            event.get("date"),
            event.get("event_date"),
            event.get("occurred_at"),
            event.get("timestamp"),

            event.get("title"),

            event.get("type"),
            event.get("event_type"),

            event.get("description"),
            event.get("details"),

            event.get("id"),

            event.get("source"),
            event.get("source_id"),

            event.get("entity"),
            event.get("entity_id"),

        )

        combined_text = " ".join(

            str(value)

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
        Fill list with currently visible events.
        """

        self.list.clear()

        unknown_date = self.translate(
            "timeline.item.unknown_date",
            default="Unknown date",
        )

        default_title = self.translate(
            "timeline.item.default_title",
            default="Timeline event",
        )

        for event in self.filtered_events:

            event_date = self._get_event_date(
                event
            )

            title = str(

                event.get("title")

                or event.get("type")

                or event.get("event_type")

                or default_title

            )

            item = QListWidgetItem(

                (
                    f"{event_date or unknown_date}"
                    f"  |  {title}"
                )

            )

            item.setToolTip(

                self._build_item_tooltip(
                    event
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
            self.events
        )

        visible_count = len(
            self.filtered_events
        )

        self._update_count_badge(

            visible_count=visible_count,

            total_count=total_count,

        )

        has_visible_events = (
            visible_count > 0
        )

        self.splitter.setVisible(
            has_visible_events
        )

        self.empty_state.setVisible(
            not has_visible_events
        )

        if has_visible_events:

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

                    "timeline.empty.search.title",

                    default="No matching timeline events",

                )

            )

            self.empty_state.set_description(

                self.translate(

                    "timeline.empty.search.description",

                    default=(
                        "No timeline events match the current search. "
                        "Try another date, title, type or identifier."
                    ),

                )

            )

            return

        self.empty_state.set_marker(
            "◷"
        )

        self.empty_state.set_title(

            self.translate(

                "timeline.empty.title",

                default="No timeline events",

            )

        )

        self.empty_state.set_description(

            self.translate(

                "timeline.empty.description",

                default=(
                    "Chronological events connected to this investigation "
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
        Update timeline event count badge.
        """

        if visible_count == total_count:

            if total_count == 1:

                badge_text = self.translate(

                    "timeline.count.single",

                    default="{count} event",

                    count=total_count,

                )

            else:

                badge_text = self.translate(

                    "timeline.count.multiple",

                    default="{count} events",

                    count=total_count,

                )

            self.count_badge.set_text(
                badge_text
            )

            return

        self.count_badge.set_text(

            self.translate(

                "timeline.count.filtered",

                default="{visible} of {total} events",

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
        Display selected timeline event details.
        """

        if (
            index < 0
            or index >= len(
                self.filtered_events
            )
        ):

            self._selected_event = None

            self.details.clear()

            return

        self._selected_event = (
            self.filtered_events[
                index
            ]
        )

        self._refresh_selected_event_details()

    def _refresh_selected_event_details(
        self,
    ) -> None:
        """
        Refresh selected event after language change.
        """

        if self._selected_event is None:

            self.details.clear()

            return

        self.details.setPlainText(
            self._build_details_text(
                self._selected_event
            )
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _get_event_date(
        event: dict[str, Any],
    ) -> str:
        """
        Return the first available event date field.
        """

        value = (
            event.get("date")
            or event.get("event_date")
            or event.get("occurred_at")
            or event.get("timestamp")
            or event.get("created_at")
            or ""
        )

        return str(
            value
        )

    @classmethod
    def _event_sort_key(
        cls,
        event: dict[str, Any],
    ) -> str:
        """
        Build stable chronological sort key.
        """

        return cls._get_event_date(
            event
        )

    def _build_item_tooltip(
        self,
        event: dict[str, Any],
    ) -> str:
        """
        Build compact timeline event tooltip.
        """

        event_date = self._get_event_date(
            event
        )

        title = str(
            event.get("title")
            or self.translate(
                "timeline.item.default_title",
                default="Timeline event",
            )
        )

        event_type = str(
            event.get("type")
            or event.get("event_type")
            or ""
        )

        description = str(
            event.get("description")
            or event.get("details")
            or ""
        )

        compact_description = " ".join(
            description.split()
        )

        if len(
            compact_description
        ) > 180:

            compact_description = (
                compact_description[:180]
                + "..."
            )

        tooltip_parts = [

            (
                f"{self.translate('timeline.details.label.date', default='Date')}: "
                f"{event_date or self.translate('timeline.item.unknown_date', default='Unknown')}"
            ),

            (
                f"{self.translate('timeline.details.label.title', default='Title')}: "
                f"{title}"
            ),

        ]

        if event_type:

            tooltip_parts.append(

                (
                    f"{self.translate('timeline.details.label.type', default='Type')}: "
                    f"{event_type}"
                )

            )

        if compact_description:

            tooltip_parts.append(

                (
                    f"{self.translate('timeline.details.label.description', default='Description')}: "
                    f"{compact_description}"
                )

            )

        return "\n".join(
            tooltip_parts
        )

    def _build_details_text(
        self,
        event: dict[str, Any],
    ) -> str:
        """
        Build readable timeline event details.
        """

        unavailable = self.translate(
            "timeline.details.unavailable",
            default="Unavailable",
        )

        details = [

            (
                self.translate(
                    "timeline.details.label.date",
                    default="Date",
                ),
                self._get_event_date(
                    event
                )
                or unavailable,
            ),

            (
                self.translate(
                    "timeline.details.label.title",
                    default="Title",
                ),
                str(
                    event.get("title")
                    or self.translate(
                        "timeline.item.default_title",
                        default="Timeline event",
                    )
                ),
            ),

            (
                self.translate(
                    "timeline.details.label.type",
                    default="Type",
                ),
                str(
                    event.get("type")
                    or event.get("event_type")
                    or unavailable
                ),
            ),

            (
                self.translate(
                    "timeline.details.label.id",
                    default="ID",
                ),
                str(
                    event.get("id")
                    or unavailable
                ),
            ),

        ]

        fields = [

            (
                "description",
                "timeline.details.label.description",
                "Description",
            ),

            (
                "details",
                "timeline.details.label.description",
                "Description",
            ),

            (
                "source",
                "timeline.details.label.source",
                "Source",
            ),

            (
                "source_name",
                "timeline.details.label.source",
                "Source",
            ),

            (
                "source_id",
                "timeline.details.label.source_id",
                "Source ID",
            ),

            (
                "entity",
                "timeline.details.label.related_entity",
                "Related Entity",
            ),

            (
                "entity_name",
                "timeline.details.label.related_entity",
                "Related Entity",
            ),

            (
                "entity_id",
                "timeline.details.label.related_entity_id",
                "Related Entity ID",
            ),

            (
                "location",
                "timeline.details.label.location",
                "Location",
            ),

            (
                "confidence",
                "timeline.details.label.confidence",
                "Confidence",
            ),

            (
                "created_at",
                "timeline.details.label.created_at",
                "Created At",
            ),

            (
                "updated_at",
                "timeline.details.label.updated_at",
                "Updated At",
            ),

        ]

        added = set()

        for field_name, key, default in fields:

            value = event.get(
                field_name
            )

            if value in (
                None,
                "",
            ):
                continue

            if key in added:
                continue

            added.add(
                key
            )

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
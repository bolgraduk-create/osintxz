"""
Evidence workspace view.

Responsible for:

- displaying evidence objects
- filtering evidence
- showing evidence details
- displaying empty and filtered states
- reacting to application language changes

Does NOT:

- access database
- execute business logic
- process files
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
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


class EvidenceWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Evidence tab workspace.

    The view automatically updates all visible interface text
    when the active application language changes.
    """

    import_files_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self.evidence: list[
            dict[str, Any]
        ] = []

        self.filtered_evidence: list[
            dict[str, Any]
        ] = []

        self._search_text = ""

        self._selected_evidence: (
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
        Create evidence workspace interface.
        """

        self.setObjectName(
            "EvidenceWorkspaceView"
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
        Create main evidence section.
        """

        self.evidence_section = Section(
            title="Investigation Evidence",
            description=(
                "Review collected evidence objects and inspect "
                "their complete stored values and identifiers."
            ),
            parent=self,
        )

        self.evidence_section.setObjectName(
            "EvidenceSection"
        )

        self.evidence_section.set_variant(
            "default"
        )

        self.evidence_section.set_content_spacing(
            14
        )

        self.evidence_section.set_content_margins(
            0,
            0,
            0,
            0,
        )

        self.evidence_section.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.main_layout.addWidget(
            self.evidence_section,
            1,
        )

    def _create_toolbar(
        self,
    ) -> None:
        """
        Create evidence search, statistics and import toolbar.
        """

        self.toolbar = Toolbar(
            parent=self.evidence_section
        )

        self.toolbar.setObjectName(
            "EvidenceToolbar"
        )

        self.toolbar.set_variant(
            "default"
        )

        self.search_box = SearchBox(
            placeholder=(
                "Search by title, type, value or identifier..."
            ),
            debounce_interval=200,
            parent=self.toolbar,
        )

        self.search_box.setObjectName(
            "EvidenceSearchBox"
        )

        self.search_box.setMinimumWidth(
            320
        )

        self.search_box.setMaximumWidth(
            680
        )

        self.count_badge = Badge(
            text="0 evidence objects",
            variant="neutral",
            size="medium",
            outlined=True,
            rounded=True,
            parent=self.toolbar,
        )

        self.count_badge.setObjectName(
            "EvidenceCountBadge"
        )

        self.import_files_button = QPushButton(
            self.toolbar
        )

        self.import_files_button.setObjectName(
            "EvidenceImportFilesButton"
        )

        self.import_files_button.setProperty(
            "variant",
            "primary",
        )

        self.import_files_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.import_files_button.clicked.connect(
            self.import_files_requested.emit
        )

        self.toolbar.add_left_widget(
            self.search_box,
            stretch=1,
        )

        self.toolbar.add_right_widget(
            self.count_badge
        )

        self.toolbar.add_separator(
            "right"
        )

        self.toolbar.add_right_widget(
            self.import_files_button
        )

        self.evidence_section.add_widget(
            self.toolbar
        )

    def _create_content(
        self,
    ) -> None:
        """
        Create evidence list, details and empty state.
        """

        self.content_container = QFrame(
            self.evidence_section
        )

        self.content_container.setObjectName(
            "EvidenceContentContainer"
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

        self.evidence_section.add_widget(
            self.content_container,
            stretch=1,
        )

    def _create_splitter(
        self,
    ) -> None:
        """
        Create evidence list and details splitter.
        """

        self.splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self.content_container,
        )

        self.splitter.setObjectName(
            "EvidenceSplitter"
        )

        self.splitter.setChildrenCollapsible(
            False
        )

        self._create_evidence_list()
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

    def _create_evidence_list(
        self,
    ) -> None:
        """
        Create evidence objects list.
        """

        self.list = QListWidget(
            self.splitter
        )

        self.list.setObjectName(
            "EvidenceList"
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
        Create selected evidence details panel.
        """

        self.details_card = Card(
            title="Evidence Details",
            subtitle=(
                "Select an evidence object to inspect its stored "
                "metadata and original value."
            ),
            parent=self.splitter,
        )

        self.details_card.setObjectName(
            "EvidenceDetailsCard"
        )

        self.details_card.set_variant(
            "default"
        )

        self.details = QPlainTextEdit(
            self.details_card
        )

        self.details.setObjectName(
            "EvidenceDetailsView"
        )

        self.details.setReadOnly(
            True
        )

        self.details.setPlaceholderText(
            "Select an evidence object to view its details."
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
        Create evidence empty state.
        """

        self.empty_state = EmptyState(
            title="No evidence collected",
            description=(
                "Evidence objects connected to this investigation "
                "will appear here."
            ),
            marker="◇",
            parent=self.content_container,
        )

        self.empty_state.setObjectName(
            "EvidenceEmptyState"
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
        Connect evidence workspace interactions.
        """

        self.search_box.search_changed.connect(
            self._filter_evidence
        )

        self.search_box.search_submitted.connect(
            self._filter_evidence
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

        self.evidence_section.set_title(
            self.translate(
                "evidence.section.title",
                default="Investigation Evidence",
            )
        )

        self.evidence_section.set_description(
            self.translate(
                "evidence.section.description",
                default=(
                    "Review collected evidence objects and inspect "
                    "their complete stored values and identifiers."
                ),
            )
        )

        self.search_box.set_placeholder(
            self.translate(
                "evidence.search.placeholder",
                default=(
                    "Search by title, type, value or identifier..."
                ),
            )
        )


        self.import_files_button.setText(
            self.translate(
                "evidence.import.files",
                default="Import files...",
            )
        )

        self.import_files_button.setToolTip(
            self.translate(
                "evidence.import.files_tooltip",
                default=(
                    "Import images, video, audio, "
                    "documents and archives"
                ),
            )
        )

        self.details_card.set_title(
            self.translate(
                "evidence.details.title",
                default="Evidence Details",
            )
        )

        self.details_card.set_subtitle(
            self.translate(
                "evidence.details.subtitle",
                default=(
                    "Select an evidence object to inspect its stored "
                    "metadata and original value."
                ),
            )
        )

        self.details.setPlaceholderText(
            self.translate(
                "evidence.details.placeholder",
                default=(
                    "Select an evidence object to view its details."
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
            < len(self.filtered_evidence)
        ):

            self.list.setCurrentRow(
                current_row
            )

        self._update_workspace_state()
        self._refresh_selected_evidence_details()

    # ==========================================================
    # Public API
    # ==========================================================

    def set_evidence(
        self,
        evidence: list,
    ) -> None:
        """
        Display evidence list.
        """

        normalized_evidence = [
            item
            for item in evidence
            if isinstance(
                item,
                dict,
            )
        ] if isinstance(
            evidence,
            list,
        ) else []

        self.evidence = (
            normalized_evidence
        )

        self._selected_evidence = None

        self.details.clear()

        self.list.clearSelection()

        self._apply_filter()

    def clear_evidence(
        self,
    ) -> None:
        """
        Remove all displayed evidence.
        """

        self.evidence = []
        self.filtered_evidence = []

        self._selected_evidence = None

        self.list.clear()
        self.details.clear()

        self._update_workspace_state()

    def set_import_enabled(
        self,
        enabled: bool,
    ) -> None:
        """
        Enable or disable file importing.
        """

        self.import_files_button.setEnabled(
            bool(
                enabled
            )
        )

    # ==========================================================
    # Filtering
    # ==========================================================

    def _filter_evidence(
        self,
        text: str,
    ) -> None:
        """
        Filter evidence objects.
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

        self._selected_evidence = None

        self.details.clear()

        self._apply_filter()

    def _apply_filter(
        self,
    ) -> None:
        """
        Apply current evidence search filter.
        """

        if not self._search_text:

            self.filtered_evidence = list(
                self.evidence
            )

        else:

            self.filtered_evidence = [
                item
                for item in self.evidence
                if self._matches_search(
                    item
                )
            ]

        self._selected_evidence = None

        self._populate_list()

        self._update_workspace_state()

        if self.filtered_evidence:

            self.list.setCurrentRow(
                0
            )

    def _matches_search(
        self,
        evidence: dict[str, Any],
    ) -> bool:
        """
        Check whether an evidence object matches search.
        """

        searchable_values = (
            evidence.get("title"),
            evidence.get("type"),
            evidence.get("value"),
            evidence.get("id"),
            evidence.get("description"),
            evidence.get("source"),
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
        Fill list with currently visible evidence.
        """

        self.list.clear()

        default_title = self.translate(
            "evidence.item.default_title",
            default="Evidence",
        )

        unknown_type = self.translate(
            "evidence.item.unknown_type",
            default="unknown",
        )

        for evidence in self.filtered_evidence:

            title = str(
                evidence.get(
                    "title"
                )
                or default_title
            )

            evidence_type = str(
                evidence.get(
                    "type"
                )
                or unknown_type
            )

            item = QListWidgetItem(
                f"{title}  [{evidence_type}]"
            )

            item.setToolTip(
                self._build_item_tooltip(
                    evidence
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
            self.evidence
        )

        visible_count = len(
            self.filtered_evidence
        )

        self._update_count_badge(
            visible_count=visible_count,
            total_count=total_count,
        )

        has_visible_evidence = (
            visible_count > 0
        )

        self.splitter.setVisible(
            has_visible_evidence
        )

        self.empty_state.setVisible(
            not has_visible_evidence
        )

        if has_visible_evidence:

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
                    "evidence.empty.search.title",
                    default="No matching evidence",
                )
            )

            self.empty_state.set_description(
                self.translate(
                    "evidence.empty.search.description",
                    default=(
                        "No evidence objects match the current search. "
                        "Try another title, type, value or identifier."
                    ),
                )
            )

            return

        self.empty_state.set_marker(
            "◇"
        )

        self.empty_state.set_title(
            self.translate(
                "evidence.empty.title",
                default="No evidence collected",
            )
        )

        self.empty_state.set_description(
            self.translate(
                "evidence.empty.description",
                default=(
                    "Evidence objects connected to this investigation "
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
        Update evidence count badge.
        """

        if visible_count == total_count:

            if total_count == 1:

                badge_text = self.translate(
                    "evidence.count.single",
                    default="{count} evidence object",
                    count=total_count,
                )

            else:

                badge_text = self.translate(
                    "evidence.count.multiple",
                    default="{count} evidence objects",
                    count=total_count,
                )

            self.count_badge.set_text(
                badge_text
            )

            return

        self.count_badge.set_text(
            self.translate(
                "evidence.count.filtered",
                default=(
                    "{visible} of {total} evidence objects"
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
        Display selected evidence details.
        """

        if index < 0:

            self._selected_evidence = None

            self.details.clear()

            return

        if index >= len(
            self.filtered_evidence
        ):

            self._selected_evidence = None

            self.details.clear()

            return

        evidence = (
            self.filtered_evidence[
                index
            ]
        )

        self._selected_evidence = evidence

        self._refresh_selected_evidence_details()

    def _show_details(
        self,
        item: QListWidgetItem,
    ) -> None:
        """
        Compatibility method for displaying selected details.
        """

        index = self.list.row(
            item
        )

        self._show_details_by_row(
            index
        )

    def _refresh_selected_evidence_details(
        self,
    ) -> None:
        """
        Refresh details using the active language.
        """

        if self._selected_evidence is None:

            return

        self.details.setPlainText(
            self._build_details_text(
                self._selected_evidence
            )
        )

    def _build_item_tooltip(
        self,
        evidence: dict[str, Any],
    ) -> str:
        """
        Build compact evidence tooltip.
        """

        default_title = self.translate(
            "evidence.item.default_title",
            default="Evidence",
        )

        unknown_type = self.translate(
            "evidence.item.unknown_type",
            default="unknown",
        )

        unavailable = self.translate(
            "evidence.details.unavailable",
            default="Unavailable",
        )

        title = str(
            evidence.get(
                "title"
            )
            or default_title
        )

        evidence_type = str(
            evidence.get(
                "type"
            )
            or unknown_type
        )

        value = str(
            evidence.get(
                "value"
            )
            or ""
        )

        compact_value = " ".join(
            value.split()
        )

        if len(
            compact_value
        ) > 180:

            compact_value = (
                compact_value[
                    :180
                ]
                + "..."
            )

        title_label = self.translate(
            "evidence.details.label.title",
            default="Title",
        )

        type_label = self.translate(
            "evidence.details.label.type",
            default="Type",
        )

        value_label = self.translate(
            "evidence.details.label.value",
            default="Value",
        )

        return (
            f"{title_label}: {title}\n"
            f"{type_label}: {evidence_type}\n"
            f"{value_label}: {compact_value or unavailable}"
        )

    def _build_details_text(
        self,
        evidence: dict[str, Any],
    ) -> str:
        """
        Build readable evidence details.
        """

        unavailable = self.translate(
            "evidence.details.unavailable",
            default="Unavailable",
        )

        title = str(
            evidence.get(
                "title"
            )
            or ""
        )

        evidence_type = str(
            evidence.get(
                "type"
            )
            or ""
        )

        value = str(
            evidence.get(
                "value"
            )
            or ""
        )

        evidence_id = str(
            evidence.get(
                "id"
            )
            or ""
        )

        description = str(
            evidence.get(
                "description"
            )
            or ""
        )

        source = str(
            evidence.get(
                "source"
            )
            or ""
        )

        created_at = str(
            evidence.get(
                "created_at"
            )
            or ""
        )

        title_label = self.translate(
            "evidence.details.label.title",
            default="Title",
        )

        type_label = self.translate(
            "evidence.details.label.type",
            default="Type",
        )

        value_label = self.translate(
            "evidence.details.label.value",
            default="Value",
        )

        id_label = self.translate(
            "evidence.details.label.id",
            default="ID",
        )

        description_label = self.translate(
            "evidence.details.label.description",
            default="Description",
        )

        source_label = self.translate(
            "evidence.details.label.source",
            default="Source",
        )

        created_at_label = self.translate(
            "evidence.details.label.created_at",
            default="Created At",
        )

        details_parts = [
            (
                f"{title_label}\n"
                f"{title or unavailable}"
            ),
            (
                f"{type_label}\n"
                f"{evidence_type or unavailable}"
            ),
            (
                f"{value_label}\n"
                f"{value or unavailable}"
            ),
            (
                f"{id_label}\n"
                f"{evidence_id or unavailable}"
            ),
        ]

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
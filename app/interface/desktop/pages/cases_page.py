"""
Cases page.

Responsible for:

- displaying investigation cases workspace
- creating investigations
- searching displayed investigations
- refreshing investigation data
- opening selected cases
- reacting to application language changes

Does NOT:

- execute business logic
- access database
- call repositories or services directly
"""

from __future__ import annotations

from datetime import (
    date,
    datetime,
)
from typing import (
    Any,
    Callable,
)

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QMenu,
    QMessageBox,
    QInputDialog,
)

from PySide6.QtGui import (
    QAction,
)

from app.interface.desktop.localization import (
    TranslatableMixin,
)
from app.interface.desktop.pages.base_page import (
    BasePage,
)
from app.interface.desktop.widgets import (
    Badge,
    Card,
    EmptyState,
    SearchBox,
    Section,
    Toolbar,
)
from app.localization import (
    TranslationManager,
    get_translation_manager,
)


class CasesPage(
    TranslatableMixin,
    BasePage,
):
    """
    Investigation cases workspace.

    The page uses the shared application TranslationManager
    and automatically updates all visible interface text when
    the active language changes.
    """

    def __init__(
        self,
        container,
        open_case_callback: Callable[
            [dict[str, Any]],
            None,
        ]
        | None = None,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        self.container = container

        self.open_case_callback = (
            open_case_callback
        )

        self._cases: list[
            dict[str, Any]
        ] = []

        self._visible_cases: list[
            dict[str, Any]
        ] = []

        self._loading = False

        super().__init__(
            "Cases"
        )

        active_translation_manager = (
            translation_manager
            if translation_manager is not None
            else self._resolve_translation_manager()
        )

        self.initialize_translations(
            active_translation_manager
        )

        self._load_cases()

    # ==========================================================
    # Translation manager
    # ==========================================================

    def _resolve_translation_manager(
        self,
    ) -> TranslationManager:
        """
        Resolve the shared application translation manager.
        """

        container_manager = getattr(
            self.container,
            "translation_manager",
            None,
        )

        if isinstance(
            container_manager,
            TranslationManager,
        ):
            return container_manager

        return get_translation_manager()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create cases workspace UI.
        """

        self.setObjectName(
            "CasesPage"
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )

        self.main_layout.setSpacing(
            20
        )

        self._create_page_section()
        self._create_toolbar()
        self._create_content_area()


    def _create_page_section(
        self,
    ) -> None:
        """
        Create main cases section.
        """

        self.cases_section = Section(
            parent=self
        )

        self.cases_section.set_title(
            "Investigation Cases"
        )

        self.cases_section.set_description(
            "Create, review and open investigation workspaces."
        )

        self.cases_section.set_variant(
            "default"
        )

        self.cases_section.set_content_spacing(
            16
        )

        self.cases_section.set_content_margins(
            0,
            0,
            0,
            0,
        )

        self.main_layout.addWidget(
            self.cases_section,
            1,
        )

    def _create_toolbar(
        self,
    ) -> None:
        """
        Create cases search and action toolbar.
        """

        self.toolbar = Toolbar(
            self.cases_section
        )

        self.toolbar.setObjectName(
            "CasesToolbar"
        )

        self.toolbar.set_variant(
            "default"
        )

        self.search_box = SearchBox(
            placeholder="Search investigations...",
            debounce_interval=200,
            parent=self.toolbar,
        )

        self.search_box.setObjectName(
            "CasesSearchBox"
        )

        self.search_box.setMinimumWidth(
            300
        )

        self.search_box.setMaximumWidth(
            520
        )

        self.search_box.search_changed.connect(
            self._apply_search
        )

        self.search_box.search_submitted.connect(
            self._apply_search
        )

        self.case_count_badge = Badge(
            text="0 investigations",
            variant="neutral",
            size="medium",
            outlined=True,
            rounded=True,
            parent=self.toolbar,
        )

        self.case_count_badge.setObjectName(
            "CasesCountBadge"
        )

        self.refresh_button = QPushButton(
            "Refresh",
            self.toolbar,
        )

        self.refresh_button.setObjectName(
            "CasesRefreshButton"
        )

        self.refresh_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.refresh_button.setToolTip(
            "Reload investigations"
        )

        self.refresh_button.clicked.connect(
            self._load_cases
        )

        self.create_button = QPushButton(
            "+ Create Investigation",
            self.toolbar,
        )

        self.create_button.setObjectName(
            "CasesCreateButton"
        )

        self.create_button.setProperty(
            "variant",
            "primary",
        )

        self.create_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.create_button.setToolTip(
            "Create a new investigation"
        )

        self.create_button.clicked.connect(
            self._create_investigation
        )

        self.toolbar.add_left_widget(
            self.search_box,
            stretch=1,
        )

        self.toolbar.add_center_widget(
            self.case_count_badge
        )

        self.toolbar.add_right_widget(
            self.refresh_button
        )

        self.toolbar.add_separator(
            "right"
        )

        self.toolbar.add_right_widget(
            self.create_button
        )

        self.cases_section.add_widget(
            self.toolbar
        )

    def _create_content_area(
        self,
    ) -> None:
        """
        Create cases list and empty-state area.
        """

        self.content_container = QFrame(
            self.cases_section
        )

        self.content_container.setObjectName(
            "CasesContentContainer"
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

        self._create_cases_list()
        self._create_empty_state()

        self.cases_section.add_widget(
            self.content_container,
            stretch=1,
        )

    def _create_cases_list(
        self,
    ) -> None:
        """
        Create investigations list.
        """

        self.case_list = QListWidget(
            self.content_container
        )

        self.case_list.setObjectName(
            "CasesList"
        )

        self.case_list.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.case_list.setSpacing(
            10
        )

        self.case_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.case_list.setVerticalScrollMode(
            QListWidget.ScrollMode.ScrollPerPixel
        )

        self.case_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )

        self.case_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.case_list.customContextMenuRequested.connect(
            self._show_case_context_menu
        )

        self.case_list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.case_list.itemDoubleClicked.connect(
            self._open_case
        )

        self.content_layout.addWidget(
            self.case_list,
            1,
        )

    def _create_empty_state(
        self,
    ) -> None:
        """
        Create reusable empty cases placeholder.
        """

        self.empty_state = EmptyState(
            title="No investigations found",
            description=(
                "Create your first investigation to begin collecting "
                "and analyzing intelligence."
            ),
            marker="○",
            parent=self.content_container,
        )

        self.empty_state.setObjectName(
            "CasesEmptyState"
        )

        self.empty_state.set_variant(
            "panel"
        )

        self.empty_create_button = QPushButton(
            "+ Create Investigation",
            self.empty_state,
        )

        self.empty_create_button.setObjectName(
            "CasesEmptyCreateButton"
        )

        self.empty_create_button.setProperty(
            "variant",
            "primary",
        )

        self.empty_create_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.empty_create_button.clicked.connect(
            self._create_investigation
        )

        self.empty_state.add_action(
            self.empty_create_button
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

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply the active language to all page controls.
        """

        self.title = self.translate(
            "navigation.cases",
            default="Cases",
        )

        self.cases_section.set_title(
            self.translate(
                "cases.section_title",
                default="Investigation Cases",
            )
        )

        self.cases_section.set_description(
            self.translate(
                "cases.section_description",
                default=(
                    "Create, review and open "
                    "investigation workspaces."
                ),
            )
        )

        self.search_box.set_placeholder(
            self.translate(
                "cases.search_placeholder",
                default="Search investigations...",
            )
        )

        self.search_box.clear_button.setToolTip(
            self.translate(
                "cases.clear_search_tooltip",
                default="Clear search",
            )
        )

        self.refresh_button.setToolTip(
            self.translate(
                "cases.reload_tooltip",
                default="Reload investigations",
            )
        )

        self.create_button.setToolTip(
            self.translate(
                "cases.create_tooltip",
                default="Create a new investigation",
            )
        )

        create_text = self.translate(
            "cases.create_investigation",
            default="Create Investigation",
        )

        self.create_button.setText(
            f"+ {create_text}"
        )

        self.empty_create_button.setText(
            f"+ {create_text}"
        )

        if self._loading:
            self.refresh_button.setText(
                self.translate(
                    "cases.refreshing",
                    default="Refreshing...",
                )
            )
        else:
            self.refresh_button.setText(
                self.translate(
                    "common.refresh",
                    default="Refresh",
                )
            )

        self._update_count(
            len(
                self._visible_cases
            )
        )

        self._update_empty_state()

        self._render_cases(
            self._visible_cases
        )

            # ==========================================================
    # Loading
    # ==========================================================

    def _load_cases(
        self,
    ) -> None:
        """
        Load cases through the application controller.
        """

        self._set_loading_state(
            True
        )

        try:

            cases = (
                self.container
                .case_controller
                .get_cases()
            )

            if cases is None:

                cases = []

            self._cases = [
                case
                for case in cases
                if isinstance(
                    case,
                    dict,
                )
            ]

            self._apply_search(
                self.search_box.text()
            )

        finally:

            self._set_loading_state(
                False
            )

    def refresh(
        self,
    ) -> None:
        """
        Public page refresh method.
        """

        self._load_cases()

    def _set_loading_state(
        self,
        loading: bool,
    ) -> None:
        """
        Update controls while cases are loading.
        """

        self._loading = bool(
            loading
        )

        self.search_box.set_busy(
            self._loading
        )

        self.refresh_button.setEnabled(
            not self._loading
        )

        self.create_button.setEnabled(
            not self._loading
        )

        self.empty_create_button.setEnabled(
            not self._loading
        )

        if self._loading:

            self.refresh_button.setText(
                self.translate(
                    "cases.refreshing",
                    default="Refreshing...",
                )
            )

        else:

            self.refresh_button.setText(
                self.translate(
                    "common.refresh",
                    default="Refresh",
                )
            )

    # ==========================================================
    # Rendering
    # ==========================================================

    def _render_cases(
        self,
        cases: list[dict[str, Any]],
    ) -> None:
        """
        Render provided cases collection.
        """

        self._visible_cases = list(
            cases
        )

        self.case_list.clear()

        for case in cases:

            card = self._create_case_card(
                case
            )

            item = QListWidgetItem()

            item.setData(
                Qt.ItemDataRole.UserRole,
                case,
            )

            item.setSizeHint(
                card.sizeHint()
            )

            self.case_list.addItem(
                item
            )

            self.case_list.setItemWidget(
                item,
                card,
            )

        self._update_count(
            len(cases)
        )

        has_cases = bool(
            cases
        )

        self.case_list.setVisible(
            has_cases
        )

        self.empty_state.setVisible(
            not has_cases
        )

        self._update_empty_state()

    def _update_empty_state(
        self,
    ) -> None:
        """
        Update empty state according to current search.
        """

        has_search = bool(
            self.search_box
            .text()
            .strip()
        )

        if has_search:

            self.empty_state.set_marker(
                "⌕"
            )

            self.empty_state.set_title(
                self.translate(
                    "cases.empty_search_title",
                    default="No matching investigations",
                )
            )

            self.empty_state.set_description(
                self.translate(
                    "cases.empty_search_description",
                    default=(
                        "No investigations match the current search. "
                        "Try another title, status or identifier."
                    ),
                )
            )

            self.empty_create_button.setVisible(
                False
            )

            return

        self.empty_state.set_marker(
            "○"
        )

        self.empty_state.set_title(
            self.translate(
                "cases.empty_title",
                default="No investigations found",
            )
        )

        self.empty_state.set_description(
            self.translate(
                "cases.empty_description",
                default=(
                    "Create your first investigation to begin "
                    "collecting and analyzing intelligence."
                ),
            )
        )

        self.empty_create_button.setVisible(
            True
        )

    def _update_count(
        self,
        count: int,
    ) -> None:
        """
        Update visible investigations count.
        """

        if count == 1:

            count_template = self.translate(
                "cases.count_single",
                default="{count} investigation",
            )

        else:

            count_template = self.translate(
                "cases.count_multiple",
                default="{count} investigations",
            )

        try:

            count_text = count_template.format(
                count=count
            )

        except (
            KeyError,
            ValueError,
        ):

            count_text = (
                f"{count} investigations"
            )

        self.case_count_badge.set_text(
            count_text
        )

    # ==========================================================
    # Case card
    # ==========================================================

    def _create_case_card(
        self,
        case: dict[str, Any],
    ) -> QWidget:
        """
        Create reusable investigation card.
        """

        card = Card()

        card.setObjectName(
            "CaseCard"
        )

        card.set_variant(
            "interactive"
        )

        card.setMinimumHeight(
            142
        )

        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        content_container = QFrame(
            card
        )

        content_container.setObjectName(
            "CaseCardContent"
        )

        content_layout = QVBoxLayout(
            content_container
        )

        content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        content_layout.setSpacing(
            12
        )

        header_layout = QHBoxLayout()

        header_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        header_layout.setSpacing(
            12
        )

        title_label = QLabel(
            self._get_case_title(
                case
            ),
            content_container,
        )

        title_label.setObjectName(
            "CaseCardTitle"
        )

        title_label.setWordWrap(
            True
        )

        status_key = (
            self._get_case_status_key(
                case
            )
        )

        status_badge = Badge(
            text=self._get_case_status(
                case
            ),
            variant=self._get_status_variant(
                status_key
            ),
            size="small",
            outlined=False,
            rounded=True,
            parent=content_container,
        )

        status_badge.setObjectName(
            "CaseStatusBadge"
        )

        header_layout.addWidget(
            title_label,
            1,
        )

        header_layout.addWidget(
            status_badge,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        description_label = QLabel(
            self._get_case_description(
                case
            ),
            content_container,
        )

        description_label.setObjectName(
            "CaseCardDescription"
        )

        description_label.setWordWrap(
            True
        )

        metadata_layout = QHBoxLayout()

        metadata_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        metadata_layout.setSpacing(
            18
        )

        case_id_label = self._create_metadata_label(
            self._format_metadata(
                label_key="cases.metadata.id",
                default_label="ID",
                value=self._short_case_id(
                    case
                ),
            ),
            content_container,
        )

        updated_label = self._create_metadata_label(
            self._format_metadata(
                label_key="cases.metadata.updated",
                default_label="Updated",
                value=self._get_updated_at(
                    case
                ),
            ),
            content_container,
        )

        entities_label = self._create_metadata_label(
            self._format_metadata(
                label_key="cases.metadata.entities",
                default_label="Entities",
                value=self._extract_count(
                    case,
                    "entities",
                ),
            ),
            content_container,
        )

        evidence_label = self._create_metadata_label(
            self._format_metadata(
                label_key="cases.metadata.evidence",
                default_label="Evidence",
                value=self._extract_count(
                    case,
                    "evidence",
                ),
            ),
            content_container,
        )

        metadata_layout.addWidget(
            case_id_label
        )

        metadata_layout.addWidget(
            updated_label
        )

        metadata_layout.addWidget(
            entities_label
        )

        metadata_layout.addWidget(
            evidence_label
        )

        metadata_layout.addStretch(
            1
        )

        content_layout.addLayout(
            header_layout
        )

        content_layout.addWidget(
            description_label
        )

        content_layout.addLayout(
            metadata_layout
        )

        card.add_widget(
            content_container
        )

        open_button = QPushButton(
            self.translate(
                "cases.open_workspace",
                default="Open workspace",
            ),
            card,
        )

        open_button.setObjectName(
            "CaseCardOpenButton"
        )

        open_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        open_button.setToolTip(
            self.translate(
                "cases.open_workspace_tooltip",
                default="Open this investigation workspace",
            )
        )

        open_button.clicked.connect(
            lambda checked=False, selected_case=case:
            self._open_case_data(
                selected_case
            )
        )

        card.add_action(
            open_button
        )

        return card

    @staticmethod
    def _create_metadata_label(
        text: str,
        parent: QWidget,
    ) -> QLabel:
        """
        Create a case metadata label.
        """

        label = QLabel(
            text,
            parent,
        )

        label.setObjectName(
            "CaseCardMetadata"
        )

        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        return label

    def _format_metadata(
        self,
        label_key: str,
        default_label: str,
        value: str,
    ) -> str:
        """
        Format a translated metadata label and its value.
        """

        label = self.translate(
            label_key,
            default=default_label,
        )

        return (
            f"{label}  {value}"
        )

    # ==========================================================
    # Search
    # ==========================================================

    def _apply_search(
        self,
        search_text: str,
    ) -> None:
        """
        Filter locally displayed investigation cases.
        """

        normalized_search = (
            search_text
            .strip()
            .casefold()
        )

        if not normalized_search:

            self._render_cases(
                self._cases
            )

            return

        filtered_cases: list[
            dict[str, Any]
        ] = []

        for case in self._cases:

            searchable_values = (
                self._get_case_title(
                    case
                ),
                self._get_case_description(
                    case
                ),
                str(
                    case.get(
                        "id",
                        "",
                    )
                ),
                str(
                    case.get(
                        "status",
                        "",
                    )
                ),
                self._get_case_status(
                    case
                ),
            )

            searchable_text = " ".join(
                searchable_values
            ).casefold()

            if normalized_search in searchable_text:

                filtered_cases.append(
                    case
                )

        self._render_cases(
            filtered_cases
        )

            # ==========================================================
    # Context menu
    # ==========================================================

    def _show_case_context_menu(
        self,
        position,
    ) -> None:
        """
        Display actions for the case under the cursor.
        """

        item = self.case_list.itemAt(
            position
        )

        if item is None:

            return

        case = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(
            case,
            dict,
        ):

            return

        self.case_list.setCurrentItem(
            item
        )

        menu = QMenu(
            self.case_list
        )

        open_action = QAction(
            self.translate(
                "cases.context.open",
                default="Open investigation",
            ),
            menu,
        )

        rename_action = QAction(
            self.translate(
                "cases.context.rename",
                default="Rename investigation",
            ),
            menu,
        )

        delete_action = QAction(
            self.translate(
                "cases.context.delete",
                default="Delete investigation",
            ),
            menu,
        )

        menu.addAction(
            open_action
        )

        menu.addAction(
            rename_action
        )

        menu.addSeparator()

        menu.addAction(
            delete_action
        )

        open_action.triggered.connect(
            lambda checked=False, selected_case=case:
                self._open_case_data(
                    selected_case
                )
        )

        rename_action.triggered.connect(
            lambda checked=False, selected_case=case:
                self._rename_case(
                    selected_case
                )
        )

        delete_action.triggered.connect(
            lambda checked=False, selected_case=case:
                self._request_delete_case(
                    selected_case
                )
        )

        menu.exec(
            self.case_list
            .viewport()
            .mapToGlobal(
                position
            )
        )

    def _rename_case(
        self,
        case: dict[str, Any],
    ) -> None:
        """
        Rename one investigation.
        """

        if not isinstance(
            case,
            dict,
        ):
            return

        case_id = case.get(
            "id"
        )

        if case_id is None:
            return

        current_title = self._get_case_title(
            case
        )

        new_title, accepted = (
            QInputDialog.getText(
                self,
                self.translate(
                    "cases.rename.title",
                    default="Rename investigation",
                ),
                self.translate(
                    "cases.rename.label",
                    default="New investigation name:",
                ),
                text=current_title,
            )
        )


        if not accepted:
            return

        new_title = new_title.strip()

        if (
            not new_title
            or new_title == current_title
        ):
            return

        try:

            renamed = (
                self.container
                .case_controller
                .rename_case(
                    case_id,
                    new_title,
                )
            )

            if not renamed:

                raise ValueError(
                    "Unable to rename investigation."
                )

            self._load_cases()

        except Exception as exc:

            QMessageBox.critical(
                self,
                self.translate(
                    "cases.rename.failed",
                    default="Rename failed",
                ),
                str(exc),
            )

    def _request_delete_case(
        self,
        case: dict[str, Any],
    ) -> None:
        """
        Confirm and request soft deletion of one investigation.
        """

        if not isinstance(
            case,
            dict,
        ):

            return

        case_id = case.get(
            "id"
        )

        if case_id is None:

            QMessageBox.warning(
                self,
                self.translate(
                    "cases.delete.title",
                    default="Delete investigation",
                ),
                self.translate(
                    "cases.delete.missing_id",
                    default=(
                        "The investigation does not contain "
                        "an identifier."
                    ),
                ),
            )

            return

        title = self._get_case_title(
            case
        )

        confirmation = QMessageBox.question(
            self,
            self.translate(
                "cases.delete.title",
                default="Delete investigation",
            ),
            self.translate(
                "cases.delete.confirmation",
                default=(
                    "Delete the investigation "
                    "\"{title}\"?\n\n"
                    "It will be removed from the active case list."
                ),
                title=title,
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            confirmation
            != QMessageBox.StandardButton.Yes
        ):

            return

        self._delete_case(
            case_id=case_id,
            title=title,
        )

    def _delete_case(
        self,
        *,
        case_id,
        title: str,
    ) -> None:
        """
        Delete one investigation through the case controller.
        """

        try:

            result = (
                self.container
                .case_controller
                .delete_case(
                    case_id
                )
            )

            if result is False:

                raise ValueError(
                    "The investigation was not found."
                )

            self._load_cases()

            QMessageBox.information(
                self,
                self.translate(
                    "cases.delete.completed_title",
                    default="Investigation deleted",
                ),
                self.translate(
                    "cases.delete.completed_message",
                    default=(
                        "The investigation "
                        "\"{title}\" was deleted."
                    ),
                    title=title,
                ),
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                self.translate(
                    "cases.delete.failed_title",
                    default="Deletion failed",
                ),
                str(
                    exc
                ),
            )
    # ==========================================================
    # Open case
    # ==========================================================

    def _open_case(
        self,
        item: QListWidgetItem,
    ) -> None:
        """
        Open case represented by a list item.
        """

        case = item.data(
            Qt.ItemDataRole.UserRole
        )

        self._open_case_data(
            case
        )

    def _open_case_data(
        self,
        case: dict[str, Any] | None,
    ) -> None:
        """
        Open provided case through the callback.
        """

        if not isinstance(
            case,
            dict,
        ):

            return

        if self.open_case_callback is None:

            return

        self.open_case_callback(
            case
        )

            # ==========================================================
    # Create
    # ==========================================================

    def _create_investigation(
        self,
    ) -> None:
        """
        Request investigation creation through the controller.
        """

        self.create_button.setEnabled(
            False
        )

        self.empty_create_button.setEnabled(
            False
        )

        try:

            (
                self.container
                .case_controller
                .create_case()
            )

            self._load_cases()

        finally:

            self.create_button.setEnabled(
                True
            )

            self.empty_create_button.setEnabled(
                True
            )

    # ==========================================================
    # Data presentation helpers
    # ==========================================================

    def _get_case_title(
        self,
        case: dict[str, Any],
    ) -> str:
        """
        Return displayable case title.
        """

        value = (
            case.get("title")
            or case.get("name")
        )

        if value:

            return str(
                value
            )

        return self.translate(
            "cases.untitled",
            default="Untitled investigation",
        )

    def _get_case_description(
        self,
        case: dict[str, Any],
    ) -> str:
        """
        Return displayable case description.
        """

        value = case.get(
            "description"
        )

        if not value:

            return self.translate(
                "cases.no_description",
                default=(
                    "No investigation description "
                    "has been provided."
                ),
            )

        return str(
            value
        )

    @staticmethod
    def _get_case_status_key(
        case: dict[str, Any],
    ) -> str:
        """
        Return normalized visual status key.
        """

        raw_status = str(
            case.get(
                "status",
                "active",
            )
        ).strip().casefold()

        if raw_status in {
            "closed",
            "completed",
            "complete",
            "resolved",
        }:

            return "closed"

        if raw_status in {
            "archived",
            "archive",
            "inactive",
        }:

            return "archived"

        return "active"

    def _get_case_status(
        self,
        case: dict[str, Any],
    ) -> str:
        """
        Return readable translated visual status.
        """

        status_key = (
            self._get_case_status_key(
                case
            )
        )

        status_translation_keys = {
            "active": "cases.status.active",
            "closed": "cases.status.closed",
            "archived": "cases.status.archived",
        }

        status_defaults = {
            "active": "Active",
            "closed": "Closed",
            "archived": "Archived",
        }

        return self.translate(
            status_translation_keys[
                status_key
            ],
            default=status_defaults[
                status_key
            ],
        )

    @staticmethod
    def _get_status_variant(
        status_key: str,
    ) -> str:
        """
        Map a case status to a badge variant.
        """

        variants = {
            "active": "success",
            "closed": "neutral",
            "archived": "warning",
        }

        return variants.get(
            status_key,
            "default",
        )

    def _short_case_id(
        self,
        case: dict[str, Any],
    ) -> str:
        """
        Return shortened case identifier.
        """

        raw_case_id = case.get(
            "id"
        )

        if raw_case_id is None:

            return self.translate(
                "cases.unavailable",
                default="Unavailable",
            )

        case_id = str(
            raw_case_id
        )

        if not case_id.strip():

            return self.translate(
                "cases.unavailable",
                default="Unavailable",
            )

        if len(
            case_id
        ) <= 12:

            return case_id

        return (
            f"{case_id[:8]}…"
        )

    @staticmethod
    def _extract_count(
        case: dict[str, Any],
        field_name: str,
    ) -> str:
        """
        Extract count from a direct field, count field or collection.
        """

        count_keys = (
            f"{field_name}_count",
            f"total_{field_name}",
        )

        for key in count_keys:

            value = case.get(
                key
            )

            if (
                isinstance(
                    value,
                    int,
                )
                and not isinstance(
                    value,
                    bool,
                )
            ):

                return str(
                    value
                )

        collection = case.get(
            field_name
        )

        if isinstance(
            collection,
            (
                list,
                tuple,
                set,
                dict,
            ),
        ):

            return str(
                len(
                    collection
                )
            )

        return "—"

    def _get_updated_at(
        self,
        case: dict[str, Any],
    ) -> str:
        """
        Return formatted case update date.
        """

        value = (
            case.get("updated_at")
            or case.get("modified_at")
            or case.get("created_at")
        )

        if value is None:

            return self.translate(
                "cases.unknown",
                default="Unknown",
            )

        if isinstance(
            value,
            datetime,
        ):

            return value.strftime(
                "%d %b %Y, %H:%M"
            )

        if isinstance(
            value,
            date,
        ):

            return value.strftime(
                "%d %b %Y"
            )

        text_value = str(
            value
        )

        try:

            normalized_value = (
                text_value.replace(
                    "Z",
                    "+00:00",
                )
            )

            parsed_value = (
                datetime.fromisoformat(
                    normalized_value
                )
            )

            return parsed_value.strftime(
                "%d %b %Y, %H:%M"
            )

        except (
            TypeError,
            ValueError,
        ):

            return text_value

    # ==========================================================
    # Qt lifecycle
    # ==========================================================

    def closeEvent(
        self,
        event,
    ) -> None:
        """
        Release translation subscriptions before closing.
        """

        self.dispose_translations()

        super().closeEvent(
            event
        )
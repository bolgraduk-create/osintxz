"""
Case workspace view.

Responsible for:

- workspace tabs UI
- displaying case sections
- emitting workspace actions
- distributing prepared workspace data between views
- forwarding graph data to graph workspace

Does NOT:

- access database
- execute business logic
- perform analysis
"""

from __future__ import annotations

from typing import Any

import json

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.interface.desktop.views.base_view import (
    BaseView,
)

from app.interface.desktop.views.entity_graph_workspace_view import (
    EntityGraphWorkspaceView,
)

from app.interface.desktop.views.entity_workspace_view import (
    EntityWorkspaceView,
)

from app.interface.desktop.views.evidence_workspace_view import (
    EvidenceWorkspaceView,
)

from app.interface.desktop.views.photo_workspace_view import (
    PhotoWorkspaceView,
)

from app.interface.desktop.views.message_workspace_view import (
    MessageWorkspaceView,
)

from app.interface.desktop.views.relationship_workspace_view import (
    RelationshipWorkspaceView,
)

from app.interface.desktop.views.report_workspace_view import (
    ReportWorkspaceView,
)

from app.interface.desktop.views.timeline_workspace_view import (
    TimelineWorkspaceView,
)

from app.interface.desktop.widgets import (
    Card,
    Toolbar,
)

from app.localization import (
    TranslationManager,
)

from app.interface.desktop.views.workspace.investigation_search_view import (
    InvestigationSearchView,
)

from app.interface.desktop.views.workspace.ai_workspace_view import (
    AIWorkspaceView,
)

from app.interface.desktop.views.location_map_workspace_view import (
    LocationMapWorkspaceView,
)


class CaseWorkspaceView(BaseView):
    """
    Main case workspace UI container.

    The view owns the workspace presentation and distributes already
    prepared workspace data between individual tab views.
    """

    investigation_search_requested = Signal(
        str,
        bool,
    )

    import_telegram_requested = Signal()

    refresh_requested = Signal()

    import_files_requested = Signal()

    create_evidence_requested = Signal(
        dict
    )

    create_entity_requested = Signal(
        dict
    )

    add_timeline_event_requested = Signal(
        dict
    )

    ai_analysis_requested = Signal(
        dict
    )

    bulk_message_action_requested = Signal(
        str,
        list,
    )

    ai_question_requested = Signal(
        str
    )

    ai_workflow_requested = Signal(
        str
    )

    calculate_image_hashes_requested = Signal(
        str
    )

    detect_faces_requested = Signal(
        str
    )

    find_face_matches_requested = Signal(
        str,
        str,
    )

    find_similar_images_requested = Signal(
        str
    )

    compare_images_requested = Signal(
        str,
        str,
    )

    create_location_requested = Signal(
        str
    )

    edit_location_requested = Signal(
        str,
        str,
        str,
        str,
    )

    location_photos_requested = Signal(
        str
    )

    attach_location_photo_requested = Signal(
        str
    )

    detach_location_photo_requested = Signal(
        str,
        str,
    )

    open_location_photo_requested = Signal(
        str
    )

    def __init__(
        self,
        translation_manager: TranslationManager,
        parent: QWidget | None = None,
    ) -> None:

        self._workspace_data: dict[
            str,
            Any,
        ] = {}

        self._loading = False

        super().__init__(
            parent=parent,
            translation_manager=translation_manager,
        )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create workspace.
        """

        self.setObjectName(
            "CaseWorkspaceView"
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.main_layout.setSpacing(
            16
        )

        self._create_toolbar()
        self._create_tabs()

    def _create_toolbar(
        self,
    ) -> None:
        """
        Create workspace actions toolbar.
        """

        self.toolbar = Toolbar(
            parent=self
        )

        self.toolbar.setObjectName(
            "CaseWorkspaceToolbar"
        )

        self.toolbar.set_variant(
            "default"
        )

        self.import_button = QPushButton(
            self.toolbar
        )

        self.import_button.setObjectName(
            "WorkspaceImportTelegramButton"
        )

        self.import_button.setProperty(
            "variant",
            "primary",
        )

        self.import_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.import_button.clicked.connect(
            self.import_telegram_requested.emit
        )

        self.refresh_button = QPushButton(
            self.toolbar
        )

        self.refresh_button.setObjectName(
            "WorkspaceRefreshButton"
        )

        self.refresh_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.refresh_button.clicked.connect(
            self.refresh_requested.emit
        )

        self.workspace_status_label = QLabel(
            self.toolbar
        )

        self.workspace_status_label.setObjectName(
            "WorkspaceStatusLabel"
        )

        self.toolbar.add_left_widget(
            self.import_button
        )

        self.toolbar.add_left_widget(
            self.refresh_button
        )

        self.toolbar.add_right_widget(
            self.workspace_status_label
        )

        self.main_layout.addWidget(
            self.toolbar
        )

    def _create_tabs(
        self,
    ) -> None:
        """
        Create workspace tabs.
        """

        self.tabs = QTabWidget(
            self
        )

        self.tabs.setObjectName(
            "CaseWorkspaceTabs"
        )

        self.tabs.setDocumentMode(
            True
        )

        self.tabs.setMovable(
            False
        )

        self.tabs.setTabsClosable(
            False
        )

        self.tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._create_overview_tab()
        self._create_investigation_search_tab()
        self._create_messages_tab()
        self._create_evidence_tab()
        self._create_photos_tab()
        self._create_map_tab()
        self._create_entities_tab()
        self._create_relationships_tab()
        self._create_graph_tab()
        self._create_timeline_tab()
        self._create_reports_tab()
        self._create_ai_tab()


        self.main_layout.addWidget(
            self.tabs,
            1,
        )

    # ==========================================================
    # Investigation Search
    # ==========================================================

    def _create_investigation_search_tab(
        self,
    ) -> None:
        self.investigation_search_view = InvestigationSearchView(
            self.tabs
        )

        self.investigation_search_view.search_requested.connect(
            self.investigation_search_requested.emit
        )

        self.investigation_search_tab_index = self.tabs.addTab(
            self.investigation_search_view,
            "Investigation Search",
        )

    # ==========================================================
    # Overview
    # ==========================================================

    def _create_overview_tab(
        self,
    ) -> None:
        """
        Create structured workspace overview.
        """

        self.overview_scroll = QScrollArea(
            self.tabs
        )

        self.overview_scroll.setObjectName(
            "WorkspaceOverviewScroll"
        )

        self.overview_scroll.setWidgetResizable(
            True
        )

        self.overview_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.overview_container = QWidget()

        self.overview_container.setObjectName(
            "WorkspaceOverviewContainer"
        )

        self.overview_layout = QVBoxLayout(
            self.overview_container
        )

        self.overview_layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        self.overview_layout.setSpacing(
            16
        )

        self._create_case_summary()
        self._create_statistics_grid()

        self.overview_layout.addStretch(
            1
        )

        self.overview_scroll.setWidget(
            self.overview_container
        )

        self.overview_tab_index = self.tabs.addTab(
            self.overview_scroll,
            "",
        )

    def _create_case_summary(
        self,
    ) -> None:
        """
        Create selected case summary card.
        """

        self.case_summary_card = Card(
            parent=self.overview_container
        )

        self.case_summary_card.setObjectName(
            "WorkspaceCaseSummaryCard"
        )

        self.case_summary_card.set_variant(
            "elevated"
        )

        self.case_title_label = QLabel(
            self.case_summary_card
        )

        self.case_title_label.setObjectName(
            "WorkspaceCaseTitle"
        )

        self.case_title_label.setWordWrap(
            True
        )

        self.case_description_label = QLabel(
            self.case_summary_card
        )

        self.case_description_label.setObjectName(
            "WorkspaceCaseDescription"
        )

        self.case_description_label.setWordWrap(
            True
        )

        self.case_identifier_label = QLabel(
            self.case_summary_card
        )

        self.case_identifier_label.setObjectName(
            "WorkspaceCaseIdentifier"
        )

        self.case_identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.case_summary_card.add_widget(
            self.case_title_label
        )

        self.case_summary_card.add_widget(
            self.case_description_label
        )

        self.case_summary_card.add_widget(
            self.case_identifier_label
        )

        self.overview_layout.addWidget(
            self.case_summary_card
        )

    def _create_statistics_grid(
        self,
    ) -> None:
        """
        Create investigation statistics cards.
        """

        self.statistics_container = QFrame(
            self.overview_container
        )

        self.statistics_container.setObjectName(
            "WorkspaceStatisticsContainer"
        )

        self.statistics_layout = QGridLayout(
            self.statistics_container
        )

        self.statistics_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.statistics_layout.setHorizontalSpacing(
            12
        )

        self.statistics_layout.setVerticalSpacing(
            12
        )

        self.statistic_labels: dict[
            str,
            QLabel,
        ] = {}

        self.statistic_title_labels: dict[
            str,
            QLabel,
        ] = {}

        statistic_keys = (
            "messages",
            "evidence",
            "entities",
            "relationships",
            "reports",
            "timeline",
        )

        for index, statistic_key in enumerate(
            statistic_keys
        ):

            (
                card,
                title_label,
                value_label,
            ) = self._create_statistic_card(
                parent=self.statistics_container,
            )

            row = index // 3
            column = index % 3

            self.statistics_layout.addWidget(
                card,
                row,
                column,
            )

            self.statistic_title_labels[
                statistic_key
            ] = title_label

            self.statistic_labels[
                statistic_key
            ] = value_label

        for column in range(
            3
        ):

            self.statistics_layout.setColumnStretch(
                column,
                1,
            )

        self.overview_layout.addWidget(
            self.statistics_container
        )

    @staticmethod
    def _create_statistic_card(
        parent: QWidget,
    ) -> tuple[
        Card,
        QLabel,
        QLabel,
    ]:
        """
        Create an overview statistic card.
        """

        card = Card(
            parent=parent
        )

        card.setObjectName(
            "WorkspaceStatisticCard"
        )

        card.set_variant(
            "default"
        )

        card.setMinimumHeight(
            110
        )

        title_label = QLabel(
            card
        )

        title_label.setObjectName(
            "WorkspaceStatisticTitle"
        )

        value_label = QLabel(
            "0",
            card,
        )

        value_label.setObjectName(
            "WorkspaceStatisticValue"
        )

        value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        card.add_widget(
            title_label
        )

        card.add_widget(
            value_label
        )

        return (
            card,
            title_label,
            value_label,
        )

    # ==========================================================
    # Workspace tabs
    # ==========================================================

    def _create_messages_tab(
        self,
    ) -> None:

        self.message_view = (
            MessageWorkspaceView()
        )

        self.message_view.create_evidence_requested.connect(
            self.create_evidence_requested
        )

        self.message_view.create_entity_requested.connect(
            self.create_entity_requested
        )

        self.message_view.add_timeline_event_requested.connect(
            self.add_timeline_event_requested
        )

        self.message_view.ai_analysis_requested.connect(
            self.ai_analysis_requested
        )

        self.messages_tab_index = self.tabs.addTab(
            self.message_view,
            "",
        )

        self.message_view.bulk_action_requested.connect(
            self.bulk_message_action_requested
        )


    def _create_evidence_tab(
        self,
    ) -> None:

        self.evidence_view = (
            EvidenceWorkspaceView()
        )

        self.evidence_view.import_files_requested.connect(
            self.import_files_requested.emit
        )

        self.evidence_tab_index = self.tabs.addTab(
            self.evidence_view,
            "",
        )

    def _create_photos_tab(
        self,
    ) -> None:
        """
        Create specialized image evidence workspace.
        """

        self.photo_view = (
            PhotoWorkspaceView(
                parent=self.tabs,
            )
        )

        self.photo_view.setObjectName(
            "CasePhotoWorkspaceView"
        )

        self.photo_view.import_images_requested.connect(
            self.import_files_requested.emit
        )

        self.photo_view.detect_faces_requested.connect(
            self.detect_faces_requested.emit
        )

        self.photo_view.find_face_matches_requested.connect(
            self.find_face_matches_requested.emit
        )

        self.photo_view.create_location_requested.connect(
            self.create_location_requested.emit
        )


        self.photo_view.calculate_hashes_requested.connect(
            self.calculate_image_hashes_requested.emit
        )

        self.photo_view.find_similar_requested.connect(
            self.find_similar_images_requested.emit
        )

        self.photo_view.compare_images_requested.connect(
            self.compare_images_requested.emit
        )

        self.photos_tab_index = self.tabs.addTab(
            self.photo_view,
            "",
        )

    def _create_map_tab(
        self,
    ) -> None:
        """
        Create geographic investigation workspace.
        """

        self.map_view = (
            LocationMapWorkspaceView(
                self
            )
        )

        self.map_tab_index = (
            self.tabs.addTab(
                self.map_view,
                "Map",
            )
        )

        self.map_view.location_edit_requested.connect(
            self.edit_location_requested.emit
        )

        self.map_view.location_photos_requested.connect(
            self.location_photos_requested.emit
        )

        self.map_view.attach_location_photo_requested.connect(
            self.attach_location_photo_requested.emit
        )

        self.map_view.detach_location_photo_requested.connect(
            self.detach_location_photo_requested.emit
        )

        self.map_view.open_location_photo_requested.connect(
            self.open_location_photo_requested.emit
        )

    def set_location_photos(
        self,
        location_id: str,
        photos: list[dict[str, Any]],
    ) -> None:
        """
        Display Evidence photos connected
        to the selected Location.
        """

        self.map_view.set_location_photos(
            location_id,
            photos,
        )

    def _create_entities_tab(
        self,
    ) -> None:

        self.entity_view = (
            EntityWorkspaceView()
        )

        self.entities_tab_index = self.tabs.addTab(
            self.entity_view,
            "",
        )

    def _create_relationships_tab(
        self,
    ) -> None:

        self.relationship_view = (
            RelationshipWorkspaceView()
        )

        self.relationships_tab_index = self.tabs.addTab(
            self.relationship_view,
            "",
        )

    def _create_graph_tab(
        self,
    ) -> None:

        self.entity_graph_view = (
            EntityGraphWorkspaceView()
        )

        self.graph_tab_index = self.tabs.addTab(
            self.entity_graph_view,
            "",
        )

    def _create_timeline_tab(
        self,
    ) -> None:

        self.timeline_view = (
            TimelineWorkspaceView()
        )

        self.timeline_tab_index = self.tabs.addTab(
            self.timeline_view,
            "",
        )

    def _create_reports_tab(
        self,
    ) -> None:

        self.report_view = (
            ReportWorkspaceView()
        )

        self.reports_tab_index = self.tabs.addTab(
            self.report_view,
            "",
        )

    def _create_ai_tab(
        self,
    ) -> None:
        """
        Create investigation AI workspace.
        """

        self.ai_view = AIWorkspaceView(
            parent=self.tabs,
        )

        self.ai_view.setObjectName(
            "CaseAIWorkspaceView"
        )

        self.ai_view.ask_button.clicked.connect(
            self._request_ai_question
        )

        self.ai_view.workflow_requested.connect(
            self.ai_workflow_requested
        )

        self.ai_tab_index = self.tabs.addTab(
            self.ai_view,
            "",
        )

    def _request_ai_question(
        self,
    ) -> None:
        """
        Emit an AI question for the current investigation.
        """

        question = (
            self.ai_view
            .prompt
            .toPlainText()
            .strip()
        )

        if not question:

            return

        self.ai_question_requested.emit(
            question
        )

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply current language to the workspace interface.
        """

        self.import_button.setText(
            self.translate(
                "workspace.import_telegram",
                default="Import Telegram",
            )
        )

        self.import_button.setToolTip(
            self.translate(
                "workspace.import_telegram_tooltip",
                default=(
                    "Import messages from a Telegram "
                    "result.json export"
                ),
            )
        )

        self.refresh_button.setToolTip(
            self.translate(
                "workspace.refresh_tooltip",
                default=(
                    "Reload all investigation workspace data"
                ),
            )
        )

        if self._loading:

            self.refresh_button.setText(
                self.translate(
                    "workspace.refreshing",
                    default="Refreshing...",
                )
            )

            self.workspace_status_label.setText(
                self.translate(
                    "workspace.loading",
                    default="Loading workspace...",
                )
            )

        else:

            self.refresh_button.setText(
                self.translate(
                    "workspace.refresh",
                    default="Refresh Workspace",
                )
            )

            status_key = (
                "workspace.loaded"
                if self._workspace_data
                else "workspace.ready"
            )

            status_default = (
                "Workspace loaded"
                if self._workspace_data
                else "Workspace ready"
            )

            self.workspace_status_label.setText(
                self.translate(
                    status_key,
                    default=status_default,
                )
            )

        self.tabs.setTabText(
            self.overview_tab_index,
            self.translate(
                "workspace.tabs.overview",
                default="Overview",
            ),
        )

        self.tabs.setTabText(
            self.messages_tab_index,
            self.translate(
                "workspace.tabs.messages",
                default="Messages",
            ),
        )

        self.tabs.setTabText(
            self.evidence_tab_index,
            self.translate(
                "workspace.tabs.evidence",
                default="Evidence",
            ),
        )

        self.tabs.setTabText(
            self.photos_tab_index,
            self.translate(
                "workspace.tabs.photos",
                default="Photos",
            ),
        )

        self.tabs.setTabText(
            self.entities_tab_index,
            self.translate(
                "workspace.tabs.entities",
                default="Entities",
            ),
        )

        self.tabs.setTabText(
            self.relationships_tab_index,
            self.translate(
                "workspace.tabs.relationships",
                default="Relationships",
            ),
        )

        self.tabs.setTabText(
            self.graph_tab_index,
            self.translate(
                "workspace.tabs.graph",
                default="Graph",
            ),
        )

        self.tabs.setTabText(
            self.timeline_tab_index,
            self.translate(
                "workspace.tabs.timeline",
                default="Timeline",
            ),
        )

        self.tabs.setTabText(
            self.reports_tab_index,
            self.translate(
                "workspace.tabs.reports",
                default="Reports",
            ),
        )

        self.tabs.setTabText(
            self.ai_tab_index,
            self.translate(
                "workspace.tabs.ai",
                default="AI Assistant",
            ),
        )

        self.statistic_title_labels[
            "messages"
        ].setText(
            self.translate(
                "workspace.statistics.messages",
                default="Messages",
            )
        )

        self.statistic_title_labels[
            "evidence"
        ].setText(
            self.translate(
                "workspace.statistics.evidence",
                default="Evidence",
            )
        )

        self.statistic_title_labels[
            "entities"
        ].setText(
            self.translate(
                "workspace.statistics.entities",
                default="Entities",
            )
        )

        self.statistic_title_labels[
            "relationships"
        ].setText(
            self.translate(
                "workspace.statistics.relationships",
                default="Relationships",
            )
        )

        self.statistic_title_labels[
            "reports"
        ].setText(
            self.translate(
                "workspace.statistics.reports",
                default="Reports",
            )
        )

        self.statistic_title_labels[
            "timeline"
        ].setText(
            self.translate(
                "workspace.statistics.timeline",
                default="Timeline events",
            )
        )


        self._refresh_case_summary_translation()

    def _refresh_case_summary_translation(
        self,
    ) -> None:
        """
        Reapply translated fallback values to the case summary.
        """

        case_data = self._workspace_data.get(
            "case",
            {},
        )

        if not isinstance(
            case_data,
            dict,
        ):

            case_data = {}

        self._set_case_data(
            case_data
        )

    # ==========================================================
    # Workspace data
    # ==========================================================

    def set_workspace_data(
        self,
        workspace: dict[str, Any] | None,
    ) -> None:
        """
        Distribute prepared workspace data between workspace views.
        """

        normalized_workspace = (
            workspace
            if isinstance(
                workspace,
                dict,
            )
            else {}
        )

        self._workspace_data = dict(
            normalized_workspace
        )

        case_data = normalized_workspace.get(
            "case",
            {},
        )

        statistics = normalized_workspace.get(
            "statistics",
            {},
        )

        if not isinstance(
            case_data,
            dict,
        ):

            case_data = {}

        if not isinstance(
            statistics,
            dict,
        ):

            statistics = {}

        self._set_case_data(
            case_data
        )

        self._set_statistics(
            statistics
        )

        self.message_view.set_messages(
            self._get_list(
                normalized_workspace,
                "messages",
            )
        )

        evidence_items = self._get_list(
            normalized_workspace,
            "evidence",
        )

        self.evidence_view.set_evidence(
            evidence_items
        )

        self.photo_view.set_evidence(
            evidence_items
        )

        entity_items = self._get_list(
            normalized_workspace,
            "entities",
        )

        self.entity_view.set_entities(
            entity_items
        )

        self.map_view.set_locations(
            self._build_map_locations(
                entity_items
            )
        )

        self.relationship_view.set_relationships(
            self._get_list(
                normalized_workspace,
                "relationships",
            )
        )

        self.set_graph_data(
            normalized_workspace.get(
                "graph",
                {
                    "nodes": [],
                    "edges": [],
                    "statistics": {},
                },
            )
        )

        self.timeline_view.set_events(
            self._get_list(
                normalized_workspace,
                "timeline",
            )
        )

        self.report_view.set_reports(
            self._get_list(
                normalized_workspace,
                "reports",
            )
        )

        self.workspace_status_label.setText(
            self.translate(
                "workspace.loaded",
                default="Workspace loaded",
            )
        )

    def _set_case_data(
        self,
        case_data: dict[str, Any],
    ) -> None:
        """
        Update selected investigation summary.
        """

        case_title = (
            case_data.get("title")
            or case_data.get("name")
            or self.translate(
                "workspace.case.untitled",
                default="Untitled investigation",
            )
        )

        case_description = (
            case_data.get("description")
            or self.translate(
                "workspace.case.no_description",
                default=(
                    "No investigation description has "
                    "been provided."
                ),
            )
        )

        case_identifier = (
            case_data.get("id")
            or self.translate(
                "workspace.case.unavailable",
                default="Unavailable",
            )
        )

        if not case_data:

            case_title = self.translate(
                "workspace.case.not_selected",
                default="No investigation selected",
            )

            case_description = self.translate(
                "workspace.case.select_prompt",
                default=(
                    "Select an investigation to load its workspace."
                ),
            )

            case_identifier = "—"

        self.case_title_label.setText(
            str(
                case_title
            )
        )

        self.case_description_label.setText(
            str(
                case_description
            )
        )

        self.case_identifier_label.setText(
            self.translate(
                "workspace.case.identifier",
                default="ID: {identifier}",
                identifier=case_identifier,
            )
        )

    def _set_statistics(
        self,
        statistics: dict[str, Any],
    ) -> None:
        """
        Update overview statistic values.
        """

        for key, label in (
            self.statistic_labels.items()
        ):

            value = statistics.get(
                key,
                0,
            )

            if value is None:

                value = 0

            label.setText(
                str(
                    value
                )
            )

    @staticmethod
    def _get_list(
        workspace: dict[str, Any],
        key: str,
    ) -> list[Any]:
        """
        Return a safe list from workspace data.
        """

        value = workspace.get(
            key,
            [],
        )

        if isinstance(
            value,
            list,
        ):

            return value

        if isinstance(
            value,
            tuple,
        ):

            return list(
                value
            )

        return []

    # ==========================================================
    # Loading state
    # ==========================================================

    def set_loading(
        self,
        loading: bool,
    ) -> None:
        """
        Update workspace controls during loading.
        """

        self._loading = loading

        self.import_button.setEnabled(
            not loading
        )

        self.refresh_button.setEnabled(
            not loading
        )

        self.retranslate_ui()

    def set_analysis_status(
        self,
        text: str | None,
    ) -> None:
        """Show unobtrusive orchestrator status in the existing status bar."""

        normalized = str(
            text
            or ""
        ).strip()

        if normalized:
            self.workspace_status_label.setText(
                normalized
            )
            return

        self.retranslate_ui()

    # ==========================================================
    # Graph data
    # ==========================================================

    def set_graph_data(
        self,
        graph_data: dict[str, Any] | None,
    ) -> None:
        """
        Forward prepared graph data to graph workspace.
        """

        self.entity_graph_view.set_graph_data(
            graph_data
        )

    def clear_graph(
        self,
    ) -> None:
        """
        Clear the entity graph workspace.
        """

        self.entity_graph_view.clear_graph()

    def show_graph_tab(
        self,
    ) -> None:


        """
        Switch the workspace to the graph tab.
        """

        self.tabs.setCurrentWidget(
            self.entity_graph_view
        )

    def show_evidence_tab(
        self,
    ) -> None:
        """
        Switch the workspace to the evidence tab.
        """

        self.tabs.setCurrentWidget(
            self.evidence_view
        )

    def show_photos_tab(
        self,
    ) -> None:
        """
        Switch the workspace to the photos tab.
        """

        self.tabs.setCurrentWidget(
            self.photo_view
        )

    def show_entities_tab(
        self,
    ) -> None:
        """
        Switch the workspace to the entities tab.
        """

        self.tabs.setCurrentWidget(
            self.entity_view
        )

    def show_timeline_tab(
        self,
    ) -> None:
        """
        Switch to the timeline tab.
        """

        self.tabs.setCurrentWidget(
            self.timeline_view
        )

    def show_ai_tab(
        self,
    ) -> None:
        """
        Switch to the AI assistant tab.
        """

        self.tabs.setCurrentWidget(
            self.ai_view
        )

    def append_ai_message(
        self,
        text: str,
    ) -> None:
        """
        Append text to the AI conversation.
        """

        normalized_text = str(
            text
            or ""
        ).strip()

        if not normalized_text:

            return

        self.ai_view.append_response(
            normalized_text
        )

    def clear_ai_workspace(
        self,
    ) -> None:
        """
        Clear AI conversation and prompt.
        """

        self.ai_view.clear()

    def set_ai_loading(
        self,
        loading: bool,
    ) -> None:
        """
        Update AI controls during a request.
        """

        self.ai_view.set_loading(
            loading
        )


    def show_map_tab(
        self,
    ) -> None:
        """
        Switch workspace to geographic map.
        """

        if not hasattr(
            self,
            "map_tab_index",
        ):

            return

        self.tabs.setCurrentIndex(
            self.map_tab_index
        )


    def focus_map_location(
        self,
        latitude: float,
        longitude: float,
        *,
        zoom: int = 17,
    ) -> None:
        """
        Open map and focus geographic coordinates.
        """

        if not hasattr(
            self,
            "map_view",
        ):

            return

        self.show_map_tab()

        self.map_view.focus_location(
            latitude,
            longitude,
            zoom=zoom,
        )

    @staticmethod
    def _build_map_locations(
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Convert LOCATION entities into map-ready data.
        """

        locations: list[
            dict[str, Any]
        ] = []

        for entity in entities:

            if not isinstance(
                entity,
                dict,
            ):

                continue

            entity_type = str(
                entity.get(
                    "type"
                )
                or ""
            ).strip().lower()

            if entity_type != "location":

                continue

            metadata_json = entity.get(
                "metadata_json"
            )

            metadata: dict[
                str,
                Any,
            ] = {}

            if isinstance(
                metadata_json,
                str,
            ):

                try:

                    decoded = json.loads(
                        metadata_json
                    )

                    if isinstance(
                        decoded,
                        dict,
                    ):

                        metadata = decoded

                except (
                    TypeError,
                    json.JSONDecodeError,
                ):

                    metadata = {}

            elif isinstance(
                metadata_json,
                dict,
            ):

                metadata = dict(
                    metadata_json
                )

            location_data = metadata.get(
                "location"
            )

            if not isinstance(
                location_data,
                dict,
            ):

                continue

            latitude = location_data.get(
                "latitude"
            )

            longitude = location_data.get(
                "longitude"
            )

            altitude = location_data.get(
                "altitude"
            )

            try:

                normalized_latitude = float(
                    latitude
                )

                normalized_longitude = float(
                    longitude
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

            map_data = metadata.get(
                "map"
            )

            if not isinstance(
                map_data,
                dict,
            ):

                map_data = {}

            marker_name = str(
                map_data.get(
                    "marker_name"
                )
                or entity.get(
                    "value"
                )
                or "Location"
            ).strip()

            marker_color = str(
                map_data.get(
                    "marker_color"
                )
                or "#e072c4"
            ).strip()

            locations.append(
                {
                    "id": str(
                        entity.get(
                            "id"
                        )
                        or ""
                    ),
                    "name": marker_name,
                    "value": (
                        entity.get(
                            "value"
                        )
                    ),
                    "latitude": (
                        normalized_latitude
                    ),
                    "longitude": (
                        normalized_longitude
                    ),
                    "altitude": altitude,
                    "marker_color": (
                        marker_color
                    ),
                    "description": (
                        entity.get(
                            "description"
                        )
                    ),
                    "metadata": metadata,
                }
            )

        return locations
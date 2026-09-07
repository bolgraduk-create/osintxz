"""
Face Memory workspace view.

Responsible for:

- displaying Face Memory profiles
- displaying unassigned face observations
- filtering profiles
- displaying selected profile details
- displaying observations belonging to a profile
- emitting user actions

Does NOT:

- access the database
- calculate face embeddings
- perform face recognition
- modify Face Memory directly
- commit database transactions
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QSize,
    Qt,
    QRect,
    Signal,
)

from PySide6.QtGui import (
    QIcon,
    QPixmap,
)

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
    EmptyState,
    SearchBox,
    Section,
    Toolbar,
)


class FaceMemoryWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Persistent Face Memory browser.
    """

    refresh_requested = Signal()

    create_profile_requested = Signal()

    rename_profile_requested = Signal(
        str
    )

    edit_description_requested = Signal(
        str
    )

    delete_profile_requested = Signal(
        str
    )

    search_similar_requested = Signal(
        str
    )

    assign_observation_requested = Signal(
        str
    )

    unassign_observation_requested = Signal(
        str
    )

    observation_selected = Signal(
        str
    )

    FACE_CROP_PADDING = 0.20

    def __init__(
        self,
        parent: QWidget | None = None,
        translation_manager: (
            TranslationManager | None
        ) = None,
    ) -> None:

        super().__init__(
            parent
        )

        self.profiles: list[
            dict[str, Any]
        ] = []

        self.unassigned: list[
            dict[str, Any]
        ] = []

        self.filtered_profiles: list[
            dict[str, Any]
        ] = []

        self._selected_profile: (
            dict[str, Any] | None
        ) = None

        self._search_text = ""

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

        self.setObjectName(
            "FaceMemoryWorkspaceView"
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

        self.face_memory_section = Section(
            title="Face Memory",
            description=(
                "Review user-managed face profiles, "
                "stored observations and unassigned "
                "faces detected during investigations."
            ),
            parent=self,
        )

        self.face_memory_section.setObjectName(
            "FaceMemorySection"
        )

        self.face_memory_section.set_variant(
            "default"
        )

        self.face_memory_section.set_content_spacing(
            14
        )

        self.face_memory_section.set_content_margins(
            0,
            0,
            0,
            0,
        )

        self.face_memory_section.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.main_layout.addWidget(
            self.face_memory_section,
            1,
        )

    def _create_toolbar(
        self,
    ) -> None:

        self.toolbar = Toolbar(
            parent=self.face_memory_section
        )

        self.toolbar.setObjectName(
            "FaceMemoryToolbar"
        )

        self.toolbar.set_variant(
            "default"
        )

        self.search_box = SearchBox(
            placeholder=(
                "Search Face Memory profiles..."
            ),
            debounce_interval=200,
            parent=self.toolbar,
        )

        self.search_box.setObjectName(
            "FaceMemorySearchBox"
        )

        self.search_box.setMinimumWidth(
            300
        )

        self.search_box.setMaximumWidth(
            620
        )

        self.profile_count_badge = Badge(
            text="0 profiles",
            variant="neutral",
            size="medium",
            outlined=True,
            rounded=True,
            parent=self.toolbar,
        )

        self.profile_count_badge.setObjectName(
            "FaceMemoryProfileCountBadge"
        )

        self.unassigned_count_badge = Badge(
            text="0 unassigned",
            variant="neutral",
            size="medium",
            outlined=True,
            rounded=True,
            parent=self.toolbar,
        )

        self.unassigned_count_badge.setObjectName(
            "FaceMemoryUnassignedCountBadge"
        )

        self.create_profile_button = QPushButton(
            "Create profile",
            self.toolbar,
        )

        self.create_profile_button.setObjectName(
            "FaceMemoryCreateProfileButton"
        )

        self.refresh_button = QPushButton(
            "Refresh",
            self.toolbar,
        )

        self.refresh_button.setObjectName(
            "FaceMemoryRefreshButton"
        )

        self.toolbar.add_left_widget(
            self.search_box
        )

        self.toolbar.add_left_widget(
            self.profile_count_badge
        )

        self.toolbar.add_left_widget(
            self.unassigned_count_badge
        )

        self.toolbar.add_right_widget(
            self.create_profile_button
        )

        self.toolbar.add_right_widget(
            self.refresh_button
        )

        self.face_memory_section.add_widget(
            self.toolbar
        )

    def _create_content(
        self,
    ) -> None:

        self.content_splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self.face_memory_section,
        )

        self.content_splitter.setObjectName(
            "FaceMemoryContentSplitter"
        )

        self._create_navigation_panel()
        self._create_detail_panel()

        self.content_splitter.addWidget(
            self.navigation_frame
        )

        self.content_splitter.addWidget(
            self.detail_frame
        )

        self.content_splitter.setStretchFactor(
            0,
            0,
        )

        self.content_splitter.setStretchFactor(
            1,
            1,
        )

        self.content_splitter.setSizes(
            [
                310,
                850,
            ]
        )

        self.face_memory_section.add_widget(
            self.content_splitter,
            1,
        )

    # ==========================================================
    # Navigation
    # ==========================================================

    def _create_navigation_panel(
        self,
    ) -> None:

        self.navigation_frame = QFrame(
            self.content_splitter
        )

        self.navigation_frame.setObjectName(
            "FaceMemoryNavigation"
        )

        self.navigation_frame.setMinimumWidth(
            260
        )

        self.navigation_frame.setMaximumWidth(
            430
        )

        layout = QVBoxLayout(
            self.navigation_frame
        )

        layout.setContentsMargins(
            10,
            10,
            10,
            10,
        )

        layout.setSpacing(
            10
        )

        self.profiles_title = QLabel(
            "Profiles",
            self.navigation_frame,
        )

        self.profiles_title.setObjectName(
            "FaceMemoryNavigationTitle"
        )

        self.profiles_list = QListWidget(
            self.navigation_frame
        )

        self.profiles_list.setObjectName(
            "FaceMemoryProfilesList"
        )

        self.profiles_list.setSelectionMode(
            QAbstractItemView
            .SelectionMode
            .SingleSelection
        )

        self.unassigned_title = QLabel(
            "Unassigned faces",
            self.navigation_frame,
        )

        self.unassigned_title.setObjectName(
            "FaceMemoryNavigationTitle"
        )

        self.unassigned_list = QListWidget(
            self.navigation_frame
        )

        self.unassigned_list.setObjectName(
            "FaceMemoryUnassignedList"
        )

        self.unassigned_list.setViewMode(
            QListWidget.ViewMode.IconMode
        )

        self.unassigned_list.setIconSize(
            QSize(
                64,
                64,
            )
        )

        self.unassigned_list.setGridSize(
            QSize(
                92,
                104,
            )
        )

        self.unassigned_list.setResizeMode(
            QListWidget.ResizeMode.Adjust
        )

        self.unassigned_list.setMovement(
            QListWidget.Movement.Static
        )

        self.unassigned_list.setSelectionMode(
            QAbstractItemView
            .SelectionMode
            .SingleSelection
        )

        layout.addWidget(
            self.profiles_title
        )

        layout.addWidget(
            self.profiles_list,
            3,
        )

        layout.addWidget(
            self.unassigned_title
        )

        layout.addWidget(
            self.unassigned_list,
            2,
        )

    # ==========================================================
    # Details
    # ==========================================================

    def _create_detail_panel(
        self,
    ) -> None:

        self.detail_frame = QFrame(
            self.content_splitter
        )

        self.detail_frame.setObjectName(
            "FaceMemoryDetails"
        )

        self.detail_layout = QVBoxLayout(
            self.detail_frame
        )

        self.detail_layout.setContentsMargins(
            16,
            12,
            16,
            12,
        )

        self.detail_layout.setSpacing(
            12
        )

        # ------------------------------------------------------
        # Empty state
        # ------------------------------------------------------

        self.empty_state = EmptyState(
            title="No Face Profile selected",
            description=(
                "Select a profile to review its "
                "stored face observations."
            ),
            parent=self.detail_frame,
        )

        self.empty_state.setObjectName(
            "FaceMemoryEmptyState"
        )

        self.detail_layout.addWidget(
            self.empty_state,
            1,
        )

        # ------------------------------------------------------
        # Profile content
        # ------------------------------------------------------

        self.profile_content = QWidget(
            self.detail_frame
        )

        self.profile_content.setObjectName(
            "FaceMemoryProfileContent"
        )

        profile_layout = QVBoxLayout(
            self.profile_content
        )

        profile_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        profile_layout.setSpacing(
            12
        )

        self.profile_header_frame = QFrame(
            self.profile_content
        )

        self.profile_header_frame.setObjectName(
            "FaceMemoryProfileHeader"
        )

        header_layout = QVBoxLayout(
            self.profile_header_frame
        )

        header_layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )

        header_layout.setSpacing(
            5
        )

        self.profile_label = QLabel(
            "Profile",
            self.profile_header_frame,
        )

        self.profile_label.setObjectName(
            "FaceMemoryProfileLabel"
        )

        self.profile_label.setTextInteractionFlags(
            Qt.TextInteractionFlag
            .TextSelectableByMouse
        )

        self.profile_description = QLabel(
            "",
            self.profile_header_frame,
        )

        self.profile_description.setObjectName(
            "FaceMemoryProfileDescription"
        )

        self.profile_description.setWordWrap(
            True
        )

        self.profile_description.setTextInteractionFlags(
            Qt.TextInteractionFlag
            .TextSelectableByMouse
        )

        self.profile_metadata = QLabel(
            "",
            self.profile_header_frame,
        )

        self.profile_metadata.setObjectName(
            "FaceMemoryProfileMetadata"
        )

        self.profile_metadata.setWordWrap(
            True
        )

        self.profile_metadata.setTextInteractionFlags(
            Qt.TextInteractionFlag
            .TextSelectableByMouse
        )

        header_layout.addWidget(
            self.profile_label
        )

        header_layout.addWidget(
            self.profile_description
        )

        header_layout.addWidget(
            self.profile_metadata
        )

        profile_layout.addWidget(
            self.profile_header_frame
        )

        # ------------------------------------------------------
        # Actions
        # ------------------------------------------------------

        self.profile_actions = QFrame(
            self.profile_content
        )

        self.profile_actions.setObjectName(
            "FaceMemoryProfileActions"
        )

        actions_layout = QHBoxLayout(
            self.profile_actions
        )

        actions_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        actions_layout.setSpacing(
            8
        )

        self.rename_button = QPushButton(
            "Rename profile",
            self.profile_actions,
        )

        self.description_button = QPushButton(
            "Edit description",
            self.profile_actions,
        )

        self.search_similar_button = QPushButton(
            "Search similar faces",
            self.profile_actions,
        )

        self.delete_profile_button = QPushButton(
            "Delete profile",
            self.profile_actions,
        )

        self.rename_button.setObjectName(
            "FaceMemoryRenameButton"
        )

        self.description_button.setObjectName(
            "FaceMemoryDescriptionButton"
        )

        self.search_similar_button.setObjectName(
            "FaceMemorySearchSimilarButton"
        )

        self.delete_profile_button.setObjectName(
            "FaceMemoryDeleteProfileButton"
        )

        actions_layout.addWidget(
            self.rename_button
        )

        actions_layout.addWidget(
            self.description_button
        )

        actions_layout.addWidget(
            self.search_similar_button
        )

        actions_layout.addStretch(
            1
        )

        actions_layout.addWidget(
            self.delete_profile_button
        )

        profile_layout.addWidget(
            self.profile_actions
        )

        # ------------------------------------------------------
        # Observations
        # ------------------------------------------------------

        self.observations_title = QLabel(
            "Face observations",
            self.profile_content,
        )

        self.observations_title.setObjectName(
            "FaceMemoryObservationsTitle"
        )

        profile_layout.addWidget(
            self.observations_title
        )

        self.observations_list = QListWidget(
            self.profile_content
        )

        self.observations_list.setObjectName(
            "FaceMemoryObservationsList"
        )

        self.observations_list.setViewMode(
            QListWidget.ViewMode.IconMode
        )

        self.observations_list.setIconSize(
            QSize(
                110,
                110,
            )
        )

        self.observations_list.setGridSize(
            QSize(
                145,
                155,
            )
        )

        self.observations_list.setResizeMode(
            QListWidget.ResizeMode.Adjust
        )

        self.observations_list.setMovement(
            QListWidget.Movement.Static
        )

        self.observations_list.setSelectionMode(
            QAbstractItemView
            .SelectionMode
            .SingleSelection
        )

        profile_layout.addWidget(
            self.observations_list,
            1,
        )

        self.observation_actions = QFrame(
            self.profile_content
        )

        observation_actions_layout = QHBoxLayout(
            self.observation_actions
        )

        observation_actions_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.unassign_button = QPushButton(
            "Remove from profile",
            self.observation_actions,
        )

        self.unassign_button.setObjectName(
            "FaceMemoryUnassignButton"
        )

        observation_actions_layout.addStretch(
            1
        )

        observation_actions_layout.addWidget(
            self.unassign_button
        )

        profile_layout.addWidget(
            self.observation_actions
        )

        self.detail_layout.addWidget(
            self.profile_content,
            1,
        )

        self.profile_content.hide()

    # ==========================================================
    # Connections
    # ==========================================================

    def _create_connections(
        self,
    ) -> None:

        self.search_box.textChanged.connect(
            self._on_search_changed
        )

        self.profiles_list.itemSelectionChanged.connect(
            self._on_profile_selected
        )

        self.unassigned_list.itemDoubleClicked.connect(
            self._on_unassigned_double_clicked
        )

        self.observations_list.itemSelectionChanged.connect(
            self._update_observation_actions
        )

        self.observations_list.itemDoubleClicked.connect(
            self._on_observation_double_clicked
        )

        self.refresh_button.clicked.connect(
            self.refresh_requested.emit
        )

        self.create_profile_button.clicked.connect(
            self.create_profile_requested.emit
        )

        self.rename_button.clicked.connect(
            self._emit_rename_profile
        )

        self.description_button.clicked.connect(
            self._emit_edit_description
        )

        self.search_similar_button.clicked.connect(
            self._emit_search_similar
        )

        self.delete_profile_button.clicked.connect(
            self._emit_delete_profile
        )

        self.unassign_button.clicked.connect(
            self._emit_unassign_observation
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def set_face_memory(
        self,
        *,
        profiles: list[dict[str, Any]],
        unassigned: list[dict[str, Any]],
    ) -> None:
        """
        Replace complete Face Memory browser data.
        """

        self.profiles = (
            [
                profile
                for profile in profiles
                if isinstance(
                    profile,
                    dict,
                )
            ]
            if isinstance(
                profiles,
                list,
            )
            else []
        )

        self.unassigned = (
            [
                observation
                for observation in unassigned
                if isinstance(
                    observation,
                    dict,
                )
            ]
            if isinstance(
                unassigned,
                list,
            )
            else []
        )

        self._apply_profile_filter()
        self._populate_unassigned()
        self._update_workspace_state()

    def set_profiles(
        self,
        profiles: list[dict[str, Any]],
    ) -> None:

        self.profiles = (
            [
                profile
                for profile in profiles
                if isinstance(
                    profile,
                    dict,
                )
            ]
            if isinstance(
                profiles,
                list,
            )
            else []
        )

        self._apply_profile_filter()
        self._update_workspace_state()

    def set_unassigned(
        self,
        observations: list[dict[str, Any]],
    ) -> None:

        self.unassigned = (
            [
                observation
                for observation in observations
                if isinstance(
                    observation,
                    dict,
                )
            ]
            if isinstance(
                observations,
                list,
            )
            else []
        )

        self._populate_unassigned()
        self._update_workspace_state()

    def clear(
        self,
    ) -> None:

        self.profiles = []
        self.filtered_profiles = []
        self.unassigned = []

        self.profiles_list.clear()
        self.unassigned_list.clear()
        self.observations_list.clear()

        self._selected_profile = None

        self._show_empty_state()
        self._update_workspace_state()

    # ==========================================================
    # Filtering
    # ==========================================================

    def _on_search_changed(
        self,
        text: str,
    ) -> None:

        self._search_text = str(
            text
            or ""
        ).strip().lower()

        self._apply_profile_filter()

    def _apply_profile_filter(
        self,
    ) -> None:

        if not self._search_text:

            self.filtered_profiles = list(
                self.profiles
            )

        else:

            query = self._search_text

            self.filtered_profiles = [
                profile
                for profile in self.profiles
                if query
                in self._profile_search_text(
                    profile
                )
            ]

        self._populate_profiles()

    @staticmethod
    def _profile_search_text(
        profile: dict[str, Any],
    ) -> str:

        values = [
            profile.get(
                "label"
            ),
            profile.get(
                "description"
            ),
            profile.get(
                "status"
            ),
            profile.get(
                "id"
            ),
        ]

        return " ".join(
            str(
                value
                or ""
            ).lower()
            for value in values
        )

    # ==========================================================
    # Population
    # ==========================================================

    def _populate_profiles(
        self,
    ) -> None:

        selected_profile_id = (
            self._selected_profile_id()
        )

        self.profiles_list.blockSignals(
            True
        )

        self.profiles_list.clear()

        restore_row: int | None = None

        for row, profile in enumerate(
            self.filtered_profiles
        ):

            profile_id = str(
                profile.get(
                    "id"
                )
                or ""
            )

            label = str(
                profile.get(
                    "label"
                )
                or "Unnamed profile"
            )

            count = self._profile_embedding_count(
                profile
            )

            text = (
                f"{label}\n"
                f"{count} observation"
                + (
                    ""
                    if count == 1
                    else "s"
                )
            )

            item = QListWidgetItem(
                text
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                dict(
                    profile
                ),
            )

            self.profiles_list.addItem(
                item
            )

            if (
                selected_profile_id
                and profile_id
                == selected_profile_id
            ):

                restore_row = row

        self.profiles_list.blockSignals(
            False
        )

        if restore_row is not None:

            self.profiles_list.setCurrentRow(
                restore_row
            )

    def _populate_unassigned(
        self,
    ) -> None:

        self.unassigned_list.clear()

        for observation in self.unassigned:

            face_id = str(
                observation.get(
                    "face_id"
                )
                or "Face"
            )

            item = QListWidgetItem(
                face_id
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                dict(
                    observation
                ),
            )

            icon = self._observation_icon(
                observation,
                size=64,
            )

            if not icon.isNull():

                item.setIcon(
                    icon
                )

            self.unassigned_list.addItem(
                item
            )

    def _populate_profile_details(
        self,
        profile: dict[str, Any],
    ) -> None:

        self._selected_profile = dict(
            profile
        )

        label = str(
            profile.get(
                "label"
            )
            or "Unnamed profile"
        )

        description = str(
            profile.get(
                "description"
            )
            or ""
        ).strip()

        status = str(
            profile.get(
                "status"
            )
            or "active"
        )

        observations = profile.get(
            "embeddings",
            [],
        )

        if not isinstance(
            observations,
            list,
        ):

            observations = []

        count = int(
            profile.get(
                "embedding_count",
                len(
                    observations
                ),
            )
            or 0
        )

        self.profile_label.setText(
            label
        )

        self.profile_description.setText(
            (
                description
                if description
                else "No description"
            )
        )

        self.profile_metadata.setText(
            (
                f"Observations: {count}   "
                f"Status: {status}   "
                f"Profile ID: "
                f"{profile.get('id', '—')}"
            )
        )

        self.observations_list.clear()

        for observation in observations:

            if not isinstance(
                observation,
                dict,
            ):

                continue

            face_id = str(
                observation.get(
                    "face_id"
                )
                or "Face"
            )

            evidence_id = str(
                observation.get(
                    "evidence_id"
                )
                or ""
            )

            display_text = (
                face_id
            )

            if evidence_id:

                display_text += (
                    "\n"
                    + self._short_identifier(
                        evidence_id
                    )
                )

            item = QListWidgetItem(
                display_text
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                dict(
                    observation
                ),
            )

            icon = self._observation_icon(
                observation,
                size=110,
            )

            if not icon.isNull():

                item.setIcon(
                    icon
                )

            self.observations_list.addItem(
                item
            )

        self.empty_state.hide()
        self.profile_content.show()

        self._update_observation_actions()

    # ==========================================================
    # Selection
    # ==========================================================

    def _on_profile_selected(
        self,
    ) -> None:

        item = (
            self.profiles_list
            .currentItem()
        )

        if item is None:

            self._selected_profile = None
            self._show_empty_state()

            return

        profile = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(
            profile,
            dict,
        ):

            self._selected_profile = None
            self._show_empty_state()

            return

        self._populate_profile_details(
            profile
        )

    def _on_unassigned_double_clicked(
        self,
        item: QListWidgetItem,
    ) -> None:

        observation = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(
            observation,
            dict,
        ):

            return

        embedding_id = str(
            observation.get(
                "id"
            )
            or observation.get(
                "embedding_id"
            )
            or ""
        ).strip()

        if not embedding_id:

            return

        self.assign_observation_requested.emit(
            embedding_id
        )

    def _on_observation_double_clicked(
        self,
        item: QListWidgetItem,
    ) -> None:

        observation = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(
            observation,
            dict,
        ):

            return

        embedding_id = str(
            observation.get(
                "id"
            )
            or observation.get(
                "embedding_id"
            )
            or ""
        ).strip()

        if embedding_id:

            self.observation_selected.emit(
                embedding_id
            )

    # ==========================================================
    # Actions
    # ==========================================================

    def _emit_rename_profile(
        self,
    ) -> None:

        profile_id = (
            self._selected_profile_id()
        )

        if profile_id:

            self.rename_profile_requested.emit(
                profile_id
            )

    def _emit_edit_description(
        self,
    ) -> None:

        profile_id = (
            self._selected_profile_id()
        )

        if profile_id:

            self.edit_description_requested.emit(
                profile_id
            )

    def _emit_search_similar(
        self,
    ) -> None:

        profile_id = (
            self._selected_profile_id()
        )

        if profile_id:

            self.search_similar_requested.emit(
                profile_id
            )

    def _emit_delete_profile(
        self,
    ) -> None:

        profile_id = (
            self._selected_profile_id()
        )

        if profile_id:

            self.delete_profile_requested.emit(
                profile_id
            )

    def _emit_unassign_observation(
        self,
    ) -> None:

        item = (
            self.observations_list
            .currentItem()
        )

        if item is None:

            return

        observation = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(
            observation,
            dict,
        ):

            return

        embedding_id = str(
            observation.get(
                "id"
            )
            or observation.get(
                "embedding_id"
            )
            or ""
        ).strip()

        if embedding_id:

            self.unassign_observation_requested.emit(
                embedding_id
            )

    # ==========================================================
    # State
    # ==========================================================

    def _show_empty_state(
        self,
    ) -> None:

        self.profile_content.hide()
        self.empty_state.show()

    def _update_workspace_state(
        self,
    ) -> None:

        profile_count = len(
            self.profiles
        )

        unassigned_count = len(
            self.unassigned
        )

        self.profile_count_badge.setText(
            (
                f"{profile_count} profile"
                if profile_count == 1
                else f"{profile_count} profiles"
            )
        )

        self.unassigned_count_badge.setText(
            (
                f"{unassigned_count} unassigned"
            )
        )

    def _update_observation_actions(
        self,
    ) -> None:

        enabled = (
            self.observations_list
            .currentItem()
            is not None
        )

        self.unassign_button.setEnabled(
            enabled
        )

    # ==========================================================
    # Face thumbnails
    # ==========================================================

    def _observation_icon(
        self,
        observation: dict[str, Any],
        *,
        size: int,
    ) -> QIcon:

        image_path = str(
            observation.get(
                "image_path"
            )
            or ""
        ).strip()

        if not image_path:

            return QIcon()

        path = Path(
            image_path
        )

        if (
            not path.exists()
            or not path.is_file()
        ):

            return QIcon()

        pixmap = QPixmap(
            str(
                path
            )
        )

        if pixmap.isNull():

            return QIcon()

        bbox = observation.get(
            "bbox"
        )

        crop_rect = self._bbox_to_rect(
            bbox=bbox,
            image_width=pixmap.width(),
            image_height=pixmap.height(),
        )

        if crop_rect is not None:

            pixmap = pixmap.copy(
                crop_rect
            )

        pixmap = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        return QIcon(
            pixmap
        )

    @classmethod
    def _bbox_to_rect(
        cls,
        *,
        bbox: Any,
        image_width: int,
        image_height: int,
    ) -> QRect | None:

        if not isinstance(
            bbox,
            dict,
        ):

            return None

        try:

            x = float(
                bbox.get(
                    "x"
                )
            )

            y = float(
                bbox.get(
                    "y"
                )
            )

            width = float(
                bbox.get(
                    "width"
                )
            )

            height = float(
                bbox.get(
                    "height"
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        if (
            width <= 0
            or height <= 0
        ):

            return None

        padding_x = (
            width
            * cls.FACE_CROP_PADDING
        )

        padding_y = (
            height
            * cls.FACE_CROP_PADDING
        )

        left = max(
            0,
            int(
                x - padding_x
            ),
        )

        top = max(
            0,
            int(
                y - padding_y
            ),
        )

        right = min(
            image_width,
            int(
                x
                + width
                + padding_x
            ),
        )

        bottom = min(
            image_height,
            int(
                y
                + height
                + padding_y
            ),
        )

        crop_width = (
            right
            - left
        )

        crop_height = (
            bottom
            - top
        )

        if (
            crop_width <= 0
            or crop_height <= 0
        ):

            return None

        return QRect(
            left,
            top,
            crop_width,
            crop_height,
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    def _selected_profile_id(
        self,
    ) -> str | None:

        if not isinstance(
            self._selected_profile,
            dict,
        ):

            return None

        profile_id = str(
            self._selected_profile.get(
                "id"
            )
            or ""
        ).strip()

        if not profile_id:

            return None

        return profile_id

    @staticmethod
    def _profile_embedding_count(
        profile: dict[str, Any],
    ) -> int:

        value = profile.get(
            "embedding_count"
        )

        if value is not None:

            try:

                return int(
                    value
                )

            except (
                TypeError,
                ValueError,
            ):

                pass

        embeddings = profile.get(
            "embeddings"
        )

        if isinstance(
            embeddings,
            list,
        ):

            return len(
                embeddings
            )

        return 0

    @staticmethod
    def _short_identifier(
        value: Any,
    ) -> str:

        text = str(
            value
            or ""
        ).strip()

        if len(
            text
        ) <= 12:

            return text

        return (
            text[:8]
            + "…"
        )

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Refresh visible Face Memory text.

        Translation keys can be added later without
        changing the public interface of this view.
        """

        self.face_memory_section.set_title(
            self.translate(
                "workspace.face_memory.title",
                default="Face Memory",
            )
        )

        self.face_memory_section.set_description(
            self.translate(
                "workspace.face_memory.description",
                default=(
                    "Review user-managed face profiles, "
                    "stored observations and unassigned "
                    "faces detected during investigations."
                ),
            )
        )

        self.search_box.setPlaceholderText(
            self.translate(
                "workspace.face_memory.search",
                default=(
                    "Search Face Memory profiles..."
                ),
            )
        )

        self.create_profile_button.setText(
            self.translate(
                "workspace.face_memory.create_profile",
                default="Create profile",
            )
        )

        self.refresh_button.setText(
            self.translate(
                "common.refresh",
                default="Refresh",
            )
        )

        self.profiles_title.setText(
            self.translate(
                "workspace.face_memory.profiles",
                default="Profiles",
            )
        )

        self.unassigned_title.setText(
            self.translate(
                "workspace.face_memory.unassigned",
                default="Unassigned faces",
            )
        )

        self.rename_button.setText(
            self.translate(
                "workspace.face_memory.rename",
                default="Rename profile",
            )
        )

        self.description_button.setText(
            self.translate(
                "workspace.face_memory.edit_description",
                default="Edit description",
            )
        )

        self.search_similar_button.setText(
            self.translate(
                "workspace.face_memory.search_similar",
                default="Search similar faces",
            )
        )

        self.delete_profile_button.setText(
            self.translate(
                "workspace.face_memory.delete_profile",
                default="Delete profile",
            )
        )

        self.observations_title.setText(
            self.translate(
                "workspace.face_memory.observations",
                default="Face observations",
            )
        )

        self.unassign_button.setText(
            self.translate(
                "workspace.face_memory.remove_observation",
                default="Remove from profile",
            )
        )

        self._update_workspace_state()
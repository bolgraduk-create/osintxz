"""
Photo investigation workspace.

Responsible for:

- displaying image evidence
- showing image thumbnails
- displaying the selected image
- controlling image zoom and rotation
- displaying image metadata and analysis sections
- emitting image-related user actions
- filtering and sorting images

Does NOT:

- access the database
- modify original files
- execute OCR
- extract EXIF directly
- run object or face detection
- execute AI analysis
"""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QSize,
    Qt,
    Signal,
)

from PySide6.QtGui import (
    QDesktopServices,
    QIcon,
    QPixmap,
)

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.interface.desktop.localization import (
    TranslatableMixin,
)

from app.interface.desktop.widgets.image_viewer import (
    ImageViewer,
)

from app.localization import (
    TranslationManager,
    get_translation_manager,
)


class PhotoWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Specialized workspace for image evidence.
    """

    # ==========================================================
    # Import and file operations
    # ==========================================================

    import_images_requested = Signal()

    open_original_requested = Signal(
        str
    )

    reveal_in_folder_requested = Signal(
        str
    )

    delete_image_requested = Signal(
        str
    )

    export_image_requested = Signal(
        str
    )

    # ==========================================================
    # Processing operations
    # ==========================================================

    analyze_image_requested = Signal(
        str
    )

    reprocess_image_requested = Signal(
        str
    )

    extract_metadata_requested = Signal(
        str
    )

    run_ocr_requested = Signal(
        str
    )

    detect_codes_requested = Signal(
        str
    )

    detect_faces_requested = Signal(
        str
    )

    find_face_matches_requested = Signal(
        str,
        str,
    )

    detect_objects_requested = Signal(
        str
    )

    calculate_hashes_requested = Signal(
        str
    )

    analyze_integrity_requested = Signal(
        str
    )

    # ==========================================================
    # Investigation operations
    # ==========================================================

    compare_images_requested = Signal(
        str,
        str,
    )

    find_similar_requested = Signal(
        str
    )

    add_to_timeline_requested = Signal(
        str
    )

    create_location_requested = Signal(
        str
    )

    create_evidence_requested = Signal(
        dict
    )

    # ==========================================================
    # AI
    # ==========================================================

    ask_ai_requested = Signal(
        str,
        str,
    )

    generate_ai_summary_requested = Signal(
        str
    )

    # ==========================================================
    # Selection
    # ==========================================================

    image_selected = Signal(
        dict
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self.images: list[
            dict[str, Any]
        ] = []

        self.filtered_images: list[
            dict[str, Any]
        ] = []

        self._selected_image: (
            dict[str, Any] | None
        ) = None

        self._comparison_mode = False

        self._comparison_source_id: (
            str | None
        ) = None

        self._search_text = ""

        self._setup_ui()
        self._create_connections()

        active_translation_manager = (
            translation_manager
            if translation_manager is not None
            else get_translation_manager()
        )

        self.initialize_translations(
            active_translation_manager
        )

        self._update_state()

    # ==========================================================
    # UI setup
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create complete photo workspace interface.
        """

        self.setObjectName(
            "PhotoWorkspaceView"
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            16,
            16,
            16,
            16,
        )

        self.main_layout.setSpacing(
            12
        )

        self._create_header()
        self._create_toolbar()
        self._create_main_splitter()
        self._create_status_bar()

    # ==========================================================
    # Header
    # ==========================================================

    def _create_header(
        self,
    ) -> None:
        """
        Create workspace title and primary actions.
        """

        self.header = QFrame(
            self
        )

        self.header.setObjectName(
            "PhotoWorkspaceHeader"
        )

        self.header_layout = QHBoxLayout(
            self.header
        )

        self.header_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.header_layout.setSpacing(
            10
        )

        title_container = QWidget(
            self.header
        )

        title_layout = QVBoxLayout(
            title_container
        )

        title_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        title_layout.setSpacing(
            2
        )

        self.title_label = QLabel(
            "Photos",
            title_container,
        )

        self.title_label.setObjectName(
            "PhotoWorkspaceTitle"
        )

        self.description_label = QLabel(
            (
                "Review, inspect and analyze image evidence "
                "inside the current investigation."
            ),
            title_container,
        )

        self.description_label.setObjectName(
            "PhotoWorkspaceDescription"
        )

        self.description_label.setWordWrap(
            True
        )

        title_layout.addWidget(
            self.title_label
        )

        title_layout.addWidget(
            self.description_label
        )

        self.import_button = QPushButton(
            "Import photos...",
            self.header,
        )

        self.import_button.setObjectName(
            "PhotoImportButton"
        )

        self.import_button.setProperty(
            "variant",
            "primary",
        )

        self.import_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.analyze_all_button = QPushButton(
            "Analyze all",
            self.header,
        )

        self.analyze_all_button.setObjectName(
            "PhotoAnalyzeAllButton"
        )

        self.analyze_all_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.header_layout.addWidget(
            title_container,
            1,
        )

        self.header_layout.addWidget(
            self.analyze_all_button
        )

        self.header_layout.addWidget(
            self.import_button
        )

        self.main_layout.addWidget(
            self.header
        )

    # ==========================================================
    # Toolbar
    # ==========================================================

    def _create_toolbar(
        self,
    ) -> None:
        """
        Create search, filtering and sorting toolbar.
        """

        self.toolbar = QFrame(
            self
        )

        self.toolbar.setObjectName(
            "PhotoWorkspaceToolbar"
        )

        self.toolbar_layout = QHBoxLayout(
            self.toolbar
        )

        self.toolbar_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.toolbar_layout.setSpacing(
            8
        )

        self.search_input = QLineEdit(
            self.toolbar
        )

        self.search_input.setObjectName(
            "PhotoSearchInput"
        )

        self.search_input.setPlaceholderText(
            "Search photos..."
        )

        self.search_input.setClearButtonEnabled(
            True
        )

        self.search_input.setMinimumWidth(
            260
        )

        self.type_filter = QComboBox(
            self.toolbar
        )

        self.type_filter.setObjectName(
            "PhotoTypeFilter"
        )

        self.type_filter.addItem(
            "All formats",
            "all",
        )

        self.type_filter.addItem(
            "JPEG",
            "jpeg",
        )

        self.type_filter.addItem(
            "PNG",
            "png",
        )

        self.type_filter.addItem(
            "WEBP",
            "webp",
        )

        self.type_filter.addItem(
            "TIFF",
            "tiff",
        )

        self.type_filter.addItem(
            "GIF",
            "gif",
        )

        self.type_filter.addItem(
            "Other",
            "other",
        )

        self.status_filter = QComboBox(
            self.toolbar
        )

        self.status_filter.setObjectName(
            "PhotoStatusFilter"
        )

        self.status_filter.addItem(
            "All statuses",
            "all",
        )

        self.status_filter.addItem(
            "Processed",
            "completed",
        )

        self.status_filter.addItem(
            "Pending",
            "pending",
        )

        self.status_filter.addItem(
            "Failed",
            "failed",
        )

        self.sort_combo = QComboBox(
            self.toolbar
        )

        self.sort_combo.setObjectName(
            "PhotoSortCombo"
        )

        self.sort_combo.addItem(
            "Name",
            "name",
        )

        self.sort_combo.addItem(
            "Recently imported",
            "created_desc",
        )

        self.sort_combo.addItem(
            "Oldest imported",
            "created_asc",
        )

        self.sort_combo.addItem(
            "Largest first",
            "size_desc",
        )

        self.sort_combo.addItem(
            "Smallest first",
            "size_asc",
        )

        self.sort_combo.addItem(
            "Capture date",
            "capture_date",
        )

        self.photo_count_label = QLabel(
            "0 images",
            self.toolbar,
        )

        self.photo_count_label.setObjectName(
            "PhotoCountLabel"
        )

        self.toolbar_layout.addWidget(
            self.search_input,
            1,
        )

        self.toolbar_layout.addWidget(
            self.type_filter
        )

        self.toolbar_layout.addWidget(
            self.status_filter
        )

        self.toolbar_layout.addWidget(
            self.sort_combo
        )

        self.toolbar_layout.addWidget(
            self.photo_count_label
        )

        self.main_layout.addWidget(
            self.toolbar
        )

    # ==========================================================
    # Main splitter
    # ==========================================================

    def _create_main_splitter(
        self,
    ) -> None:
        """
        Create library, viewer and analysis panels.
        """

        self.main_splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )

        self.main_splitter.setObjectName(
            "PhotoWorkspaceSplitter"
        )

        self.main_splitter.setChildrenCollapsible(
            False
        )

        self._create_library_panel()
        self._create_viewer_panel()
        self._create_analysis_panel()

        self.main_splitter.addWidget(
            self.library_panel
        )

        self.main_splitter.addWidget(
            self.viewer_panel
        )

        self.main_splitter.addWidget(
            self.analysis_panel
        )

        self.main_splitter.setStretchFactor(
            0,
            2,
        )

        self.main_splitter.setStretchFactor(
            1,
            5,
        )

        self.main_splitter.setStretchFactor(
            2,
            3,
        )

        self.main_splitter.setSizes(
            [
                245,
                610,
                430,
            ]
        )

        self.main_layout.addWidget(
            self.main_splitter,
            1,
        )

    # ==========================================================
    # Image library
    # ==========================================================

    def _create_library_panel(
        self,
    ) -> None:
        """
        Create the left image library.
        """

        self.library_panel = QFrame(
            self.main_splitter
        )

        self.library_panel.setObjectName(
            "PhotoLibraryPanel"
        )

        self.library_panel.setMinimumWidth(
            220
        )

        self.library_layout = QVBoxLayout(
            self.library_panel
        )

        self.library_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.library_layout.setSpacing(
            8
        )

        self.library_title = QLabel(
            "Image library",
            self.library_panel,
        )

        self.library_title.setObjectName(
            "PhotoLibraryTitle"
        )

        self.photo_list = QListWidget(
            self.library_panel
        )

        self.photo_list.setObjectName(
            "PhotoLibraryList"
        )

        self.photo_list.setViewMode(
            QListWidget.ViewMode.IconMode
        )

        self.photo_list.setResizeMode(
            QListWidget.ResizeMode.Adjust
        )

        self.photo_list.setMovement(
            QListWidget.Movement.Static
        )

        self.photo_list.setWrapping(
            True
        )

        self.photo_list.setIconSize(
            QSize(
                132,
                96,
            )
        )

        self.photo_list.setGridSize(
            QSize(
                168,
                146,
            )
        )

        self.photo_list.setSpacing(
            6
        )

        self.photo_list.setSelectionMode(
            QAbstractItemView
            .SelectionMode
            .SingleSelection
        )

        self.photo_list.setVerticalScrollMode(
            QAbstractItemView
            .ScrollMode
            .ScrollPerPixel
        )

        self.photo_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.library_actions = QHBoxLayout()

        self.library_actions.setSpacing(
            6
        )

        self.select_all_button = QPushButton(
            "Select all",
            self.library_panel,
        )

        self.clear_selection_button = QPushButton(
            "Clear",
            self.library_panel,
        )

        self.library_actions.addWidget(
            self.select_all_button
        )

        self.library_actions.addWidget(
            self.clear_selection_button
        )

        self.library_layout.addWidget(
            self.library_title
        )

        self.library_layout.addWidget(
            self.photo_list,
            1,
        )

        self.library_layout.addLayout(
            self.library_actions
        )

    # ==========================================================
    # Viewer
    # ==========================================================

    def _create_viewer_panel(
        self,
    ) -> None:
        """
        Create central image viewing panel.
        """

        self.viewer_panel = QFrame(
            self.main_splitter
        )

        self.viewer_panel.setObjectName(
            "PhotoViewerPanel"
        )

        self.viewer_layout = QVBoxLayout(
            self.viewer_panel
        )

        self.viewer_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.viewer_layout.setSpacing(
            10
        )

        self.viewer_header = QFrame(
            self.viewer_panel
        )

        self.viewer_header.setObjectName(
            "PhotoViewerHeader"
        )

        self.viewer_header_layout = QHBoxLayout(
            self.viewer_header
        )

        self.viewer_header_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.viewer_header_layout.setSpacing(
            8
        )

        self.selected_title_label = QLabel(
            "No image selected",
            self.viewer_header,
        )

        self.selected_title_label.setObjectName(
            "PhotoSelectedTitle"
        )

        self.selected_title_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.selected_title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.selected_title_label.setWordWrap(
            False
        )

        self.selected_dimensions_label = QLabel(
            "",
            self.viewer_header,
        )

        self.selected_dimensions_label.setObjectName(
            "PhotoSelectedDimensions"
        )

        self.selected_dimensions_label.setMinimumWidth(
            90
        )

        self.selected_dimensions_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.viewer_header_layout.addWidget(
            self.selected_title_label,
            1,
        )

        self.viewer_header_layout.addWidget(
            self.selected_dimensions_label
        )

        self.image_viewer = ImageViewer(
            self.viewer_panel
        )

        self.image_viewer.setObjectName(
            "PhotoMainImageViewer"
        )

        self.image_viewer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.image_viewer.setMinimumHeight(
            300
        )

        self.viewer_empty_label = QLabel(
            (
                "Select an image from the library "
                "to display it here."
            ),
            self.image_viewer.viewport(),
        )

        self.viewer_empty_label.setObjectName(
            "PhotoViewerEmptyLabel"
        )

        self.viewer_empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.viewer_empty_label.setWordWrap(
            True
        )

        self.viewer_empty_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        self.viewer_empty_label.setGeometry(
            self.image_viewer.viewport().rect()
        )

        self._create_viewer_controls()
        self._create_overlay_controls()

        self.viewer_layout.addWidget(
            self.viewer_header
        )

        self.viewer_layout.addWidget(
            self.image_viewer,
            1,
        )

        self.viewer_layout.addSpacing(
            4
        )

        self.viewer_layout.addWidget(
            self.viewer_controls
        )

        self.viewer_layout.addWidget(
            self.overlay_controls
        )

    def _create_viewer_controls(
        self,
    ) -> None:
        """Create responsive zoom and view controls."""

        self.viewer_controls = QFrame(self.viewer_panel)
        self.viewer_controls.setObjectName("PhotoViewerControls")

        self.viewer_controls_layout = QVBoxLayout(self.viewer_controls)
        self.viewer_controls_layout.setContentsMargins(0, 6, 0, 0)
        self.viewer_controls_layout.setSpacing(8)

        self.zoom_row = QFrame(self.viewer_controls)
        self.zoom_row_layout = QHBoxLayout(self.zoom_row)
        self.zoom_row_layout.setContentsMargins(0, 0, 0, 0)
        self.zoom_row_layout.setSpacing(8)

        self.zoom_label = QLabel("Zoom", self.zoom_row)
        self.zoom_label.setMinimumWidth(42)

        self.zoom_out_button = QToolButton(self.zoom_row)
        self.zoom_out_button.setText("−")
        self.zoom_out_button.setToolTip("Zoom out")
        self.zoom_out_button.setFixedSize(32, 30)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal, self.zoom_row)
        self.zoom_slider.setObjectName("PhotoZoomSlider")
        self.zoom_slider.setRange(5, 500)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setMinimumWidth(160)
        self.zoom_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.zoom_percent_label = QLabel("100%", self.zoom_row)
        self.zoom_percent_label.setObjectName("PhotoZoomPercentLabel")
        self.zoom_percent_label.setFixedWidth(58)
        self.zoom_percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.zoom_in_button = QToolButton(self.zoom_row)
        self.zoom_in_button.setText("+")
        self.zoom_in_button.setToolTip("Zoom in")
        self.zoom_in_button.setFixedSize(32, 30)

        self.zoom_row_layout.addWidget(self.zoom_label)
        self.zoom_row_layout.addWidget(self.zoom_out_button)
        self.zoom_row_layout.addWidget(self.zoom_slider, 1)
        self.zoom_row_layout.addWidget(self.zoom_percent_label)
        self.zoom_row_layout.addWidget(self.zoom_in_button)

        self.view_actions_row = QFrame(self.viewer_controls)
        self.view_actions_layout = QGridLayout(self.view_actions_row)
        self.view_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.view_actions_layout.setHorizontalSpacing(6)
        self.view_actions_layout.setVerticalSpacing(6)

        self.fit_button = QPushButton("Fit", self.view_actions_row)
        self.actual_size_button = QPushButton("1:1", self.view_actions_row)
        self.rotate_left_button = QPushButton("Rotate left", self.view_actions_row)
        self.rotate_right_button = QPushButton("Rotate right", self.view_actions_row)
        self.reset_view_button = QPushButton("Reset", self.view_actions_row)
        self.fullscreen_button = QPushButton("Full screen", self.view_actions_row)
        self.open_original_button = QPushButton("Open original", self.view_actions_row)

        for button in (self.fit_button, self.actual_size_button, self.reset_view_button):
            button.setMinimumWidth(70)
            button.setMinimumHeight(32)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        for button in (self.rotate_left_button, self.rotate_right_button, self.fullscreen_button, self.open_original_button):
            button.setMinimumWidth(112)
            button.setMinimumHeight(32)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.view_actions_layout.addWidget(self.fit_button, 0, 0)
        self.view_actions_layout.addWidget(self.actual_size_button, 0, 1)
        self.view_actions_layout.addWidget(self.rotate_left_button, 0, 2)
        self.view_actions_layout.addWidget(self.rotate_right_button, 0, 3)
        self.view_actions_layout.addWidget(self.reset_view_button, 1, 0)
        self.view_actions_layout.addWidget(self.fullscreen_button, 1, 1, 1, 2)
        self.view_actions_layout.addWidget(self.open_original_button, 1, 3)

        for column in range(4):
            self.view_actions_layout.setColumnStretch(column, 1)

        self.viewer_controls_layout.addWidget(self.zoom_row)
        self.viewer_controls_layout.addWidget(self.view_actions_row)

    def _create_overlay_controls(
        self,
    ) -> None:
        """Create responsive overlay controls."""

        self.overlay_controls = QFrame(self.viewer_panel)
        self.overlay_controls.setObjectName("PhotoOverlayControls")
        self.overlay_controls_layout = QGridLayout(self.overlay_controls)
        self.overlay_controls_layout.setContentsMargins(0, 2, 0, 0)
        self.overlay_controls_layout.setHorizontalSpacing(12)
        self.overlay_controls_layout.setVerticalSpacing(6)

        self.overlay_title_label = QLabel("Overlays:", self.overlay_controls)
        self.ocr_overlay_checkbox = QCheckBox("OCR boxes", self.overlay_controls)
        self.faces_overlay_checkbox = QCheckBox("Faces", self.overlay_controls)
        self.objects_overlay_checkbox = QCheckBox("Objects", self.overlay_controls)
        self.codes_overlay_checkbox = QCheckBox("Codes", self.overlay_controls)
        self.integrity_overlay_checkbox = QCheckBox("Integrity indicators", self.overlay_controls)

        self.overlay_controls_layout.addWidget(self.overlay_title_label, 0, 0)
        self.overlay_controls_layout.addWidget(self.ocr_overlay_checkbox, 0, 1)
        self.overlay_controls_layout.addWidget(self.faces_overlay_checkbox, 0, 2)
        self.overlay_controls_layout.addWidget(self.objects_overlay_checkbox, 0, 3)
        self.overlay_controls_layout.addWidget(self.codes_overlay_checkbox, 1, 1)
        self.overlay_controls_layout.addWidget(self.integrity_overlay_checkbox, 1, 2, 1, 2)
        self.overlay_controls_layout.setColumnStretch(4, 1)

    # ==========================================================
    # Analysis panel
    # ==========================================================

    def _create_analysis_panel(
        self,
    ) -> None:
        """
        Create right-side analysis tabs.
        """

        self.analysis_panel = QFrame(
            self.main_splitter
        )

        self.analysis_panel.setObjectName(
            "PhotoAnalysisPanel"
        )

        self.analysis_panel.setMinimumWidth(
            390
        )

        self.analysis_layout = QVBoxLayout(
            self.analysis_panel
        )

        self.analysis_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.analysis_layout.setSpacing(
            8
        )

        self.analysis_header = QLabel(
            "Image analysis",
            self.analysis_panel,
        )

        self.analysis_header.setObjectName(
            "PhotoAnalysisHeader"
        )

        self.analysis_tabs = QTabWidget(
            self.analysis_panel
        )

        self.analysis_tabs.setObjectName(
            "PhotoAnalysisTabs"
        )

        self.analysis_tabs.setDocumentMode(
            True
        )

        self.analysis_tabs.setUsesScrollButtons(True)
        self.analysis_tabs.tabBar().setExpanding(False)
        self.analysis_tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)

        self._create_overview_tab()
        self._create_metadata_tab()
        self._create_ocr_tab()
        self._create_codes_tab()
        self._create_faces_tab()
        self._create_objects_tab()
        self._create_hashes_tab()
        self._create_integrity_tab()
        self._create_ai_tab()
        self._create_actions_tab()

        self.analysis_layout.addWidget(
            self.analysis_header
        )

        self.analysis_layout.addWidget(
            self.analysis_tabs,
            1,
        )

    # ==========================================================
    # Analysis tabs
    # ==========================================================

    def _create_overview_tab(
        self,
    ) -> None:
        """
        Create basic information tab.
        """

        self.overview_tab = QWidget()

        layout = QVBoxLayout(
            self.overview_tab
        )

        self.overview_text = QPlainTextEdit(
            self.overview_tab
        )

        self.overview_text.setReadOnly(
            True
        )

        self.overview_text.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )

        self.overview_text.setPlaceholderText(
            "Basic image information will appear here."
        )

        self.analyze_image_button = QPushButton(
            "Run complete image analysis",
            self.overview_tab,
        )

        self.reprocess_image_button = QPushButton(
            "Reprocess image",
            self.overview_tab,
        )

        layout.addWidget(
            self.overview_text,
            1,
        )

        layout.addWidget(
            self.analyze_image_button
        )

        layout.addWidget(
            self.reprocess_image_button
        )

        self.analysis_tabs.addTab(
            self.overview_tab,
            "Overview",
        )

    def _create_metadata_tab(
        self,
    ) -> None:
        """
        Create EXIF and technical metadata tab.
        """

        self.metadata_tab = QWidget()

        layout = QVBoxLayout(
            self.metadata_tab
        )

        self.metadata_text = QPlainTextEdit(
            self.metadata_tab
        )

        self.metadata_text.setReadOnly(
            True
        )

        self.metadata_text.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )

        self.metadata_text.setPlaceholderText(
            (
                "EXIF, XMP, IPTC, GPS and device "
                "metadata will appear here."
            )
        )

        self.extract_metadata_button = QPushButton(
            "Extract metadata",
            self.metadata_tab,
        )

        self.create_location_button = QPushButton(
            "Create location from GPS",
            self.metadata_tab,
        )

        layout.addWidget(
            self.metadata_text,
            1,
        )

        layout.addWidget(
            self.extract_metadata_button
        )

        layout.addWidget(
            self.create_location_button
        )

        self.analysis_tabs.addTab(
            self.metadata_tab,
            "Metadata",
        )

    def _create_ocr_tab(
        self,
    ) -> None:
        """
        Create OCR results tab.
        """

        self.ocr_tab = QWidget()

        layout = QVBoxLayout(
            self.ocr_tab
        )

        controls = QHBoxLayout()

        self.ocr_language_combo = QComboBox(
            self.ocr_tab
        )

        self.ocr_language_combo.addItem(
            "Automatic",
            "auto",
        )

        self.ocr_language_combo.addItem(
            "English",
            "eng",
        )

        self.ocr_language_combo.addItem(
            "Russian",
            "rus",
        )

        self.ocr_language_combo.addItem(
            "Ukrainian",
            "ukr",
        )

        self.ocr_language_combo.addItem(
            "Bulgarian",
            "bul",
        )

        self.run_ocr_button = QPushButton(
            "Run OCR",
            self.ocr_tab,
        )

        self.copy_ocr_button = QPushButton(
            "Copy text",
            self.ocr_tab,
        )

        self.create_ocr_evidence_button = QPushButton(
            "Create evidence",
            self.ocr_tab,
        )

        controls.addWidget(
            self.ocr_language_combo
        )

        controls.addWidget(
            self.run_ocr_button
        )

        controls.addWidget(
            self.copy_ocr_button
        )

        self.ocr_text = QPlainTextEdit(
            self.ocr_tab
        )

        self.ocr_text.setReadOnly(
            True
        )

        self.ocr_text.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )

        self.ocr_text.setPlaceholderText(
            "Recognized text will appear here."
        )

        layout.addLayout(
            controls
        )

        layout.addWidget(
            self.ocr_text,
            1,
        )

        layout.addWidget(
            self.create_ocr_evidence_button
        )

        self.analysis_tabs.addTab(
            self.ocr_tab,
            "Text",
        )

    def _create_codes_tab(
        self,
    ) -> None:
        """
        Create QR and barcode results tab.
        """

        self.codes_tab = QWidget()

        layout = QVBoxLayout(
            self.codes_tab
        )

        self.codes_list = QListWidget(
            self.codes_tab
        )


        self.detect_codes_button = QPushButton(
            "Detect QR and barcodes",
            self.codes_tab,
        )

        self.copy_code_button = QPushButton(
            "Copy selected value",
            self.codes_tab,
        )

        self.create_code_evidence_button = QPushButton(
            "Create evidence from code",
            self.codes_tab,
        )

        layout.addWidget(
            self.codes_list,
            1,
        )

        layout.addWidget(
            self.detect_codes_button
        )

        layout.addWidget(
            self.copy_code_button
        )

        layout.addWidget(
            self.create_code_evidence_button
        )

        self.analysis_tabs.addTab(
            self.codes_tab,
            "Codes",
        )

    def _create_faces_tab(
        self,
    ) -> None:
        """
        Create face detection tab.
        """

        self.faces_tab = QWidget()

        layout = QVBoxLayout(
            self.faces_tab
        )

        self.faces_list = QListWidget(
            self.faces_tab
        )

        self.faces_list.setViewMode(
            QListWidget.ViewMode.IconMode
        )

        self.faces_list.setIconSize(
            QSize(
                72,
                72,
            )
        )

        self.faces_list.setGridSize(
            QSize(
                96,
                112,
            )
        )

        self.detect_faces_button = QPushButton(
            "Detect faces",
            self.faces_tab,
        )

        self.find_face_matches_button = QPushButton(
            "Find visually similar faces",
            self.faces_tab,
        )

        layout.addWidget(
            self.faces_list,
            1,
        )

        layout.addWidget(
            self.detect_faces_button
        )

        layout.addWidget(
            self.find_face_matches_button
        )

        self.analysis_tabs.addTab(
            self.faces_tab,
            "Faces",
        )

    def _create_objects_tab(
        self,
    ) -> None:
        """
        Create object detection tab.
        """

        self.objects_tab = QWidget()

        layout = QVBoxLayout(
            self.objects_tab
        )

        self.objects_list = QListWidget(
            self.objects_tab
        )

        self.detect_objects_button = QPushButton(
            "Detect objects",
            self.objects_tab,
        )

        self.create_object_evidence_button = QPushButton(
            "Create evidence from selection",
            self.objects_tab,
        )

        layout.addWidget(
            self.objects_list,
            1,
        )

        layout.addWidget(
            self.detect_objects_button
        )

        layout.addWidget(
            self.create_object_evidence_button
        )

        self.analysis_tabs.addTab(
            self.objects_tab,
            "Objects",
        )

    def _create_hashes_tab(
        self,
    ) -> None:
        """
        Create file and perceptual hash tab.
        """

        self.hashes_tab = QWidget()

        layout = QVBoxLayout(
            self.hashes_tab
        )

        self.hashes_text = QPlainTextEdit(
            self.hashes_tab
        )

        self.hashes_text.setReadOnly(
            True
        )

        self.hashes_text.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )

        self.hashes_text.setPlaceholderText(
            (
                "SHA-256, pHash and other visual "
                "fingerprints will appear here."
            )
        )

        self.calculate_hashes_button = QPushButton(
            "Calculate image hashes",
            self.hashes_tab,
        )

        self.find_similar_button = QPushButton(
            "Find similar images",
            self.hashes_tab,
        )

        self.compare_button = QPushButton(
            "Compare with another image",
            self.hashes_tab,
        )

        layout.addWidget(
            self.hashes_text,
            1,
        )

        layout.addWidget(
            self.calculate_hashes_button
        )

        layout.addWidget(
            self.find_similar_button
        )

        layout.addWidget(
            self.compare_button
        )

        self.analysis_tabs.addTab(
            self.hashes_tab,
            "Similarity",
        )

    def _create_integrity_tab(
        self,
    ) -> None:
        """
        Create integrity indicators tab.
        """

        self.integrity_tab = QWidget()

        layout = QVBoxLayout(
            self.integrity_tab
        )

        warning_label = QLabel(
            (
                "These checks show technical indicators only. "
                "They do not prove that an image is authentic "
                "or manipulated."
            ),
            self.integrity_tab,
        )

        warning_label.setWordWrap(
            True
        )

        warning_label.setObjectName(
            "PhotoIntegrityWarning"
        )

        self.integrity_text = QPlainTextEdit(
            self.integrity_tab
        )

        self.integrity_text.setReadOnly(
            True
        )

        self.integrity_text.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )

        self.integrity_text.setPlaceholderText(
            "Integrity indicators will appear here."
        )

        self.integrity_button = QPushButton(
            "Analyze integrity indicators",
            self.integrity_tab,
        )

        layout.addWidget(
            warning_label
        )

        layout.addWidget(
            self.integrity_text,
            1,
        )

        layout.addWidget(
            self.integrity_button
        )

        self.analysis_tabs.addTab(
            self.integrity_tab,
            "Integrity",
        )

    def _create_ai_tab(
        self,
    ) -> None:
        """
        Create image AI assistant tab.
        """

        self.ai_tab = QWidget()

        layout = QVBoxLayout(
            self.ai_tab
        )

        self.ai_summary_text = QPlainTextEdit(
            self.ai_tab
        )

        self.ai_summary_text.setReadOnly(
            True
        )

        self.ai_summary_text.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )

        self.ai_summary_text.setPlaceholderText(
            (
                "AI observations, uncertainties and "
                "recommended checks will appear here."
            )
        )

        self.generate_ai_summary_button = QPushButton(
            "Generate image summary",
            self.ai_tab,
        )

        self.ai_question_input = QPlainTextEdit(
            self.ai_tab
        )

        self.ai_question_input.setPlaceholderText(
            "Ask a question about the selected image..."
        )

        self.ai_question_input.setMaximumHeight(
            100
        )

        self.ask_ai_button = QPushButton(
            "Ask AI",
            self.ai_tab,
        )

        layout.addWidget(
            self.ai_summary_text,
            1,
        )

        layout.addWidget(
            self.generate_ai_summary_button
        )

        layout.addWidget(
            self.ai_question_input
        )

        layout.addWidget(
            self.ask_ai_button
        )

        self.analysis_tabs.addTab(
            self.ai_tab,
            "AI",
        )

    def _create_actions_tab(
        self,
    ) -> None:
        """
        Create investigation actions tab.
        """

        self.actions_tab = QWidget()

        layout = QVBoxLayout(
            self.actions_tab
        )

        self.add_timeline_button = QPushButton(
            "Add image to timeline",
            self.actions_tab,
        )

        self.reveal_folder_button = QPushButton(
            "Show in folder",
            self.actions_tab,
        )

        self.export_button = QPushButton(
            "Export image and analysis",
            self.actions_tab,
        )

        self.delete_button = QPushButton(
            "Delete from investigation",
            self.actions_tab,
        )

        self.delete_button.setProperty(
            "variant",
            "danger",
        )

        layout.addWidget(
            self.add_timeline_button
        )

        layout.addWidget(
            self.reveal_folder_button
        )

        layout.addWidget(
            self.export_button
        )

        layout.addStretch(
            1
        )

        layout.addWidget(
            self.delete_button
        )

        self.analysis_tabs.addTab(
            self.actions_tab,
            "Actions",
        )

    # ==========================================================
    # Status bar
    # ==========================================================

    def _create_status_bar(
        self,
    ) -> None:
        """
        Create compact workspace status bar.
        """

        self.status_bar = QFrame(
            self
        )

        self.status_bar.setObjectName(
            "PhotoWorkspaceStatusBar"
        )

        layout = QHBoxLayout(
            self.status_bar
        )

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.status_label = QLabel(
            "Ready",
            self.status_bar,
        )

        self.processing_label = QLabel(
            "",
            self.status_bar,
        )

        layout.addWidget(
            self.status_label,
            1,
        )

        layout.addWidget(
            self.processing_label
        )

        self.main_layout.addWidget(
            self.status_bar
        )

    # ==========================================================
    # Connections
    # ==========================================================

    def _create_connections(
        self,
    ) -> None:
        """
        Connect visible controls.
        """

        self.import_button.clicked.connect(
            self.import_images_requested.emit
        )

        self.search_input.textChanged.connect(
            self._on_filter_changed
        )

        self.type_filter.currentIndexChanged.connect(
            self._apply_filter
        )

        self.status_filter.currentIndexChanged.connect(
            self._apply_filter
        )

        self.sort_combo.currentIndexChanged.connect(
            self._apply_filter
        )

        self.photo_list.currentRowChanged.connect(
            self._on_image_row_changed
        )

        # Viewer controls

        self.zoom_out_button.clicked.connect(
            self.image_viewer.zoom_out
        )

        self.zoom_in_button.clicked.connect(
            self.image_viewer.zoom_in
        )

        self.fit_button.clicked.connect(
            self.image_viewer.fit_to_window
        )

        self.actual_size_button.clicked.connect(
            self.image_viewer.show_actual_size
        )

        self.rotate_left_button.clicked.connect(
            self.image_viewer.rotate_left
        )

        self.rotate_right_button.clicked.connect(
            self.image_viewer.rotate_right
        )

        self.reset_view_button.clicked.connect(
            self.image_viewer.reset_view
        )

        self.zoom_slider.valueChanged.connect(
            self._set_viewer_zoom
        )

        self.image_viewer.zoom_changed.connect(
            self._on_viewer_zoom_changed
        )

        self.image_viewer.load_failed.connect(
            self._on_image_load_failed
        )

        self.open_original_button.clicked.connect(
            self._emit_open_original
        )

        # Analysis actions

        self.analyze_image_button.clicked.connect(
            self._emit_analyze_image
        )

        self.reprocess_image_button.clicked.connect(
            self._emit_reprocess_image
        )

        self.extract_metadata_button.clicked.connect(
            self._emit_extract_metadata
        )

        self.run_ocr_button.clicked.connect(
            self._emit_run_ocr
        )

        self.detect_codes_button.clicked.connect(
            self._emit_detect_codes
        )

        self.detect_faces_button.clicked.connect(
            self._emit_detect_faces
        )

        self.find_face_matches_button.clicked.connect(
            self._emit_find_face_matches
        )

        self.detect_objects_button.clicked.connect(
            self._emit_detect_objects
        )

        self.calculate_hashes_button.clicked.connect(
            self._emit_calculate_hashes
        )

        self.find_similar_button.clicked.connect(
            self._emit_find_similar
        )

        self.compare_button.clicked.connect(
            self._emit_compare
        )

        self.integrity_button.clicked.connect(
            self._emit_integrity_analysis
        )

        self.generate_ai_summary_button.clicked.connect(
            self._emit_generate_ai_summary
        )

        self.ask_ai_button.clicked.connect(
            self._emit_ask_ai
        )

        self.add_timeline_button.clicked.connect(
            self._emit_add_to_timeline
        )

        self.create_location_button.clicked.connect(
            self._emit_create_location
        )

        self.reveal_folder_button.clicked.connect(
            self._emit_reveal_in_folder
        )

        self.export_button.clicked.connect(
            self._emit_export_image
        )

        self.delete_button.clicked.connect(
            self._emit_delete_image
        )

        self.copy_ocr_button.clicked.connect(
            self._copy_ocr_text
        )

        self.select_all_button.clicked.connect(
            self.photo_list.selectAll
        )

        self.clear_selection_button.clicked.connect(
            self.photo_list.clearSelection
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def set_images(
        self,
        images: list[dict[str, Any]],
    ) -> None:
        """
        Display image evidence.
        """

        self.images = [
            item
            for item in images
            if (
                isinstance(
                    item,
                    dict,
                )
                and str(
                    item.get(
                        "type"
                    )
                    or ""
                ).lower()
                == "image"
            )
        ]

        self._selected_image = None

        self._apply_filter()

    def set_evidence(
        self,
        evidence: list[dict[str, Any]],
    ) -> None:
        """
        Compatibility API accepting complete evidence list.
        """

        self.set_images(
            evidence
        )

    def clear(
        self,
    ) -> None:
        """
        Clear complete workspace state.
        """

        self._comparison_mode = False
        self._comparison_source_id = None

        self.images = []
        self.filtered_images = []
        self._selected_image = None

        self.photo_list.clear()

        self.image_viewer.clear_image()

        self._clear_analysis()

        self._update_state()

    def selected_image(
        self,
    ) -> dict[str, Any] | None:
        """
        Return selected image evidence.
        """

        if self._selected_image is None:

            return None

        return dict(
            self._selected_image
        )

    def select_image(
        self,
        evidence_id: str,
    ) -> bool:
        """
        Select image Evidence by ID.

        Returns True when the requested image exists
        in the current image collection.
        """

        target_id = str(
            evidence_id
            or ""
        ).strip()

        if not target_id:

            return False

        # ------------------------------------------------------
        # First try the currently visible / filtered collection.
        # ------------------------------------------------------

        for row, image in enumerate(
            self.filtered_images
        ):

            image_id = str(
                image.get(
                    "id"
                )
                or ""
            ).strip()

            if image_id != target_id:

                continue

            self.photo_list.setCurrentRow(
                row
            )

            self.photo_list.scrollToItem(
                self.photo_list.item(
                    row
                )
            )

            return True

        # ------------------------------------------------------
        # The image may currently be hidden by a filter/search.
        # Reset filtering and try again.
        # ------------------------------------------------------

        image_exists = any(
            str(
                image.get(
                    "id"
                )
                or ""
            ).strip()
            == target_id
            for image in self.images
        )

        if not image_exists:

            return False

        self.search_input.clear()

        if self.filter_combo.count() > 0:

            self.filter_combo.setCurrentIndex(
                0
            )

        self._apply_filter()

        for row, image in enumerate(
            self.filtered_images
        ):

            image_id = str(
                image.get(
                    "id"
                )
                or ""
            ).strip()

            if image_id != target_id:

                continue

            self.photo_list.setCurrentRow(
                row
            )

            self.photo_list.scrollToItem(
                self.photo_list.item(
                    row
                )
            )

            return True

        return False

    def set_processing(
        self,
        processing: bool,
        message: str = "",
    ) -> None:
        """
        Update processing state.
        """

        enabled = not processing

        self.import_button.setEnabled(
            enabled
        )

        self.analyze_image_button.setEnabled(
            enabled
        )

        self.reprocess_image_button.setEnabled(
            enabled
        )

        self.extract_metadata_button.setEnabled(
            enabled
        )

        self.run_ocr_button.setEnabled(
            enabled
        )

        self.detect_codes_button.setEnabled(
            enabled
        )

        self.detect_faces_button.setEnabled(
            enabled
        )

        self.detect_objects_button.setEnabled(
            enabled
        )

        self.calculate_hashes_button.setEnabled(
            enabled
        )

        self.integrity_button.setEnabled(
            enabled
        )

        if processing:

            self.processing_label.setText(
                message
                or "Processing..."
            )

        else:

            self.processing_label.clear()

    # ==========================================================
    # Filtering and list
    # ==========================================================

    def _on_filter_changed(
        self,
        text: str,
    ) -> None:

        self._search_text = (
            text
            .strip()
            .casefold()
        )

        self._apply_filter()

    def _apply_filter(
        self,
    ) -> None:
        """
        Apply search, type, status and sorting.
        """

        format_filter = (
            self.type_filter.currentData()
        )

        status_filter = (
            self.status_filter.currentData()
        )

        visible: list[
            dict[str, Any]
        ] = []

        for image in self.images:

            if (
                self._search_text
                and not self._matches_search(
                    image
                )
            ):

                continue

            if (
                format_filter != "all"
                and not self._matches_format(
                    image,
                    str(
                        format_filter
                    ),
                )
            ):

                continue

            if (
                status_filter != "all"
                and self._processing_status(
                    image
                )
                != status_filter
            ):

                continue

            visible.append(
                image
            )

        self.filtered_images = (
            self._sort_images(
                visible
            )
        )

        self._populate_photo_list()
        self._update_state()

    def _matches_search(
        self,
        image: dict[str, Any],
    ) -> bool:

        metadata = self._metadata_dict(
            image
        )

        searchable = " ".join(
            str(
                value
            )
            for value in (
                image.get("title"),
                image.get("file_path"),
                image.get("mime_type"),
                image.get("sha256"),
                image.get("description"),
                metadata.get("original_name"),
                metadata.get("camera"),
                metadata.get("device_model"),
                metadata.get("ocr_text"),
            )
            if value is not None
        ).casefold()

        return (
            self._search_text
            in searchable
        )

    def _matches_format(
        self,
        image: dict[str, Any],
        format_filter: str,
    ) -> bool:

        path = str(
            image.get(
                "file_path"
            )
            or ""
        )

        suffix = Path(
            path
        ).suffix.lower()

        format_extensions = {
            "jpeg": {
                ".jpg",
                ".jpeg",
            },
            "png": {
                ".png",
            },
            "webp": {
                ".webp",
            },
            "tiff": {
                ".tif",
                ".tiff",
            },
            "gif": {
                ".gif",
            },
        }

        expected = format_extensions.get(
            format_filter
        )

        if expected is None:

            known = set().union(
                *format_extensions.values()
            )

            return suffix not in known

        return suffix in expected

    def _sort_images(
        self,
        images: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        sort_mode = (
            self.sort_combo.currentData()
        )

        if sort_mode == "created_desc":

            return sorted(
                images,
                key=lambda item: str(
                    item.get(
                        "created_at"
                    )
                    or ""
                ),
                reverse=True,
            )

        if sort_mode == "created_asc":

            return sorted(
                images,
                key=lambda item: str(
                    item.get(
                        "created_at"
                    )
                    or ""
                ),
            )

        if sort_mode == "size_desc":

            return sorted(
                images,
                key=self._image_size_bytes,
                reverse=True,
            )

        if sort_mode == "size_asc":

            return sorted(
                images,
                key=self._image_size_bytes,
            )

        if sort_mode == "capture_date":

            return sorted(
                images,
                key=lambda item: str(
                    self._metadata_dict(
                        item
                    ).get(
                        "capture_date"
                    )
                    or ""
                ),
                reverse=True,
            )

        return sorted(
            images,
            key=lambda item: str(
                item.get(
                    "title"
                )
                or ""
            ).casefold(),
        )

    def _populate_photo_list(
        self,
    ) -> None:
        """
        Populate thumbnail library.
        """

        self.photo_list.clear()

        for image in self.filtered_images:

            title = str(
                image.get(
                    "title"
                )
                or "Image"
            )

            item = QListWidgetItem(
                title
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                image,
            )

            item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter
            )

            item.setToolTip(
                self._build_image_tooltip(
                    image
                )
            )

            icon = self._build_thumbnail_icon(
                image
            )

            if not icon.isNull():

                item.setIcon(
                    icon
                )

            self.photo_list.addItem(
                item
            )

        if self.filtered_images:

            self.photo_list.setCurrentRow(
                0
            )

        else:

            self._selected_image = None
            self.image_viewer.clear_image()
            self._clear_analysis()

    # ==========================================================
    # Selection
    # ==========================================================

    def _on_image_row_changed(
        self,
        row: int,
    ) -> None:

        if (
            row < 0
            or row >= len(
                self.filtered_images
            )
        ):

            self._selected_image = None

            self.image_viewer.clear_image()

            self._clear_analysis()

            self._update_state()

            return

        image = self.filtered_images[
        row
    ]

        self._selected_image = image

        self._display_selected_image(
            image
        )

        self.image_selected.emit(
            dict(
                image
            )
        )

        if not self._comparison_mode:

            return

        source_id = str(
            self._comparison_source_id
            or ""
        ).strip()

        target_id = self._selected_image_id()

        if not source_id:

            self._cancel_comparison_mode()

            return

        if not target_id:

            return

        if target_id == source_id:

            self.status_label.setText(
                (
                    "Comparison mode: select a "
                    "different image."
                )
            )

            return

        self._comparison_mode = False

        self._comparison_source_id = None

        self.compare_button.setText(
            "Compare with another image"
        )

        self.status_label.setText(
            "Comparing images..."
        )

        self.compare_images_requested.emit(
            source_id,
            target_id,
        )

    def _display_selected_image(
        self,
        image: dict[str, Any],
    ) -> None:

        title = str(
            image.get(
                "title"
            )
            or "Image"
        )

        original_path = str(
            image.get(
                "file_path"
            )
            or ""
        )

        viewer_path = self._preview_path(
            image
        )

        if viewer_path:

            loaded = self.image_viewer.load_image(
                viewer_path
            )

            self.viewer_empty_label.setVisible(
                not loaded
            )

            if loaded:

                self.status_label.setText(
                    (
                        "Preview displayed"
                        if (
                            original_path
                            and viewer_path
                            != original_path
                        )
                        else "Image displayed"
                    )
                )
            else:

                self.image_viewer.clear_image()

                self.viewer_empty_label.setText(
                    "No compatible image preview is available."
                )

                self.viewer_empty_label.show()

                self.viewer_empty_label.setVisible(
                    not loaded
                )

        else:

            self.image_viewer.clear_image()

            self.viewer_empty_label.show()

        self._populate_analysis(
            image
        )

        self._update_state()

    # ==========================================================
    # Analysis display
    # ==========================================================

    def _populate_analysis(
        self,
        image: dict[str, Any],
    ) -> None:

        metadata = self._metadata_dict(
            image
        )

        overview_lines = [
            f"Title: {image.get('title') or 'Unavailable'}",
            f"Evidence ID: {image.get('id') or 'Unavailable'}",
            f"MIME type: {image.get('mime_type') or 'Unavailable'}",
            f"File path: {image.get('file_path') or 'Unavailable'}",
            f"SHA-256: {image.get('sha256') or 'Unavailable'}",
            (
                "Size: "
                f"{self._format_size(self._image_size_bytes(image))}"
            ),
            (
                "Dimensions: "
                f"{self._dimensions_text(metadata) or 'Unavailable'}"
            ),
            (
                "Processing status: "
                f"{self._processing_status(image)}"
            ),
        ]

        self.overview_text.setPlainText(
            "\n".join(
                overview_lines
            )
        )

        self.metadata_text.setPlainText(
            self._format_metadata_text(
                metadata
            )
        )

        self.ocr_text.setPlainText(
            str(
                metadata.get(
                    "ocr_text"
                )
                or ""
            )
        )

        self.hashes_text.setPlainText(
            self._format_hashes_text(
                image,
                metadata,
            )
        )

        self.integrity_text.setPlainText(
            self._format_generic_result(
                metadata.get(
                    "integrity"
                )
            )
        )

        self.ai_summary_text.setPlainText(
            str(
                metadata.get(
                    "ai_summary"
                )
                or ""
            )
        )

        self._populate_generic_list(
            self.codes_list,
            metadata.get(
                "codes"
            ),
        )

        self._populate_generic_list(
            self.objects_list,
            metadata.get(
                "objects"
            ),
        )

# ==========================================================
# Faces
# ==========================================================

        faces: list[dict[str, Any]] = []

        image_analysis = metadata.get(
            "image_analysis"
        )

        if isinstance(
            image_analysis,
            dict,
        ):

            faces_result = image_analysis.get(
                "faces"
            )

            if isinstance(
                faces_result,
                dict,
            ):

                faces_data = faces_result.get(
                    "data"
                )

                if isinstance(
                    faces_data,
                    dict,
                ):

                    detected_faces = faces_data.get(
                        "faces"
                    )

                    if isinstance(
                        detected_faces,
                        list,
                    ):

                        faces = [
                            face
                            for face
                            in detected_faces
                            if isinstance(
                                face,
                                dict,
                            )
                        ]

        # Backward compatibility with older metadata layout.
        if not faces:

            legacy_faces = metadata.get(
                "faces"
            )

            if isinstance(
                legacy_faces,
                list,
            ):

                faces = [
                    face
                    for face
                    in legacy_faces
                    if isinstance(
                        face,
                        dict,
                    )
                ]

        self._populate_faces(
            faces
        )

    def _clear_analysis(
        self,
    ) -> None:

        self.selected_title_label.setText(
            "No image selected"
        )

        self.selected_dimensions_label.clear()

        self.overview_text.clear()
        self.metadata_text.clear()
        self.ocr_text.clear()
        self.hashes_text.clear()
        self.integrity_text.clear()
        self.ai_summary_text.clear()

        self.codes_list.clear()
        self.faces_list.clear()
        self.objects_list.clear()

    # ==========================================================
    # Signal emitters
    # ==========================================================

    def _selected_image_id(
        self,
    ) -> str:

        if self._selected_image is None:

            return ""

        return str(
            self._selected_image.get(
                "id"
            )
            or ""
        )

    def _selected_image_path(
        self,
    ) -> str:

        if self._selected_image is None:

            return ""

        return str(
            self._selected_image.get(
                "file_path"
            )
            or ""
        )

    def _emit_open_original(
        self,
    ) -> None:

        path = self._selected_image_path()

        if path:

            self.open_original_requested.emit(
                path
            )

    def _emit_analyze_image(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.analyze_image_requested.emit(
                image_id
            )

    def _emit_reprocess_image(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.reprocess_image_requested.emit(
                image_id
            )

    def _emit_extract_metadata(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.extract_metadata_requested.emit(
                image_id
            )

    def _emit_run_ocr(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.run_ocr_requested.emit(
                image_id
            )

    def _emit_detect_codes(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.detect_codes_requested.emit(
                image_id
            )

    def _emit_detect_faces(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.detect_faces_requested.emit(
                image_id
            )

    def _emit_find_face_matches(
        self,
    ) -> None:
        """
        Request similarity search for the
        currently selected detected face.
        """

        image_id = self._selected_image_id()

        if not image_id:

            return

        current_item = (
            self.faces_list
            .currentItem()
        )

        if current_item is None:

            return

        face_data = current_item.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(
            face_data,
            dict,
        ):

            return

        face_id = str(
            face_data.get(
                "id"
            )
            or ""
        ).strip()

        if not face_id:

            return

        self.find_face_matches_requested.emit(
            image_id,
            face_id,
        )

    def _emit_detect_objects(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.detect_objects_requested.emit(
                image_id
            )

    def _emit_calculate_hashes(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.calculate_hashes_requested.emit(
                image_id
            )

    def _emit_find_similar(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.find_similar_requested.emit(
                image_id
            )

    def _emit_compare(
        self,
    ) -> None:
        """
        Start or cancel image comparison mode.
        """

        if self._comparison_mode:

            self._cancel_comparison_mode()

            return

        image_id = self._selected_image_id()

        if not image_id:

            return

        if len(
            self.images
        ) < 2:

            self.status_label.setText(
                (
                    "At least two images are required "
                    "for comparison."
                )
            )

            return

        self._comparison_source_id = (
            image_id
        )

        self._comparison_mode = True

        self.compare_button.setText(
            "Cancel comparison"
        )

        self.status_label.setText(
            (
                "Comparison mode: select the "
                "second image."
            )
        )


    def _cancel_comparison_mode(
        self,
    ) -> None:
        """
        Leave image comparison selection mode.
        """

        self._comparison_mode = False

        self._comparison_source_id = None

        self.compare_button.setText(
            "Compare with another image"
        )

        if self._selected_image is not None:

            self.status_label.setText(
                "Image selected"
            )

        elif self.images:

            self.status_label.setText(
                "No image selected"
            )

        else:

            self.status_label.setText(
                "No images"
            )

    def _cancel_comparison_mode(
        self,
    ) -> None:
        """
        Leave image comparison selection mode.
        """

        self._comparison_mode = False

        self._comparison_source_id = None

        self.compare_button.setText(
            "Compare with another image"
        )

        if self._selected_image is not None:

            self.status_label.setText(
                "Image selected"
            )

        elif self.images:

            self.status_label.setText(
                "No image selected"
            )

        else:

            self.status_label.setText(
                "No images"
            )

    def _emit_integrity_analysis(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.analyze_integrity_requested.emit(
                image_id
            )

    def _emit_generate_ai_summary(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.generate_ai_summary_requested.emit(
                image_id
            )

    def _emit_ask_ai(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        question = (
            self.ai_question_input
            .toPlainText()
            .strip()
        )

        if (
            image_id
            and question
        ):

            self.ask_ai_requested.emit(
                image_id,
                question,
            )

    def _emit_add_to_timeline(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.add_to_timeline_requested.emit(
                image_id
            )

    def _emit_create_location(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.create_location_requested.emit(
                image_id
            )

    def _emit_reveal_in_folder(
        self,
    ) -> None:

        path = self._selected_image_path()

        if path:

            self.reveal_in_folder_requested.emit(
                path
            )

    def _emit_export_image(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.export_image_requested.emit(
                image_id
            )

    def _emit_delete_image(
        self,
    ) -> None:

        image_id = self._selected_image_id()

        if image_id:

            self.delete_image_requested.emit(
                image_id
            )

    # ==========================================================
    # Viewer helpers
    # ==========================================================

    def _set_viewer_zoom(
        self,
        value: int,
    ) -> None:

        if self.image_viewer.has_image():

            self.image_viewer.set_zoom_percent(
                value
            )

    def _on_viewer_zoom_changed(
        self,
        percent: int,
    ) -> None:

        self.zoom_slider.blockSignals(
            True
        )

        self.zoom_slider.setValue(
            max(
                self.zoom_slider.minimum(),
                min(
                    self.zoom_slider.maximum(),
                    percent,
                ),
            )
        )

        self.zoom_slider.blockSignals(
            False
        )

        self.zoom_percent_label.setText(
            f"{percent}%"
        )

    def _on_image_load_failed(
        self,
        message: str,
    ) -> None:

        self.status_label.setText(
            message
        )

        self.viewer_empty_label.setText(
            message
        )

        self.viewer_empty_label.show()

    # ==========================================================
    # Small UI helpers
    # ==========================================================

    def _copy_ocr_text(
        self,
    ) -> None:

        self.ocr_text.selectAll()
        self.ocr_text.copy()

        cursor = self.ocr_text.textCursor()

        cursor.clearSelection()

        self.ocr_text.setTextCursor(
            cursor
        )

    def _update_state(
        self,
    ) -> None:

        count = len(
            self.filtered_images
        )

        self.photo_count_label.setText(
            (
                f"{count} image"
                if count == 1
                else f"{count} images"
            )
        )

        has_selection = (
            self._selected_image is not None
        )

        self.analysis_tabs.setEnabled(
            has_selection
        )

        self.viewer_controls.setEnabled(
            has_selection
        )

        self.overlay_controls.setEnabled(
            has_selection
        )

        if has_selection:

            self.status_label.setText(
                "Image selected"
            )

        elif self.images:

            self.status_label.setText(
                "No image selected"
            )

        else:

            self.status_label.setText(
                "No images in this investigation"
            )

    # ==========================================================
    # Data helpers
    # ==========================================================

    @staticmethod
    def _metadata_dict(
        image: dict[str, Any],
    ) -> dict[str, Any]:

        metadata = image.get(
            "metadata"
        )

        if isinstance(
            metadata,
            dict,
        ):

            return metadata

        metadata_json = image.get(
            "metadata_json"
        )

        if isinstance(
            metadata_json,
            dict,
        ):

            return metadata_json

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

                    return decoded

            except json.JSONDecodeError:

                return {}

        return {}


    @classmethod
    def _processing_metadata_dict(
            cls,
            image: dict[str, Any],
        ) -> dict[str, Any]:
            """
            Return normalized processing metadata.
            """

            metadata = cls._metadata_dict(
                image
            )

            processing_metadata = metadata.get(
                "processing_metadata"
            )

            if isinstance(
                processing_metadata,
                dict,
            ):

                return processing_metadata

            processing_result = metadata.get(
                "processing"
            )

            if isinstance(
                processing_result,
                dict,
            ):

                nested_metadata = processing_result.get(
                    "metadata"
                )

                if isinstance(
                    nested_metadata,
                    dict,
                ):

                    return nested_metadata

            return {}

    @classmethod
    def _preview_path(
        cls,
        image: dict[str, Any],
    ) -> str:
        """
        Return the best available path for the central viewer.

        Priority:

        1. generated preview
        2. generated thumbnail
        3. original file
        """

        metadata = cls._metadata_dict(
            image
        )

        processing_metadata = (
            cls._processing_metadata_dict(
                image
            )
        )

        preview_data = (
            processing_metadata.get(
                "preview"
            )
        )

        if isinstance(
            preview_data,
            dict,
        ):

            preview_path = str(
                preview_data.get(
                    "preview_path"
                )
                or preview_data.get(
                    "path"
                )
                or ""
            )

            if preview_path:

                return preview_path

        preview_path = str(
            processing_metadata.get(
                "preview_path"
            )
            or metadata.get(
                "preview_path"
            )
            or image.get(
                "preview_path"
            )
            or ""
        )

        if preview_path:

            return preview_path

        thumbnail_data = (
            processing_metadata.get(
                "thumbnail"
            )
        )

        if isinstance(
            thumbnail_data,
            dict,
        ):

            thumbnail_path = str(
                thumbnail_data.get(
                    "thumbnail_path"
                )
                or thumbnail_data.get(
                    "path"
                )
                or ""
            )

            if thumbnail_path:

                return thumbnail_path

        thumbnail_path = str(
            processing_metadata.get(
                "thumbnail_path"
            )
            or metadata.get(
                "thumbnail_path"
            )
            or image.get(
                "thumbnail_path"
            )
            or ""
        )

        if thumbnail_path:

            return thumbnail_path

        return str(
            image.get(
                "file_path"
            )
            or ""
        )

    @classmethod
    def _image_size_bytes(
        cls,
        image: dict[str, Any],
    ) -> int:

        metadata = cls._metadata_dict(
            image
        )

        try:

            return int(
                metadata.get(
                    "size_bytes"
                )
                or image.get(
                    "size_bytes"
                )
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0


    @staticmethod
    def _format_size(
        size_bytes: int,
    ) -> str:
        """
        Convert file size in bytes to a readable value.
        """

        try:

            size = float(
                max(
                    0,
                    int(
                        size_bytes
                    ),
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            size = 0.0

        units = (
            "B",
            "KB",
            "MB",
            "GB",
            "TB",
        )

        unit_index = 0

        while (
            size >= 1024.0
            and unit_index
            < len(
                units
            ) - 1
        ):

            size /= 1024.0

            unit_index += 1

        if unit_index == 0:

            return (
                f"{int(size)} "
                f"{units[unit_index]}"
            )

        return (
            f"{size:.1f} "
            f"{units[unit_index]}"
        )

    @classmethod
    def _processing_status(
        cls,
        image: dict[str, Any],
    ) -> str:

        metadata = cls._metadata_dict(
            image
        )

        return str(
            metadata.get(
                "processing_status"
            )
            or image.get(
                "processing_status"
            )
            or "pending"
        ).lower()

    @classmethod
    def _dimensions_text(
        cls,
        metadata: dict[str, Any],
    ) -> str:
        """
        Return image dimensions from normalized metadata.
        """

        processing_metadata = metadata.get(
            "processing_metadata"
        )

        if not isinstance(
            processing_metadata,
            dict,
        ):

            processing_metadata = {}

        width = (
            processing_metadata.get(
                "width"
            )
            or metadata.get(
                "width"
            )
        )

        height = (
            processing_metadata.get(
                "height"
            )
            or metadata.get(
                "height"
            )
        )

        if (
            width
            and height
        ):

            return (
                f"{width} × {height}"
            )

        return ""

    @staticmethod
    def _format_generic_result(
        value: Any,
    ) -> str:

        if value is None:

            return ""

        if isinstance(
            value,
            str,
        ):

            return value

        try:

            return json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )

        except TypeError:

            return str(
                value
            )

    @classmethod
    def _format_metadata_text(
        cls,
        metadata: dict[str, Any],
    ) -> str:
        """
        Format image and EXIF metadata into readable sections.

        Complete raw metadata is preserved at the bottom.
        """

        if not metadata:

            return (
                "No metadata is available "
                "for the selected image."
            )

        processing_metadata = metadata.get(
            "processing_metadata"
        )

        if not isinstance(
            processing_metadata,
            dict,
        ):

            processing_metadata = metadata.get(
                "processing"
            )

            if isinstance(
                processing_metadata,
                dict,
            ):

                nested_metadata = (
                    processing_metadata.get(
                        "metadata"
                    )
                )

                if isinstance(
                    nested_metadata,
                    dict,
                ):

                    processing_metadata = (
                        nested_metadata
                    )

            if not isinstance(
                processing_metadata,
                dict,
            ):

                processing_metadata = {}

        exif_result = processing_metadata.get(
            "exif"
        )

        if not isinstance(
            exif_result,
            dict,
        ):

            exif_result = metadata.get(
                "exif"
            )

        if not isinstance(
            exif_result,
            dict,
        ):

            exif_result = {}

        normalized_exif = exif_result.get(
            "normalized"
        )

        if not isinstance(
            normalized_exif,
            dict,
        ):

            normalized_exif = {}

        raw_exif = exif_result.get(
            "raw"
        )

        if not isinstance(
            raw_exif,
            dict,
        ):

            raw_exif = {}

        camera = normalized_exif.get(
            "camera"
        )

        if not isinstance(
            camera,
            dict,
        ):

            camera = {}

        capture = normalized_exif.get(
            "capture"
        )

        if not isinstance(
            capture,
            dict,
        ):

            capture = {}

        timestamps = normalized_exif.get(
            "timestamps"
        )

        if not isinstance(
            timestamps,
            dict,
        ):

            timestamps = {}

        gps = normalized_exif.get(
            "gps"
        )

        if not isinstance(
            gps,
            dict,
        ):

            gps = {}

        authorship = normalized_exif.get(
            "authorship"
        )

        if not isinstance(
            authorship,
            dict,
        ):

            authorship = {}

        thumbnail = processing_metadata.get(
            "thumbnail"
        )

        if not isinstance(
            thumbnail,
            dict,
        ):

            thumbnail = {}

        preview = processing_metadata.get(
            "preview"
        )

        if not isinstance(
            preview,
            dict,
        ):

            preview = {}

        sections: list[str] = []

        # ======================================================
        # File
        # ======================================================

        file_fields = [
            (
                "Filename",
                processing_metadata.get(
                    "filename"
                )
                or metadata.get(
                    "filename"
                ),
            ),
            (
                "Original path",
                processing_metadata.get(
                    "path"
                )
                or metadata.get(
                    "file_path"
                ),
            ),
            (
                "Extension",
                processing_metadata.get(
                    "extension"
                ),
            ),
            (
                "MIME type",
                processing_metadata.get(
                    "mime_type"
                )
                or metadata.get(
                    "mime_type"
                ),
            ),
            (
                "File size",
                cls._format_optional_size(
                    processing_metadata.get(
                        "size_bytes"
                    )
                    or metadata.get(
                        "size_bytes"
                    )
                ),
            ),
            (
                "SHA-256",
                processing_metadata.get(
                    "sha256"
                )
                or metadata.get(
                    "sha256"
                ),
            ),
            (
                "Processing status",
                processing_metadata.get(
                    "processing_status"
                )
                or metadata.get(
                    "processing_status"
                ),
            ),
        ]

        cls._append_metadata_section(
            sections,
            "FILE",
            file_fields,
        )

        # ======================================================
        # Image
        # ======================================================

        width = processing_metadata.get(
            "width"
        )

        height = processing_metadata.get(
            "height"
        )

        dimensions = None

        if (
            width is not None
            and height is not None
        ):

            dimensions = (
                f"{width} × {height}"
            )

        image_fields = [
            (
                "Dimensions",
                dimensions,
            ),
            (
                "Megapixels",
                processing_metadata.get(
                    "megapixels"
                ),
            ),
            (
                "Aspect ratio",
                processing_metadata.get(
                    "aspect_ratio"
                ),
            ),
            (
                "Orientation",
                processing_metadata.get(
                    "orientation"
                ),
            ),
            (
                "EXIF orientation",
                processing_metadata.get(
                    "exif_orientation_name"
                )
                or processing_metadata.get(
                    "exif_orientation"
                ),
            ),
            (
                "Image format",
                processing_metadata.get(
                    "image_format"
                ),
            ),
            (
                "Color mode",
                processing_metadata.get(
                    "color_mode"
                ),
            ),
            (
                "Color bands",
                processing_metadata.get(
                    "color_bands"
                ),
            ),
            (
                "Alpha channel",
                processing_metadata.get(
                    "has_alpha"
                ),
            ),
            (
                "Animated",
                processing_metadata.get(
                    "is_animated"
                ),
            ),
            (
                "Frame count",
                processing_metadata.get(
                    "frame_count"
                ),
            ),
            (
                "DPI",
                processing_metadata.get(
                    "dpi"
                ),
            ),
            (
                "ICC profile",
                processing_metadata.get(
                    "icc_profile_present"
                ),
            ),
        ]

        cls._append_metadata_section(
            sections,
            "IMAGE",
            image_fields,
        )

        # ======================================================
        # Camera
        # ======================================================

        camera_fields = [
            (
                "Manufacturer",
                camera.get(
                    "make"
                )
                or processing_metadata.get(
                    "camera_make"
                ),
            ),
            (
                "Model",
                camera.get(
                    "model"
                )
                or processing_metadata.get(
                    "camera_model"
                ),
            ),
            (
                "Lens",
                camera.get(
                    "lens_model"
                )
                or processing_metadata.get(
                    "lens_model"
                ),
            ),
        ]

        cls._append_metadata_section(
            sections,
            "CAMERA",
            camera_fields,
        )

        # ======================================================
        # Capture
        # ======================================================

        capture_fields = [
            (
                "ISO",
                capture.get(
                    "iso"
                )
                or processing_metadata.get(
                    "iso"
                ),
            ),
            (
                "Exposure time",
                capture.get(
                    "exposure_time"
                )
                or processing_metadata.get(
                    "exposure_time"
                ),
            ),
            (
                "Aperture",
                capture.get(
                    "aperture"
                )
                or processing_metadata.get(
                    "aperture"
                ),
            ),
            (
                "Focal length",
                capture.get(
                    "focal_length"
                )
                or processing_metadata.get(
                    "focal_length"
                ),
            ),
            (
                "Orientation",
                capture.get(
                    "orientation"
                )
                or processing_metadata.get(
                    "metadata_orientation"
                ),
            ),
        ]

        cls._append_metadata_section(
            sections,
            "CAPTURE",
            capture_fields,
        )

        # ======================================================
        # Dates
        # ======================================================

        dates_fields = [
            (
                "Date taken",
                timestamps.get(
                    "date_taken"
                )
                or processing_metadata.get(
                    "date_taken"
                ),
            ),
            (
                "Metadata modified",
                timestamps.get(
                    "modify_date"
                )
                or processing_metadata.get(
                    "metadata_modify_date"
                ),
            ),
            (
                "Imported",
                metadata.get(
                    "created_at"
                ),
            ),
            (
                "Updated",
                metadata.get(
                    "updated_at"
                ),
            ),
        ]

        cls._append_metadata_section(
            sections,
            "DATES",
            dates_fields,
        )

        # ======================================================
        # GPS
        # ======================================================

        latitude = (
            gps.get(
                "latitude"
            )
            or processing_metadata.get(
                "gps_latitude"
            )
        )

        longitude = (
            gps.get(
                "longitude"
            )
            or processing_metadata.get(
                "gps_longitude"
            )
        )

        altitude = (
            gps.get(
                "altitude"
            )
            or processing_metadata.get(
                "gps_altitude"
            )
        )

        gps_fields = [
            (
                "GPS available",
                gps.get(
                    "available"
                )
                if "available" in gps
                else processing_metadata.get(
                    "gps_available"
                ),
            ),
            (
                "Latitude",
                latitude,
            ),
            (
                "Longitude",
                longitude,
            ),
            (
                "Altitude",
                altitude,
            ),
        ]

        cls._append_metadata_section(
            sections,
            "GPS",
            gps_fields,
        )

        # ======================================================
        # Software and authorship
        # ======================================================

        software_fields = [
            (
                "Software",
                normalized_exif.get(
                    "software"
                )
                or processing_metadata.get(
                    "software"
                ),
            ),
            (
                "Editing software detected",
                normalized_exif.get(
                    "editing_software_detected"
                )
                if (
                    "editing_software_detected"
                    in normalized_exif
                )
                else processing_metadata.get(
                    "editing_software_detected"
                ),
            ),
            (
                "Artist",
                authorship.get(
                    "artist"
                )
                or processing_metadata.get(
                    "artist"
                ),
            ),
            (
                "Copyright",
                authorship.get(
                    "copyright"
                )
                or processing_metadata.get(
                    "copyright"
                ),
            ),
            (
                "Description",
                normalized_exif.get(
                    "description"
                )
                or processing_metadata.get(
                    "image_description"
                ),
            ),
            (
                "Keywords",
                normalized_exif.get(
                    "keywords"
                )
                or processing_metadata.get(
                    "keywords"
                ),
            ),
        ]

        cls._append_metadata_section(
            sections,
            "SOFTWARE AND AUTHORSHIP",
            software_fields,
        )

        # ======================================================
        # Derived files
        # ======================================================

        derived_fields = [
            (
                "Thumbnail path",
                thumbnail.get(
                    "thumbnail_path"
                )
                or processing_metadata.get(
                    "thumbnail_path"
                ),
            ),
            (
                "Thumbnail dimensions",
                cls._format_dimensions_pair(
                    thumbnail.get(
                        "thumbnail_width"
                    )
                    or processing_metadata.get(
                        "thumbnail_width"
                    ),
                    thumbnail.get(
                        "thumbnail_height"
                    )
                    or processing_metadata.get(
                        "thumbnail_height"
                    ),
                ),
            ),
            (
                "Preview path",
                preview.get(
                    "preview_path"
                )
                or processing_metadata.get(
                    "preview_path"
                ),
            ),
            (
                "Preview dimensions",
                cls._format_dimensions_pair(
                    preview.get(
                        "preview_width"
                    )
                    or processing_metadata.get(
                        "preview_width"
                    ),
                    preview.get(
                        "preview_height"
                    )
                    or processing_metadata.get(
                        "preview_height"
                    ),
                ),
            ),
            (
                "Preview lossless",
                preview.get(
                    "lossless"
                ),
            ),
            (
                "Preview resized",
                preview.get(
                    "resized"
                ),
            ),
        ]

        cls._append_metadata_section(
            sections,
            "DERIVED FILES",
            derived_fields,
        )

        # ======================================================
        # Warnings and errors
        # ======================================================

        warning_values: list[Any] = []

        processing_warnings = (
            processing_metadata.get(
                "warnings"
            )
        )

        if isinstance(
            processing_warnings,
            list,
        ):

            warning_values.extend(
                processing_warnings
            )

        exif_warnings = exif_result.get(
            "warnings"
        )

        if isinstance(
            exif_warnings,
            list,
        ):

            warning_values.extend(
                exif_warnings
            )

        exif_errors = exif_result.get(
            "errors"
        )

        error_fields = []

        if warning_values:

            error_fields.append(
                (
                    "Warnings",
                    warning_values,
                )
            )

        if isinstance(
            exif_errors,
            list,
        ) and exif_errors:

            error_fields.append(
                (
                    "Errors",
                    exif_errors,
                )
            )

        cls._append_metadata_section(
            sections,
            "WARNINGS AND ERRORS",
            error_fields,
        )

        # ======================================================
        # Raw ExifTool metadata
        # ======================================================

        if raw_exif:

            sections.append(
                cls._metadata_section_title(
                    "RAW EXIFTOOL METADATA"
                )
            )

            sections.append(
                json.dumps(
                    raw_exif,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )

        return "\n\n".join(
            section
            for section in sections
            if section.strip()
        )

    @classmethod
    def _append_metadata_section(
        cls,
        sections: list[str],
        title: str,
        fields: list[
            tuple[
                str,
                Any,
            ]
        ],
    ) -> None:
        """
        Add a metadata section when at least one value exists.
        """

        lines: list[str] = []

        for label, value in fields:

            if cls._metadata_value_is_empty(
                value
            ):

                continue

            formatted_value = (
                cls._format_metadata_value(
                    value
                )
            )

            lines.append(
                f"{label}\n{formatted_value}"
            )

        if not lines:

            return

        sections.append(
            cls._metadata_section_title(
                title
            )
        )

        sections.append(
            "\n\n".join(
                lines
            )
        )

    @staticmethod
    def _metadata_section_title(
        title: str,
    ) -> str:
        """
        Create a readable metadata section heading.
        """

        line = "═" * 42

        return (
            f"{line}\n"
            f"{title}\n"
            f"{line}"
        )

    @staticmethod
    def _metadata_value_is_empty(
        value: Any,
    ) -> bool:
        """
        Return whether a metadata value should be hidden.
        """

        if value is None:

            return True

        if isinstance(
            value,
            str,
        ):

            return not value.strip()

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
                dict,
            ),
        ):

            return len(
                value
            ) == 0

        return False

    @staticmethod
    def _format_metadata_value(
        value: Any,
    ) -> str:
        """
        Convert a metadata value to readable text.
        """

        if isinstance(
            value,
            bool,
        ):

            return (
                "Yes"
                if value
                else "No"
            )

        if isinstance(
            value,
            dict,
        ):

            return json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            return "\n".join(
                f"• {item}"
                for item in value
            )

        return str(
            value
        )

    @classmethod
    def _format_optional_size(
        cls,
        value: Any,
    ) -> str | None:
        """
        Format optional byte size.
        """

        if value is None:

            return None

        try:

            return cls._format_size(
                int(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            return str(
                value
            )

    @staticmethod
    def _format_dimensions_pair(
        width: Any,
        height: Any,
    ) -> str | None:
        """
        Format width and height pair.
        """

        if (
            width is None
            or height is None
        ):

            return None

        return (
            f"{width} × {height}"
        )

    @classmethod
    def _format_hashes_text(
        cls,
        image: dict[str, Any],
        metadata: dict[str, Any],
    ) -> str:

        hashes = {
            "sha256": (
                image.get(
                    "sha256"
                )
            ),
            "phash": (
                metadata.get(
                    "phash"
                )
            ),
            "average_hash": (
                metadata.get(
                    "average_hash"
                )
            ),
            "color_hash": (
                metadata.get(
                    "color_hash"
                )
            ),
        }

        return cls._format_generic_result(
            {
                key: value
                for key, value in hashes.items()
                if value
            }
        )

    @staticmethod
    def _populate_generic_list(
        widget: QListWidget,
        values: Any,
    ) -> None:

        widget.clear()

        if not isinstance(
            values,
            list,
        ):

            return

        for value in values:

            if isinstance(
                value,
                dict,
            ):

                text = json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                )

            else:

                text = str(
                    value
                )

            widget.addItem(
                text
            )

    def _populate_faces(
        self,
        faces: Any,
    ) -> None:
        """
        Populate detected faces and preserve
        face metadata in each list item.
        """

        self.faces_list.clear()

        if not isinstance(
            faces,
            list,
        ):

            return

        for index, face in enumerate(
            faces,
            start=1,
        ):

            if isinstance(
                face,
                dict,
            ):

                face_id = str(
                    face.get(
                        "id"
                    )
                    or f"face_{index}"
                )

                label = str(
                    face.get(
                        "label"
                    )
                    or face.get(
                        "cluster"
                    )
                    or f"Face {index}"
                )

                confidence = (
                    face.get(
                        "confidence"
                    )
                )

                if confidence is not None:

                    try:

                        confidence_text = (
                            f"{float(confidence) * 100.0:.1f}%"
                        )

                        label = (
                            f"{label}\n"
                            f"{confidence_text}"
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):

                        pass

                item = QListWidgetItem(
                    label
                )

                item.setData(
                    Qt.ItemDataRole.UserRole,
                    {
                        **face,
                        "id": face_id,
                    },
                )

                self.faces_list.addItem(
                    item
                )

            else:

                item = QListWidgetItem(
                    f"Face {index}"
                )

                item.setData(
                    Qt.ItemDataRole.UserRole,
                    {
                        "id": (
                            f"face_{index}"
                        ),
                        "index": (
                            index - 1
                        ),
                    },
                )

                self.faces_list.addItem(
                    item
                )

        if (
            self.faces_list.count()
            > 0
        ):

            self.faces_list.setCurrentRow(
                0
            )

    def _build_thumbnail_icon(
        self,
        image: dict[str, Any],
    ) -> QIcon:

        metadata = self._metadata_dict(
            image
        )

        thumbnail_path = str(
            metadata.get(
                "thumbnail_path"
            )
            or image.get(
                "thumbnail_path"
            )
            or image.get(
                "file_path"
            )
            or ""
        )

        if not thumbnail_path:

            return QIcon()

        pixmap = QPixmap(
            thumbnail_path
        )

        if pixmap.isNull():

            return QIcon()

        scaled = pixmap.scaled(
            QSize(
                132,
                96,
            ),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        return QIcon(
            scaled
        )

    def _build_thumbnail_icon(
        self,
        image: dict[str, Any],
    ) -> QIcon:
        """
        Build an icon from a cached thumbnail.

        Falls back to the original image when no thumbnail
        is available.
        """

        metadata = self._metadata_dict(
            image
        )

        processing_metadata = (
            self._processing_metadata_dict(
                image
            )
        )

        thumbnail_data = (
            processing_metadata.get(
                "thumbnail"
            )
        )

        thumbnail_path = ""

        if isinstance(
            thumbnail_data,
            dict,
        ):

            thumbnail_path = str(
                thumbnail_data.get(
                    "thumbnail_path"
                )
                or thumbnail_data.get(
                    "path"
                )
                or ""
            )

        if not thumbnail_path:

            thumbnail_path = str(
                processing_metadata.get(
                    "thumbnail_path"
                )
                or metadata.get(
                    "thumbnail_path"
                )
                or image.get(
                    "thumbnail_path"
                )
                or ""
            )

        preview_path = (
            thumbnail_path
            or str(
                image.get(
                    "file_path"
                )
                or ""
            )
        )

        if not preview_path:

            return QIcon()

        pixmap = QPixmap(
            preview_path
        )

        if pixmap.isNull():

            original_path = str(
                image.get(
                    "file_path"
                )
                or ""
            )

            if (
                original_path
                and original_path != preview_path
            ):

                pixmap = QPixmap(
                    original_path
                )

        if pixmap.isNull():

            return QIcon()

        scaled = pixmap.scaled(
            QSize(
                132,
                96,
            ),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        return QIcon(
            scaled
        )

    def _build_image_tooltip(
        self,
        image: dict[str, Any],
    ) -> str:
        """
        Build a detailed tooltip for one image item.
        """

        metadata = self._metadata_dict(
            image
        )

        processing_metadata = (
            self._processing_metadata_dict(
                image
            )
        )

        width = (
            processing_metadata.get(
                "width"
            )
            or metadata.get(
                "width"
            )
        )

        height = (
            processing_metadata.get(
                "height"
            )
            or metadata.get(
                "height"
            )
        )

        dimensions = (
            f"{width} × {height}"
            if width and height
            else "Unavailable"
        )

        image_format = (
            processing_metadata.get(
                "image_format"
            )
            or metadata.get(
                "image_format"
            )
            or Path(
                str(
                    image.get(
                        "file_path"
                    )
                    or ""
                )
            ).suffix.lstrip(".").upper()
            or "Unavailable"
        )

        size_bytes = (
            self._image_size_bytes(
                image
            )
        )

        processing_status = (
            self._processing_status(
                image
            )
        )

        created_at = str(
            image.get(
                "created_at"
            )
            or "Unavailable"
        )

        sha256 = str(
            image.get(
                "sha256"
            )
            or "Unavailable"
        )

        return (
            f"Title: {image.get('title') or 'Image'}\n"
            f"Format: {image_format}\n"
            f"MIME type: {image.get('mime_type') or 'Unavailable'}\n"
            f"Dimensions: {dimensions}\n"
            f"Size: {self._format_size(size_bytes)}\n"
            f"Status: {processing_status}\n"
            f"Imported: {created_at}\n"
            f"SHA-256: {sha256}"
        )

    # ==========================================================
    # Events
    # ==========================================================

    def resizeEvent(
        self,
        event,
    ) -> None:
        """Keep the empty-state label aligned with the viewport."""

        super().resizeEvent(event)

        if hasattr(self, "viewer_empty_label") and hasattr(self, "image_viewer"):
            self.viewer_empty_label.setGeometry(self.image_viewer.viewport().rect())

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply active application language.

        Full translation keys can be added after the interface
        structure has been approved.
        """

        self.title_label.setText(
            self.translate(
                "photos.title",
                default="Photos",
            )
        )

        self.description_label.setText(
            self.translate(
                "photos.description",
                default=(
                    "Review, inspect and analyze image evidence "
                    "inside the current investigation."
                ),
            )
        )

        self.import_button.setText(
            self.translate(
                "photos.import",
                default="Import photos...",
            )
        )

        self.search_input.setPlaceholderText(
            self.translate(
                "photos.search.placeholder",
                default="Search photos...",
            )
        )

        self.library_title.setText(
            self.translate(
                "photos.library.title",
                default="Image library",
            )
        )

        self.analysis_header.setText(
            self.translate(
                "photos.analysis.title",
                default="Image analysis",
            )
        )
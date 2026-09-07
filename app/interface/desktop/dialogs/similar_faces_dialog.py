"""
Similar faces dialog.

Displays Face Memory similarity search results.

Responsible for:

- displaying the selected query face
- displaying the currently selected matching face
- cropping faces using stored bounding boxes
- listing visually similar face observations
- displaying similarity information
- displaying linked Face Profile information
- allowing the user to inspect individual matches

Does NOT:

- calculate face embeddings
- perform vector similarity search
- access repositories
- modify Face Profiles
- commit database transactions
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    Qt,
    QRect,
    Signal,
)

from PySide6.QtGui import (
    QPixmap,
)

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SimilarFacesDialog(
    QDialog,
):

    create_profile_requested = Signal(
        str,
    )

    assign_profile_requested = Signal(
        str,
    )

    create_profile_requested = Signal(
        str,
    )

    assign_profile_requested = Signal(
        str,
    )

    """
    Dialog for reviewing Face Memory
    similarity search results.
    """

    FACE_CROP_PADDING = 0.20

    def __init__(
        self,
        search_result: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        if not isinstance(
            search_result,
            dict,
        ):

            raise TypeError(
                "search_result must be a dictionary."
            )

        self.search_result = dict(
            search_result
        )

        self.query_face = (
            self.search_result.get(
                "query_face",
                {},
            )
        )

        if not isinstance(
            self.query_face,
            dict,
        ):

            self.query_face = {}

        raw_matches = (
            self.search_result.get(
                "matches",
                [],
            )
        )

        if isinstance(
            raw_matches,
            list,
        ):

            self.matches = [
                match
                for match in raw_matches
                if isinstance(
                    match,
                    dict,
                )
            ]

        else:

            self.matches = []

        self._current_match_index: (
            int | None
        ) = None

        self.setObjectName(
            "SimilarFacesDialog"
        )

        self.setWindowTitle(
            "Similar Faces"
        )

        self.setModal(
            True
        )

        self.resize(
            1100,
            800,
        )

        self.setMinimumSize(
            820,
            620,
        )

        self._setup_ui()
        self._load_summary()
        self._load_query_face()
        self._load_matches()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:

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
            14
        )

        # ------------------------------------------------------
        # Header
        # ------------------------------------------------------

        self.header_frame = QFrame(
            self
        )

        self.header_frame.setObjectName(
            "SimilarFacesHeader"
        )

        self.header_layout = QVBoxLayout(
            self.header_frame
        )

        self.header_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.header_layout.setSpacing(
            6
        )

        self.title_label = QLabel(
            "Similar Faces",
            self.header_frame,
        )

        self.title_label.setObjectName(
            "SimilarFacesTitle"
        )

        self.subtitle_label = QLabel(
            (
                "Review Face Memory observations "
                "that are visually similar to the "
                "selected face."
            ),
            self.header_frame,
        )

        self.subtitle_label.setObjectName(
            "SimilarFacesSubtitle"
        )

        self.subtitle_label.setWordWrap(
            True
        )

        self.header_layout.addWidget(
            self.title_label
        )

        self.header_layout.addWidget(
            self.subtitle_label
        )

        self.main_layout.addWidget(
            self.header_frame
        )

        # ------------------------------------------------------
        # Summary
        # ------------------------------------------------------

        self.summary_frame = QFrame(
            self
        )

        self.summary_frame.setObjectName(
            "SimilarFacesSummary"
        )

        self.summary_layout = QHBoxLayout(
            self.summary_frame
        )

        self.summary_layout.setContentsMargins(
            12,
            10,
            12,
            10,
        )

        self.summary_layout.setSpacing(
            18
        )

        self.query_label = QLabel(
            self.summary_frame
        )

        self.matches_label = QLabel(
            self.summary_frame
        )

        self.threshold_label = QLabel(
            self.summary_frame
        )

        for label in (
            self.query_label,
            self.matches_label,
            self.threshold_label,
        ):

            label.setObjectName(
                "SimilarFacesSummaryLabel"
            )

            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

            self.summary_layout.addWidget(
                label
            )

        self.summary_layout.addStretch(
            1
        )

        self.main_layout.addWidget(
            self.summary_frame
        )

        # ------------------------------------------------------
        # Face comparison area
        # ------------------------------------------------------

        self.face_splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )

        self.face_splitter.setObjectName(
            "SimilarFacesSplitter"
        )

        self.query_frame = (
            self._create_face_panel(
                title="Selected face",
                query=True,
            )
        )

        self.match_frame = (
            self._create_face_panel(
                title="Selected match",
                query=False,
            )
        )

        self.face_splitter.addWidget(
            self.query_frame
        )

        self.face_splitter.addWidget(
            self.match_frame
        )

        self.face_splitter.setStretchFactor(
            0,
            1,
        )

        self.face_splitter.setStretchFactor(
            1,
            1,
        )

        self.main_layout.addWidget(
            self.face_splitter,
            3,
        )

        # ------------------------------------------------------
        # Selected match metadata
        # ------------------------------------------------------

        self.match_info_frame = QFrame(
            self
        )

        self.match_info_frame.setObjectName(
            "SimilarFacesMatchInfo"
        )

        self.match_info_layout = QHBoxLayout(
            self.match_info_frame
        )

        self.match_info_layout.setContentsMargins(
            12,
            8,
            12,
            8,
        )

        self.match_info_layout.setSpacing(
            18
        )

        self.similarity_label = QLabel(
            "Similarity: —",
            self.match_info_frame,
        )

        self.classification_label = QLabel(
            "Classification: —",
            self.match_info_frame,
        )

        self.profile_label = QLabel(
            "Profile: —",
            self.match_info_frame,
        )

        for label in (
            self.similarity_label,
            self.classification_label,
            self.profile_label,
        ):

            label.setObjectName(
                "SimilarFacesMatchInfoLabel"
            )

            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

            self.match_info_layout.addWidget(
                label
            )

        self.match_info_layout.addStretch(
            1
        )

        self.main_layout.addWidget(
            self.match_info_frame
        )

        # ------------------------------------------------------
        # Results
        # ------------------------------------------------------

        self.results_label = QLabel(
            "Face Memory matches",
            self,
        )

        self.results_label.setObjectName(
            "SimilarFacesSectionTitle"
        )

        self.main_layout.addWidget(
            self.results_label
        )

        self.results_table = QTableWidget(
            self
        )

        self.results_table.setObjectName(
            "SimilarFacesResultsTable"
        )

        self.results_table.setColumnCount(
            5
        )

        self.results_table.setHorizontalHeaderLabels(
            [
                "Face",
                "Evidence",
                "Similarity",
                "Classification",
                "Profile",
            ]
        )

        self.results_table.setSelectionBehavior(
            QAbstractItemView
            .SelectionBehavior
            .SelectRows
        )

        self.results_table.setSelectionMode(
            QAbstractItemView
            .SelectionMode
            .SingleSelection
        )

        self.results_table.setEditTriggers(
            QAbstractItemView
            .EditTrigger
            .NoEditTriggers
        )

        self.results_table.setAlternatingRowColors(
            True
        )

        self.results_table.verticalHeader().setVisible(
            False
        )

        header = (
            self.results_table
            .horizontalHeader()
        )

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        self.results_table.itemSelectionChanged.connect(
            self._on_match_selected
        )

        self.main_layout.addWidget(
            self.results_table,
            2,
        )

        # ------------------------------------------------------
        # Buttons
        # ------------------------------------------------------

        self.button_box = QDialogButtonBox(
            self
        )

        self.details_button = QPushButton(
            "Match details",
            self.button_box,
        )

        self.create_profile_button = QPushButton(
            "Create profile",
            self.button_box,
        )

        self.assign_profile_button = QPushButton(
            "Assign to profile",
            self.button_box,
        )

        self.create_profile_button.setObjectName(
            "SimilarFacesCreateProfileButton"
        )

        self.assign_profile_button.setObjectName(
            "SimilarFacesAssignProfileButton"
        )

        self.close_button = QPushButton(
            "Close",
            self.button_box,
        )

        self.details_button.setObjectName(
            "SimilarFacesDetailsButton"
        )

        self.close_button.setObjectName(
            "SimilarFacesCloseButton"
        )

        self.button_box.addButton(
            self.details_button,
            QDialogButtonBox.ButtonRole.ActionRole,
        )

        self.button_box.addButton(
            self.close_button,
            QDialogButtonBox.ButtonRole.RejectRole,
        )

        self.button_box.addButton(
            self.create_profile_button,
            QDialogButtonBox.ButtonRole.ActionRole,
        )

        self.button_box.addButton(
            self.assign_profile_button,
            QDialogButtonBox.ButtonRole.ActionRole,
        )

        self.details_button.clicked.connect(
            self._show_match_details
        )

        self.close_button.clicked.connect(
            self.reject
        )

        self.create_profile_button.clicked.connect(
            self._emit_create_profile
        )

        self.assign_profile_button.clicked.connect(
            self._emit_assign_profile
        )

        self.details_button.setEnabled(
            False
        )

        self.create_profile_button.setEnabled(
            False
        )

        self.assign_profile_button.setEnabled(
            False
        )

        self.main_layout.addWidget(
            self.button_box
        )



    def _create_face_panel(
        self,
        *,
        title: str,
        query: bool,
    ) -> QFrame:
        """
        Create one face preview panel.
        """

        frame = QFrame(
            self
        )

        frame.setObjectName(
            (
                "SimilarFacesQueryPanel"
                if query
                else "SimilarFacesMatchPanel"
            )
        )

        layout = QVBoxLayout(
            frame
        )

        layout.setContentsMargins(
            10,
            10,
            10,
            10,
        )

        layout.setSpacing(
            8
        )

        title_label = QLabel(
            title,
            frame,
        )

        title_label.setObjectName(
            "SimilarFacesPanelTitle"
        )

        image_label = QLabel(
            frame
        )

        image_label.setObjectName(
            (
                "SimilarFacesQueryImage"
                if query
                else "SimilarFacesMatchImage"
            )
        )

        image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        image_label.setMinimumSize(
            280,
            240,
        )

        image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        image_label.setText(
            "No face"
        )

        face_label = QLabel(
            frame
        )

        face_label.setObjectName(
            "SimilarFacesFaceName"
        )

        face_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        face_label.setWordWrap(
            True
        )

        face_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        layout.addWidget(
            title_label
        )

        layout.addWidget(
            image_label,
            1,
        )

        layout.addWidget(
            face_label
        )

        if query:

            self.query_image_label = (
                image_label
            )

            self.query_name_label = (
                face_label
            )

        else:

            self.match_image_label = (
                image_label
            )

            self.match_name_label = (
                face_label
            )

        return frame

    # ==========================================================
    # Data
    # ==========================================================

    def _load_summary(
        self,
    ) -> None:

        face_id = str(
            self.query_face.get(
                "face_id"
            )
            or "Unknown face"
        )

        self.query_label.setText(
            f"Query face: {face_id}"
        )

        self.matches_label.setText(
            f"Matches: {len(self.matches)}"
        )

        threshold = (
            self.search_result.get(
                "minimum_similarity",
                0.0,
            )
        )

        self.threshold_label.setText(
            (
                "Threshold: "
                + self._format_similarity(
                    threshold
                )
            )
        )

    def _load_query_face(
        self,
    ) -> None:
        """
        Load query-face crop.
        """

        face_id = str(
            self.query_face.get(
                "face_id"
            )
            or "Unknown face"
        )

        self.query_name_label.setText(
            face_id
        )

        image_path = (
            self.query_face.get(
                "image_path"
            )
        )

        bbox = (
            self.query_face.get(
                "bbox"
            )
        )

        self._set_face_crop(
            self.query_image_label,
            image_path=image_path,
            bbox=bbox,
        )

    def _load_matches(
        self,
    ) -> None:

        self.results_table.setRowCount(
            len(
                self.matches
            )
        )

        for row, match in enumerate(
            self.matches
        ):

            embedding = (
                self._extract_embedding(
                    match
                )
            )

            face_id = str(
                embedding.get(
                    "face_id"
                )
                or "Unknown face"
            )

            evidence_id = str(
                embedding.get(
                    "evidence_id"
                )
                or "Unknown evidence"
            )

            similarity = (
                self._format_similarity(
                    match.get(
                        "similarity"
                    )
                )
            )

            classification = str(
                match.get(
                    "classification"
                )
                or "unknown"
            )

            profile_name = (
                self._extract_profile_name(
                    match
                )
            )

            values = (
                face_id,
                evidence_id,
                similarity,
                classification,
                profile_name,
            )

            for column, value in enumerate(
                values
            ):

                item = QTableWidgetItem(
                    value
                )

                if column == 0:

                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        row,
                    )

                self.results_table.setItem(
                    row,
                    column,
                    item,
                )

        if self.matches:

            self.results_table.selectRow(
                0
            )

        else:

            self._clear_match()

    # ==========================================================
    # Selection
    # ==========================================================

    def _on_match_selected(
        self,
    ) -> None:

        selected_rows = (
            self.results_table
            .selectionModel()
            .selectedRows()
        )

        if not selected_rows:

            self._clear_match()

            return

        row = selected_rows[
            0
        ].row()

        if not (
            0
            <= row
            < len(
                self.matches
            )
        ):

            self._clear_match()

            return

        self._current_match_index = (
            row
        )

        match = self.matches[
            row
        ]

        embedding = (
            self._extract_embedding(
                match
            )
        )

        face_id = str(
            embedding.get(
                "face_id"
            )
            or "Unknown face"
        )

        self.match_name_label.setText(
            face_id
        )

        self._set_face_crop(
            self.match_image_label,
            image_path=(
                match.get(
                    "image_path"
                )
            ),
            bbox=(
                embedding.get(
                    "bbox"
                )
            ),
        )

        self.similarity_label.setText(
            (
                "Similarity: "
                + self._format_similarity(
                    match.get(
                        "similarity"
                    )
                )
            )
        )

        self.classification_label.setText(
            (
                "Classification: "
                + str(
                    match.get(
                        "classification"
                    )
                    or "unknown"
                )
            )
        )

        self.profile_label.setText(
            (
                "Profile: "
                + self._extract_profile_name(
                    match
                )
            )
        )

        self.details_button.setEnabled(
            True
        )

        self.create_profile_button.setEnabled(
            True
        )

        self.assign_profile_button.setEnabled(
            True
        )

    def _clear_match(
        self,
    ) -> None:

        self._current_match_index = (
            None
        )

        self.match_image_label.clear()

        self.match_image_label.setText(
            "Select a result"
        )

        self.match_name_label.clear()

        self.similarity_label.setText(
            "Similarity: —"
        )

        self.classification_label.setText(
            "Classification: —"
        )

        self.profile_label.setText(
            "Profile: —"
        )

        self.details_button.setEnabled(
            False
        )

        self.create_profile_button.setEnabled(
            False
        )

        self.assign_profile_button.setEnabled(
            False
        )

    # ==========================================================
    # Actions
    # ==========================================================

    def _show_match_details(
        self,
    ) -> None:

        if (
            self._current_match_index
            is None
        ):

            return

        match = self.matches[
            self._current_match_index
        ]

        embedding = (
            self._extract_embedding(
                match
            )
        )

        lines: list[str] = []

        lines.append(
            (
                "Face: "
                + str(
                    embedding.get(
                        "face_id"
                    )
                    or "Unknown face"
                )
            )
        )

        lines.append(
            (
                "Evidence: "
                + str(
                    embedding.get(
                        "evidence_id"
                    )
                    or "Unknown evidence"
                )
            )
        )

        lines.append(
            (
                "Embedding ID: "
                + str(
                    embedding.get(
                        "id"
                    )
                    or "Unavailable"
                )
            )
        )

        lines.append(
            (
                "Similarity: "
                + self._format_similarity(
                    match.get(
                        "similarity"
                    )
                )
            )
        )

        lines.append(
            (
                "Distance: "
                + self._format_number(
                    match.get(
                        "distance"
                    )
                )
            )
        )

        lines.append(
            (
                "Classification: "
                + str(
                    match.get(
                        "classification"
                    )
                    or "unknown"
                )
            )
        )

        lines.append(
            (
                "Profile: "
                + self._extract_profile_name(
                    match
                )
            )
        )

        QMessageBox.information(
            self,
            "Face match details",
            "\n".join(
                lines
            ),
        )

    def _emit_create_profile(
        self,
    ) -> None:
        """
        Request creation of a Face Profile
        from the selected observation.
        """

        embedding_id = (
            self._selected_embedding_id()
        )

        if not embedding_id:

            return

        self.create_profile_requested.emit(
            embedding_id
        )

    def _emit_assign_profile(
        self,
    ) -> None:
        """
        Request assignment of the selected
        observation to an existing profile.
        """

        embedding_id = (
            self._selected_embedding_id()
        )

        if not embedding_id:

            return

        self.assign_profile_requested.emit(
            embedding_id
        )

    def _selected_embedding_id(
        self,
    ) -> str | None:
        """
        Return persistent FaceEmbedding ID
        for the currently selected match.
        """

        if (
            self._current_match_index
            is None
        ):

            return None

        if not (
            0
            <= self._current_match_index
            < len(
                self.matches
            )
        ):

            return None

        match = self.matches[
            self._current_match_index
        ]

        embedding = (
            self._extract_embedding(
                match
            )
        )

        embedding_id = str(
            embedding.get(
                "id"
            )
            or embedding.get(
                "embedding_id"
            )
            or ""
        ).strip()

        if not embedding_id:

            return None

        return embedding_id

    # ==========================================================
    # Face image helpers
    # ==========================================================

    def _set_face_crop(
        self,
        label: QLabel,
        *,
        image_path: Any,
        bbox: Any,
    ) -> None:
        """
        Load an image, crop the stored face region,
        and display it in the provided label.
        """

        path = self._normalize_path(
            image_path
        )

        if (
            path is None
            or not path.exists()
            or not path.is_file()
        ):

            label.clear()

            label.setText(
                "Image unavailable"
            )

            return

        pixmap = QPixmap(
            str(
                path
            )
        )

        if pixmap.isNull():

            label.clear()

            label.setText(
                "Preview unavailable"
            )

            return

        crop_rect = (
            self._bbox_to_rect(
                bbox=bbox,
                image_width=(
                    pixmap.width()
                ),
                image_height=(
                    pixmap.height()
                ),
            )
        )

        if crop_rect is None:

            face_pixmap = pixmap

        else:

            face_pixmap = pixmap.copy(
                crop_rect
            )

        target_size = label.size()

        if (
            target_size.width()
            <= 1
            or target_size.height()
            <= 1
        ):

            target_size = (
                label.minimumSize()
            )

        scaled = (
            face_pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        label.setPixmap(
            scaled
        )

    @classmethod
    def _bbox_to_rect(
        cls,
        *,
        bbox: Any,
        image_width: int,
        image_height: int,
    ) -> QRect | None:
        """
        Convert stored bbox dictionary into
        a padded QRect constrained to the image.
        """

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

    @staticmethod
    def _normalize_path(
        value: Any,
    ) -> Path | None:

        raw_path = str(
            value
            or ""
        ).strip()

        if not raw_path:

            return None

        return Path(
            raw_path
        )

    # ==========================================================
    # General helpers
    # ==========================================================

    @staticmethod
    def _extract_embedding(
        match: dict[str, Any],
    ) -> dict[str, Any]:

        embedding = match.get(
            "embedding",
            {},
        )

        if isinstance(
            embedding,
            dict,
        ):

            return embedding

        return {}

    @staticmethod
    def _extract_profile_name(
        match: dict[str, Any],
    ) -> str:

        profile = match.get(
            "profile"
        )

        if not isinstance(
            profile,
            dict,
        ):

            return "Unassigned"

        return str(
            profile.get(
                "name"
            )
            or profile.get(
                "label"
            )
            or profile.get(
                "display_name"
            )
            or "Unnamed profile"
        )

    @staticmethod
    def _format_similarity(
        value: Any,
    ) -> str:

        try:

            similarity = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return "—"

        if similarity <= 1.0:

            similarity *= 100.0

        return (
            f"{similarity:.2f}%"
        )

    @staticmethod
    def _format_number(
        value: Any,
    ) -> str:

        try:

            return (
                f"{float(value):.8f}"
            )

        except (
            TypeError,
            ValueError,
        ):

            return "—"
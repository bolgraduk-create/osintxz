"""
Similar images dialog.

Displays image similarity search results.

Responsible for:

- displaying the source image
- displaying the currently selected matching image
- listing all similarity matches
- showing similarity metadata
- allowing the user to inspect individual matches

Does NOT:

- search for similar images
- calculate hashes
- compare image fingerprints
- access repositories
- commit database transactions
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    Qt,
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


class SimilarImagesDialog(
    QDialog,
):
    """
    Dialog for reviewing image similarity
    search results.
    """

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

        self.source_evidence = (
            self.search_result.get(
                "source_evidence",
                {},
            )
        )

        if not isinstance(
            self.source_evidence,
            dict,
        ):

            self.source_evidence = {}

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
                item
                for item in raw_matches
                if isinstance(
                    item,
                    dict,
                )
            ]

        else:

            self.matches = []

        self._current_match_index: (
            int | None
        ) = None

        self.setObjectName(
            "SimilarImagesDialog"
        )

        self.setWindowTitle(
            "Similar Images"
        )

        self.setModal(
            True
        )

        self.resize(
            1100,
            780,
        )

        self.setMinimumSize(
            820,
            600,
        )

        self._setup_ui()
        self._load_source()
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
            "SimilarImagesHeader"
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
            "Similar Images",
            self.header_frame,
        )

        self.title_label.setObjectName(
            "SimilarImagesTitle"
        )

        self.subtitle_label = QLabel(
            (
                "Review images that are visually "
                "similar to the selected evidence."
            ),
            self.header_frame,
        )

        self.subtitle_label.setObjectName(
            "SimilarImagesSubtitle"
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
            "SimilarImagesSummary"
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

        self.checked_label = QLabel(
            self.summary_frame
        )

        self.matches_label = QLabel(
            self.summary_frame
        )

        self.threshold_label = QLabel(
            self.summary_frame
        )

        for label in (
            self.checked_label,
            self.matches_label,
            self.threshold_label,
        ):

            label.setObjectName(
                "SimilarImagesSummaryLabel"
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
        # Image comparison area
        # ------------------------------------------------------

        self.image_splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )

        self.image_splitter.setObjectName(
            "SimilarImagesSplitter"
        )

        self.source_frame = (
            self._create_image_panel(
                title="Source image",
                source=True,
            )
        )

        self.match_frame = (
            self._create_image_panel(
                title="Selected match",
                source=False,
            )
        )

        self.image_splitter.addWidget(
            self.source_frame
        )

        self.image_splitter.addWidget(
            self.match_frame
        )

        self.image_splitter.setStretchFactor(
            0,
            1,
        )

        self.image_splitter.setStretchFactor(
            1,
            1,
        )

        self.main_layout.addWidget(
            self.image_splitter,
            3,
        )

        # ------------------------------------------------------
        # Match information
        # ------------------------------------------------------

        self.match_info_frame = QFrame(
            self
        )

        self.match_info_frame.setObjectName(
            "SimilarImagesMatchInfo"
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

        self.exact_label = QLabel(
            "Exact match: —",
            self.match_info_frame,
        )

        for label in (
            self.similarity_label,
            self.classification_label,
            self.exact_label,
        ):

            label.setObjectName(
                "SimilarImagesMatchInfoLabel"
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
        # Results table
        # ------------------------------------------------------

        self.results_label = QLabel(
            "Results",
            self,
        )

        self.results_label.setObjectName(
            "SimilarImagesSectionTitle"
        )

        self.main_layout.addWidget(
            self.results_label
        )

        self.results_table = QTableWidget(
            self
        )

        self.results_table.setObjectName(
            "SimilarImagesResultsTable"
        )

        self.results_table.setColumnCount(
            4
        )

        self.results_table.setHorizontalHeaderLabels(
            [
                "Image",
                "Similarity",
                "Classification",
                "Exact",
            ]
        )

        self.results_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.results_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.results_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
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
            QHeaderView.ResizeMode.Stretch,
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            3,
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
            "Comparison details",
            self.button_box,
        )

        self.details_button.setObjectName(
            "SimilarImagesDetailsButton"
        )

        self.close_button = QPushButton(
            "Close",
            self.button_box,
        )

        self.close_button.setObjectName(
            "SimilarImagesCloseButton"
        )

        self.button_box.addButton(
            self.details_button,
            QDialogButtonBox.ButtonRole.ActionRole,
        )

        self.button_box.addButton(
            self.close_button,
            QDialogButtonBox.ButtonRole.RejectRole,
        )

        self.details_button.clicked.connect(
            self._show_comparison_details
        )

        self.close_button.clicked.connect(
            self.reject
        )

        self.details_button.setEnabled(
            False
        )

        self.main_layout.addWidget(
            self.button_box
        )

    def _create_image_panel(
        self,
        *,
        title: str,
        source: bool,
    ) -> QFrame:
        """
        Create one side of the comparison area.
        """

        frame = QFrame(
            self
        )

        frame.setObjectName(
            (
                "SimilarImagesSourcePanel"
                if source
                else "SimilarImagesMatchPanel"
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
            "SimilarImagesPanelTitle"
        )

        image_label = QLabel(
            frame
        )

        image_label.setObjectName(
            (
                "SimilarImagesSourceImage"
                if source
                else "SimilarImagesMatchImage"
            )
        )

        image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        image_label.setMinimumSize(
            280,
            220,
        )

        image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        image_label.setText(
            "No image"
        )

        name_label = QLabel(
            frame
        )

        name_label.setObjectName(
            "SimilarImagesFileName"
        )

        name_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        name_label.setWordWrap(
            True
        )

        name_label.setTextInteractionFlags(
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
            name_label
        )

        if source:

            self.source_image_label = (
                image_label
            )

            self.source_name_label = (
                name_label
            )

        else:

            self.match_image_label = (
                image_label
            )

            self.match_name_label = (
                name_label
            )

        return frame

    # ==========================================================
    # Data
    # ==========================================================

    def _load_source(
        self,
    ) -> None:
        """
        Load source image and search summary.
        """

        source_path = self._extract_path(
            self.source_evidence
        )

        source_name = self._extract_name(
            self.source_evidence
        )

        self.source_name_label.setText(
            source_name
        )

        self._set_image(
            self.source_image_label,
            source_path,
        )

        candidate_count = int(
            self.search_result.get(
                "candidate_count",
                0,
            )
            or 0
        )

        match_count = int(
            self.search_result.get(
                "match_count",
                len(
                    self.matches
                ),
            )
            or 0
        )

        threshold = (
            self.search_result.get(
                "minimum_similarity",
                0.0,
            )
        )

        try:

            threshold_text = (
                f"{float(threshold):.2f}%"
            )

        except (
            TypeError,
            ValueError,
        ):

            threshold_text = "—"

        self.checked_label.setText(
            f"Images checked: {candidate_count}"
        )

        self.matches_label.setText(
            f"Matches: {match_count}"
        )

        self.threshold_label.setText(
            f"Threshold: {threshold_text}"
        )

    def _load_matches(
        self,
    ) -> None:
        """
        Populate results table.
        """

        self.results_table.setRowCount(
            len(
                self.matches
            )
        )

        for row, match in enumerate(
            self.matches
        ):

            evidence = match.get(
                "evidence",
                {},
            )

            if not isinstance(
                evidence,
                dict,
            ):

                evidence = {}

            name = self._extract_name(
                evidence
            )

            similarity = (
                self._format_similarity(
                    match.get(
                        "visual_similarity"
                    )
                )
            )

            classification = str(
                match.get(
                    "classification"
                )
                or "unknown"
            )

            exact = (
                "Yes"
                if bool(
                    match.get(
                        "exact_match",
                        False,
                    )
                )
                else "No"
            )

            name_item = QTableWidgetItem(
                name
            )

            similarity_item = QTableWidgetItem(
                similarity
            )

            classification_item = QTableWidgetItem(
                classification
            )

            exact_item = QTableWidgetItem(
                exact
            )

            name_item.setData(
                Qt.ItemDataRole.UserRole,
                row,
            )

            self.results_table.setItem(
                row,
                0,
                name_item,
            )

            self.results_table.setItem(
                row,
                1,
                similarity_item,
            )

            self.results_table.setItem(
                row,
                2,
                classification_item,
            )

            self.results_table.setItem(
                row,
                3,
                exact_item,
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
        """
        Display the currently selected result.
        """

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

        evidence = match.get(
            "evidence",
            {},
        )

        if not isinstance(
            evidence,
            dict,
        ):

            evidence = {}

        match_path = self._extract_path(
            evidence
        )

        match_name = self._extract_name(
            evidence
        )

        self.match_name_label.setText(
            match_name
        )

        self._set_image(
            self.match_image_label,
            match_path,
        )

        self.similarity_label.setText(
            (
                "Similarity: "
                + self._format_similarity(
                    match.get(
                        "visual_similarity"
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

        self.exact_label.setText(
            (
                "Exact match: "
                + (
                    "Yes"
                    if bool(
                        match.get(
                            "exact_match",
                            False,
                        )
                    )
                    else "No"
                )
            )
        )

        self.details_button.setEnabled(
            True
        )

    def _clear_match(
        self,
    ) -> None:
        """
        Clear selected-match preview.
        """

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

        self.exact_label.setText(
            "Exact match: —"
        )

        self.details_button.setEnabled(
            False
        )

    # ==========================================================
    # Actions
    # ==========================================================

    def _show_comparison_details(
        self,
    ) -> None:
        """
        Show detailed hash comparison.
        """

        if (
            self._current_match_index
            is None
        ):

            return

        match = self.matches[
            self._current_match_index
        ]

        comparison = match.get(
            "comparison",
            {},
        )

        if not isinstance(
            comparison,
            dict,
        ):

            comparison = {}

        lines: list[str] = []

        visual_similarity = (
            self._format_similarity(
                comparison.get(
                    "visual_similarity"
                )
            )
        )

        lines.append(
            (
                "Visual similarity: "
                f"{visual_similarity}"
            )
        )

        lines.append(
            (
                "Classification: "
                f"{comparison.get('classification', 'unknown')}"
            )
        )

        lines.append(
            (
                "Exact file match: "
                + (
                    "Yes"
                    if bool(
                        comparison.get(
                            "exact_match",
                            False,
                        )
                    )
                    else "No"
                )
            )
        )

        hash_similarity = (
            comparison.get(
                "hash_similarity",
                {},
            )
        )

        if isinstance(
            hash_similarity,
            dict,
        ) and hash_similarity:

            lines.append(
                ""
            )

            lines.append(
                "Hash similarities:"
            )

            for key, value in (
                hash_similarity.items()
            ):

                try:

                    value_text = (
                        f"{float(value):.2f}%"
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    value_text = str(
                        value
                    )

                lines.append(
                    f"{key}: {value_text}"
                )

        QMessageBox.information(
            self,
            "Comparison details",
            "\n".join(
                lines
            ),
        )

    # ==========================================================
    # Image helpers
    # ==========================================================

    def _set_image(
        self,
        label: QLabel,
        path: Path | None,
    ) -> None:
        """
        Load image preview into label.
        """

        if (
            path is None
            or not path.exists()
            or not path.is_file()
        ):

            label.clear()

            label.setText(
                "Image file unavailable"
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

        target_size = label.size()

        if (
            target_size.width()
            <= 1
            or target_size.height()
            <= 1
        ):

            target_size = label.minimumSize()

        scaled = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        label.setPixmap(
            scaled
        )

    @staticmethod
    def _extract_path(
        evidence: dict[str, Any],
    ) -> Path | None:
        """
        Resolve evidence image path.
        """

        raw_path = str(
            evidence.get(
                "file_path"
            )
            or evidence.get(
                "value"
            )
            or ""
        ).strip()

        if not raw_path:

            return None

        return Path(
            raw_path
        )

    @staticmethod
    def _extract_name(
        evidence: dict[str, Any],
    ) -> str:
        """
        Resolve readable evidence name.
        """

        title = str(
            evidence.get(
                "title"
            )
            or ""
        ).strip()

        if title:

            return title

        raw_path = str(
            evidence.get(
                "file_path"
            )
            or ""
        ).strip()

        if raw_path:

            return Path(
                raw_path
            ).name

        evidence_id = str(
            evidence.get(
                "id"
            )
            or ""
        ).strip()

        if evidence_id:

            return evidence_id

        return "Image"

    @staticmethod
    def _format_similarity(
        value: Any,
    ) -> str:
        """
        Format similarity percentage.
        """

        try:

            return (
                f"{float(value):.2f}%"
            )

        except (
            TypeError,
            ValueError,
        ):

            return "—"
"""
Select Location Photos dialog.

Allows the user to select one or more IMAGE evidence
records for attachment to a LOCATION entity.

Responsibilities:

- display image evidence thumbnails
- support multi-selection
- filter images by search text
- return selected evidence identifiers

Does NOT:

- modify database state
- create EvidenceEntity links
- commit transactions
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QSize,
    Qt,
)

from PySide6.QtGui import (
    QIcon,
    QPixmap,
)

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SelectLocationPhotosDialog(
    QDialog,
):
    """
    Dialog for selecting IMAGE evidence
    to attach to a Location.
    """

    THUMBNAIL_WIDTH = 150
    THUMBNAIL_HEIGHT = 105

    GRID_WIDTH = 185
    GRID_HEIGHT = 165

    def __init__(
        self,
        images: list[dict[str, Any]],
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._images = [
            dict(
                image
            )
            for image in images
            if isinstance(
                image,
                dict,
            )
        ]

        self.setWindowTitle(
            "Attach photos to location"
        )

        self.setModal(
            True
        )

        self.resize(
            900,
            650,
        )

        self.setMinimumSize(
            680,
            480,
        )

        self._setup_ui()

        self._populate_images()

        self._update_selection_state()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            16,
            16,
            16,
            16,
        )

        layout.setSpacing(
            12
        )

        # ------------------------------------------------------
        # Header
        # ------------------------------------------------------

        title_label = QLabel(
            "Select photos",
            self,
        )

        title_label.setObjectName(
            "SelectLocationPhotosTitle"
        )

        layout.addWidget(
            title_label
        )

        description_label = QLabel(
            (
                "Select one or more images from the current "
                "investigation to attach to this location."
            ),
            self,
        )

        description_label.setWordWrap(
            True
        )

        layout.addWidget(
            description_label
        )

        # ------------------------------------------------------
        # Search
        # ------------------------------------------------------

        search_layout = QHBoxLayout()

        search_label = QLabel(
            "Search:",
            self,
        )

        self.search_input = QLineEdit(
            self
        )

        self.search_input.setPlaceholderText(
            "Search by title, file name, path or Evidence ID..."
        )

        search_layout.addWidget(
            search_label
        )

        search_layout.addWidget(
            self.search_input,
            1,
        )

        layout.addLayout(
            search_layout
        )

        # ------------------------------------------------------
        # Image grid
        # ------------------------------------------------------

        self.image_list = QListWidget(
            self
        )

        self.image_list.setObjectName(
            "SelectLocationPhotosList"
        )

        self.image_list.setViewMode(
            QListWidget.ViewMode.IconMode
        )

        self.image_list.setResizeMode(
            QListWidget.ResizeMode.Adjust
        )

        self.image_list.setMovement(
            QListWidget.Movement.Static
        )

        self.image_list.setWrapping(
            True
        )

        self.image_list.setSpacing(
            8
        )

        self.image_list.setIconSize(
            QSize(
                self.THUMBNAIL_WIDTH,
                self.THUMBNAIL_HEIGHT,
            )
        )

        self.image_list.setGridSize(
            QSize(
                self.GRID_WIDTH,
                self.GRID_HEIGHT,
            )
        )

        self.image_list.setSelectionMode(
            QAbstractItemView
            .SelectionMode
            .ExtendedSelection
        )

        layout.addWidget(
            self.image_list,
            1,
        )

        # ------------------------------------------------------
        # Selection info
        # ------------------------------------------------------

        self.selection_label = QLabel(
            "Selected: 0",
            self,
        )

        layout.addWidget(
            self.selection_label
        )

        # ------------------------------------------------------
        # Actions
        # ------------------------------------------------------

        actions_layout = QHBoxLayout()

        actions_layout.addStretch(
            1
        )

        self.cancel_button = QPushButton(
            "Cancel",
            self,
        )

        self.attach_button = QPushButton(
            "Attach selected",
            self,
        )

        self.attach_button.setEnabled(
            False
        )

        actions_layout.addWidget(
            self.cancel_button
        )

        actions_layout.addWidget(
            self.attach_button
        )

        layout.addLayout(
            actions_layout
        )

        # ------------------------------------------------------
        # Signals
        # ------------------------------------------------------

        self.search_input.textChanged.connect(
            self._apply_filter
        )

        self.image_list.itemSelectionChanged.connect(
            self._update_selection_state
        )

        self.image_list.itemDoubleClicked.connect(
            self._on_item_double_clicked
        )

        self.cancel_button.clicked.connect(
            self.reject
        )

        self.attach_button.clicked.connect(
            self.accept
        )

    # ==========================================================
    # Population
    # ==========================================================

    def _populate_images(
        self,
    ) -> None:

        self.image_list.clear()

        for image in self._images:

            evidence_id = str(
                image.get(
                    "id"
                )
                or ""
            ).strip()

            if not evidence_id:

                continue

            title = str(
                image.get(
                    "title"
                )
                or image.get(
                    "name"
                )
                or "Untitled image"
            ).strip()

            file_path = str(
                image.get(
                    "file_path"
                )
                or ""
            ).strip()

            display_name = (
                title
                or (
                    Path(
                        file_path
                    ).name
                    if file_path
                    else "Image"
                )
            )

            item = QListWidgetItem(
                display_name
            )

            item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                image,
            )

            item.setToolTip(
                self._build_tooltip(
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

            self.image_list.addItem(
                item
            )

    # ==========================================================
    # Search
    # ==========================================================

    def _apply_filter(
        self,
        text: str,
    ) -> None:

        query = str(
            text
            or ""
        ).strip().casefold()

        for index in range(
            self.image_list.count()
        ):

            item = self.image_list.item(
                index
            )

            image = item.data(
                Qt.ItemDataRole.UserRole
            )

            if not isinstance(
                image,
                dict,
            ):

                item.setHidden(
                    True
                )

                continue

            searchable_values = [
                image.get(
                    "title"
                ),
                image.get(
                    "name"
                ),
                image.get(
                    "file_path"
                ),
                image.get(
                    "id"
                ),
            ]

            searchable_text = " ".join(
                str(
                    value
                    or ""
                )
                for value in searchable_values
            ).casefold()

            item.setHidden(
                bool(
                    query
                    and query not in searchable_text
                )
            )

        self._update_selection_state()

    # ==========================================================
    # Selection
    # ==========================================================

    def selected_evidence_ids(
        self,
    ) -> list[str]:
        """
        Return selected Evidence identifiers.
        """

        result: list[str] = []

        seen: set[str] = set()

        for item in (
            self.image_list
            .selectedItems()
        ):

            if item.isHidden():

                continue

            image = item.data(
                Qt.ItemDataRole.UserRole
            )

            if not isinstance(
                image,
                dict,
            ):

                continue

            evidence_id = str(
                image.get(
                    "id"
                )
                or ""
            ).strip()

            if (
                not evidence_id
                or evidence_id in seen
            ):

                continue

            seen.add(
                evidence_id
            )

            result.append(
                evidence_id
            )

        return result

    def _update_selection_state(
        self,
    ) -> None:

        selected_count = len(
            self.selected_evidence_ids()
        )

        self.selection_label.setText(
            f"Selected: {selected_count}"
        )

        self.attach_button.setEnabled(
            selected_count > 0
        )

    def _on_item_double_clicked(
        self,
        item: QListWidgetItem,
    ) -> None:
        """
        Double-click selects one item and accepts.
        """

        if item.isHidden():

            return

        self.image_list.clearSelection()

        item.setSelected(
            True
        )

        self.accept()

    # ==========================================================
    # Thumbnail
    # ==========================================================

    @classmethod
    def _build_thumbnail_icon(
        cls,
        image: dict[str, Any],
    ) -> QIcon:

        path_value = str(
            image.get(
                "thumbnail_path"
            )
            or image.get(
                "preview_path"
            )
            or image.get(
                "file_path"
            )
            or ""
        ).strip()

        if not path_value:

            return QIcon()

        path = Path(
            path_value
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

        scaled = pixmap.scaled(
            QSize(
                cls.THUMBNAIL_WIDTH,
                cls.THUMBNAIL_HEIGHT,
            ),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        return QIcon(
            scaled
        )

    # ==========================================================
    # Tooltip
    # ==========================================================

    @staticmethod
    def _build_tooltip(
        image: dict[str, Any],
    ) -> str:

        title = str(
            image.get(
                "title"
            )
            or "Untitled image"
        ).strip()

        evidence_id = str(
            image.get(
                "id"
            )
            or ""
        ).strip()

        file_path = str(
            image.get(
                "file_path"
            )
            or ""
        ).strip()

        mime_type = str(
            image.get(
                "mime_type"
            )
            or ""
        ).strip()

        lines = [
            title,
        ]

        if evidence_id:

            lines.append(
                f"Evidence ID: {evidence_id}"
            )

        if file_path:

            lines.append(
                f"Path: {file_path}"
            )

        else:

            lines.append(
                "Path: unavailable"
            )

        if mime_type:

            lines.append(
                f"MIME: {mime_type}"
            )

        return "\n".join(
            lines
        )
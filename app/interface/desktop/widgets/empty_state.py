"""
Reusable empty state component.

Responsible for:

- displaying an empty data state
- displaying an optional icon or marker
- displaying a title
- displaying a description
- providing one or more actions
- providing optional custom content

Does NOT:

- execute business logic
- access controllers
- access services
- load application data
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class EmptyState(QFrame):
    """
    Reusable empty-state component.

    The component contains:

    - optional visual marker
    - title
    - optional description
    - optional custom content
    - optional actions
    """

    def __init__(
        self,
        title: str,
        description: str | None = None,
        marker: str | None = None,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._title_text = (
            title or ""
        )

        self._description_text = (
            description or ""
        )

        self._marker_text = (
            marker or ""
        )

        self.setObjectName(
            "EmptyState"
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._setup_ui()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Build empty-state structure.
        """

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            32,
            48,
            32,
            48,
        )

        self.main_layout.setSpacing(
            12
        )

        self.main_layout.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self._create_marker()
        self._create_text_content()
        self._create_custom_content()
        self._create_actions()

        self._update_visibility()

    def _create_marker(
        self,
    ) -> None:
        """
        Create optional visual marker.
        """

        self.marker_container = QFrame(
            self
        )

        self.marker_container.setObjectName(
            "EmptyStateMarkerContainer"
        )

        marker_layout = QVBoxLayout(
            self.marker_container
        )

        marker_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        marker_layout.setSpacing(
            0
        )

        marker_layout.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.marker_label = QLabel(
            self._marker_text,
            self.marker_container,
        )

        self.marker_label.setObjectName(
            "EmptyStateMarker"
        )

        self.marker_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        marker_layout.addWidget(
            self.marker_label
        )

        self.main_layout.addWidget(
            self.marker_container,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

    def _create_text_content(
        self,
    ) -> None:
        """
        Create title and description.
        """

        self.text_container = QFrame(
            self
        )

        self.text_container.setObjectName(
            "EmptyStateTextContainer"
        )

        text_layout = QVBoxLayout(
            self.text_container
        )

        text_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        text_layout.setSpacing(
            6
        )

        text_layout.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.title_label = QLabel(
            self._title_text,
            self.text_container,
        )

        self.title_label.setObjectName(
            "EmptyStateTitle"
        )

        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.title_label.setWordWrap(
            True
        )

        self.description_label = QLabel(
            self._description_text,
            self.text_container,
        )

        self.description_label.setObjectName(
            "EmptyStateDescription"
        )

        self.description_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.description_label.setWordWrap(
            True
        )

        text_layout.addWidget(
            self.title_label
        )

        text_layout.addWidget(
            self.description_label
        )

        self.main_layout.addWidget(
            self.text_container,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

    def _create_custom_content(
        self,
    ) -> None:
        """
        Create optional custom content area.
        """

        self.content_container = QFrame(
            self
        )

        self.content_container.setObjectName(
            "EmptyStateContent"
        )

        self.content_layout = QVBoxLayout(
            self.content_container
        )

        self.content_layout.setContentsMargins(
            0,
            4,
            0,
            4,
        )

        self.content_layout.setSpacing(
            8
        )

        self.content_layout.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.main_layout.addWidget(
            self.content_container,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

    def _create_actions(
        self,
    ) -> None:
        """
        Create empty-state actions area.
        """

        self.actions_container = QFrame(
            self
        )

        self.actions_container.setObjectName(
            "EmptyStateActions"
        )

        self.actions_layout = QHBoxLayout(
            self.actions_container
        )

        self.actions_layout.setContentsMargins(
            0,
            6,
            0,
            0,
        )

        self.actions_layout.setSpacing(
            8
        )

        self.actions_layout.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.main_layout.addWidget(
            self.actions_container,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )

    # ==========================================================
    # Text API
    # ==========================================================

    def set_title(
        self,
        title: str,
    ) -> None:
        """
        Update empty-state title.
        """

        self._title_text = (
            title or ""
        )

        self.title_label.setText(
            self._title_text
        )

        self._update_visibility()

    def title(
        self,
    ) -> str:
        """
        Return current title.
        """

        return self._title_text

    def set_description(
        self,
        description: str | None,
    ) -> None:
        """
        Update empty-state description.
        """

        self._description_text = (
            description or ""
        )

        self.description_label.setText(
            self._description_text
        )

        self._update_visibility()

    def description(
        self,
    ) -> str:
        """
        Return current description.
        """

        return self._description_text

    def set_marker(
        self,
        marker: str | None,
    ) -> None:
        """
        Update visual marker.
        """

        self._marker_text = (
            marker or ""
        )

        self.marker_label.setText(
            self._marker_text
        )

        self._update_visibility()

    def marker(
        self,
    ) -> str:
        """
        Return current marker.
        """

        return self._marker_text

    # ==========================================================
    # Content API
    # ==========================================================

    def add_widget(
        self,
        widget: QWidget,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Add custom widget to the content area.
        """

        if alignment is None:

            self.content_layout.addWidget(
                widget
            )

        else:

            self.content_layout.addWidget(
                widget,
                0,
                alignment,
            )

        self._update_visibility()

    def add_layout(
        self,
        layout,
    ) -> None:
        """
        Add custom layout to the content area.
        """

        self.content_layout.addLayout(
            layout
        )

        self._update_visibility()

    def clear_content(
        self,
    ) -> None:
        """
        Remove all custom content.
        """

        self._clear_layout(
            self.content_layout
        )

        self._update_visibility()

    # ==========================================================
    # Actions API
    # ==========================================================

    def add_action(
        self,
        widget: QWidget,
    ) -> None:
        """
        Add action widget.
        """

        self.actions_layout.addWidget(
            widget
        )

        self._update_visibility()

    def clear_actions(
        self,
    ) -> None:
        """
        Remove all action widgets.
        """

        self._clear_layout(
            self.actions_layout
        )

        self._update_visibility()

    # ==========================================================
    # Appearance API
    # ==========================================================

    def set_variant(
        self,
        variant: str,
    ) -> None:
        """
        Set empty-state visual variant.

        Supported values:

        - default
        - panel
        - compact
        - illustrated
        """

        normalized_variant = (
            variant.strip().casefold()
        )

        supported_variants = {
            "default",
            "panel",
            "compact",
            "illustrated",
        }

        if normalized_variant not in supported_variants:

            normalized_variant = "default"

        self.setProperty(
            "variant",
            normalized_variant,
        )

        if normalized_variant == "compact":

            self.main_layout.setContentsMargins(
                20,
                24,
                20,
                24,
            )

            self.main_layout.setSpacing(
                8
            )

        else:

            self.main_layout.setContentsMargins(
                32,
                48,
                32,
                48,
            )

            self.main_layout.setSpacing(
                12
            )

        self.style().unpolish(
            self
        )

        self.style().polish(
            self
        )

        self.update()

    # ==========================================================
    # Internal helpers
    # ==========================================================

    def _update_visibility(
        self,
    ) -> None:
        """
        Update child element visibility.
        """

        has_title = bool(
            self._title_text.strip()
        )

        has_description = bool(
            self._description_text.strip()
        )

        has_marker = bool(
            self._marker_text.strip()
        )

        has_content = (
            self.content_layout.count() > 0
        )

        has_actions = (
            self.actions_layout.count() > 0
        )

        self.title_label.setVisible(
            has_title
        )

        self.description_label.setVisible(
            has_description
        )

        self.text_container.setVisible(
            has_title or has_description
        )

        self.marker_container.setVisible(
            has_marker
        )

        self.content_container.setVisible(
            has_content
        )

        self.actions_container.setVisible(
            has_actions
        )

    @staticmethod
    def _clear_layout(
        layout,
    ) -> None:
        """
        Recursively remove layout contents.
        """

        while layout.count():

            item = layout.takeAt(
                0
            )

            widget = item.widget()

            if widget is not None:

                widget.setParent(
                    None
                )

                widget.deleteLater()

                continue

            child_layout = item.layout()

            if child_layout is not None:

                EmptyState._clear_layout(
                    child_layout
                )

                child_layout.deleteLater()
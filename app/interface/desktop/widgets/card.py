"""
Reusable desktop card component.

Responsible for:

- providing a consistent card container
- displaying an optional title
- displaying an optional subtitle
- providing a content layout
- providing optional header actions

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


class Card(QFrame):
    """
    Reusable application card.

    The component contains:

    - optional header
    - optional title
    - optional subtitle
    - optional action area
    - main content layout
    """

    def __init__(
        self,
        title: str | None = None,
        subtitle: str | None = None,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._title_text = (
            title or ""
        )

        self._subtitle_text = (
            subtitle or ""
        )

        self.setObjectName(
            "Card"
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self._setup_ui()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Build card structure.
        """

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            18,
            18,
            18,
            18,
        )

        self.main_layout.setSpacing(
            14
        )

        self._create_header()
        self._create_content()

    def _create_header(
        self,
    ) -> None:
        """
        Create optional card header.
        """

        self.header = QFrame(
            self
        )

        self.header.setObjectName(
            "CardHeader"
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
            12
        )

        self.title_container = QFrame(
            self.header
        )

        self.title_container.setObjectName(
            "CardTitleContainer"
        )

        title_layout = QVBoxLayout(
            self.title_container
        )

        title_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        title_layout.setSpacing(
            3
        )

        self.title_label = QLabel(
            self._title_text,
            self.title_container,
        )

        self.title_label.setObjectName(
            "CardTitle"
        )

        self.title_label.setWordWrap(
            True
        )

        self.subtitle_label = QLabel(
            self._subtitle_text,
            self.title_container,
        )

        self.subtitle_label.setObjectName(
            "CardSubtitle"
        )

        self.subtitle_label.setWordWrap(
            True
        )

        title_layout.addWidget(
            self.title_label
        )

        title_layout.addWidget(
            self.subtitle_label
        )

        self.header_layout.addWidget(
            self.title_container,
            1,
        )

        self.action_container = QFrame(
            self.header
        )

        self.action_container.setObjectName(
            "CardActions"
        )

        self.action_layout = QHBoxLayout(
            self.action_container
        )

        self.action_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.action_layout.setSpacing(
            8
        )

        self.action_layout.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.header_layout.addWidget(
            self.action_container
        )

        self.main_layout.addWidget(
            self.header
        )

        self._update_header_visibility()

    def _create_content(
        self,
    ) -> None:
        """
        Create card content area.
        """

        self.content = QFrame(
            self
        )

        self.content.setObjectName(
            "CardContent"
        )

        self.content_layout = QVBoxLayout(
            self.content
        )

        self.content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.content_layout.setSpacing(
            10
        )

        self.main_layout.addWidget(
            self.content
        )

    # ==========================================================
    # Content API
    # ==========================================================

    def add_widget(
        self,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Add a widget to the card content area.
        """

        if alignment is None:

            self.content_layout.addWidget(
                widget,
                stretch,
            )

            return

        self.content_layout.addWidget(
            widget,
            stretch,
            alignment,
        )

    def add_layout(
        self,
        layout,
        stretch: int = 0,
    ) -> None:
        """
        Add a layout to the card content area.
        """

        self.content_layout.addLayout(
            layout,
            stretch,
        )

    def add_stretch(
        self,
        stretch: int = 1,
    ) -> None:
        """
        Add stretch to the card content area.
        """

        self.content_layout.addStretch(
            stretch
        )

    def clear_content(
        self,
    ) -> None:
        """
        Remove all widgets and nested layouts from card content.
        """

        while self.content_layout.count():

            item = self.content_layout.takeAt(
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

                self._clear_layout(
                    child_layout
                )

                child_layout.deleteLater()

    # ==========================================================
    # Header API
    # ==========================================================

    def set_title(
        self,
        title: str | None,
    ) -> None:
        """
        Update card title.
        """

        self._title_text = (
            title or ""
        )

        self.title_label.setText(
            self._title_text
        )

        self._update_header_visibility()

    def title(
        self,
    ) -> str:
        """
        Return current card title.
        """

        return self._title_text

    def set_subtitle(
        self,
        subtitle: str | None,
    ) -> None:
        """
        Update card subtitle.
        """

        self._subtitle_text = (
            subtitle or ""
        )

        self.subtitle_label.setText(
            self._subtitle_text
        )

        self._update_header_visibility()

    def subtitle(
        self,
    ) -> str:
        """
        Return current card subtitle.
        """

        return self._subtitle_text

    def add_action(
        self,
        widget: QWidget,
    ) -> None:
        """
        Add a widget to the card header action area.
        """

        self.action_layout.addWidget(
            widget
        )

        self._update_header_visibility()

    def clear_actions(
        self,
    ) -> None:
        """
        Remove all widgets from the card action area.
        """

        while self.action_layout.count():

            item = self.action_layout.takeAt(
                0
            )

            widget = item.widget()

            if widget is not None:

                widget.setParent(
                    None
                )

                widget.deleteLater()

        self._update_header_visibility()

    def set_header_visible(
        self,
        visible: bool,
    ) -> None:
        """
        Explicitly control header visibility.
        """

        self.header.setVisible(
            visible
        )

    # ==========================================================
    # Appearance API
    # ==========================================================

    def set_variant(
        self,
        variant: str,
    ) -> None:
        """
        Set visual card variant.

        Supported values:

        - default
        - elevated
        - interactive
        - danger
        - warning
        - success
        """

        normalized_variant = (
            variant.strip().casefold()
        )

        supported_variants = {
            "default",
            "elevated",
            "interactive",
            "danger",
            "warning",
            "success",
        }

        if normalized_variant not in supported_variants:

            normalized_variant = "default"

        self.setProperty(
            "variant",
            normalized_variant,
        )

        self.style().unpolish(
            self
        )

        self.style().polish(
            self
        )

        self.update()

    def set_compact(
        self,
        compact: bool,
    ) -> None:
        """
        Enable or disable compact card spacing.
        """

        self.setProperty(
            "compact",
            compact,
        )

        if compact:

            self.main_layout.setContentsMargins(
                14,
                12,
                14,
                12,
            )

            self.main_layout.setSpacing(
                10
            )

        else:

            self.main_layout.setContentsMargins(
                18,
                18,
                18,
                18,
            )

            self.main_layout.setSpacing(
                14
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

    def _update_header_visibility(
        self,
    ) -> None:
        """
        Update title, subtitle and header visibility.
        """

        has_title = bool(
            self._title_text.strip()
        )

        has_subtitle = bool(
            self._subtitle_text.strip()
        )

        has_actions = (
            self.action_layout.count() > 0
        )

        self.title_label.setVisible(
            has_title
        )

        self.subtitle_label.setVisible(
            has_subtitle
        )

        self.title_container.setVisible(
            has_title or has_subtitle
        )

        self.action_container.setVisible(
            has_actions
        )

        self.header.setVisible(
            has_title
            or has_subtitle
            or has_actions
        )

    @staticmethod
    def _clear_layout(
        layout,
    ) -> None:
        """
        Recursively clear a Qt layout.
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

                Card._clear_layout(
                    child_layout
                )

                child_layout.deleteLater()
"""
Reusable desktop section component.

Responsible for:

- grouping related page content
- displaying an optional section title
- displaying an optional section description
- providing a section actions area
- providing a reusable content layout

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


class Section(QFrame):
    """
    Reusable application page section.

    A section contains:

    - optional title
    - optional description
    - optional actions
    - reusable content area
    """

    def __init__(
        self,
        title: str | None = None,
        description: str | None = None,
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

        self.setObjectName(
            "Section"
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
        Build section structure.
        """

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
            14
        )

        self._create_header()
        self._create_content()

    def _create_header(
        self,
    ) -> None:
        """
        Create section header.
        """

        self.header = QFrame(
            self
        )

        self.header.setObjectName(
            "SectionHeader"
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
            14
        )

        self.title_container = QFrame(
            self.header
        )

        self.title_container.setObjectName(
            "SectionTitleContainer"
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
            4
        )

        self.title_label = QLabel(
            self._title_text,
            self.title_container,
        )

        self.title_label.setObjectName(
            "SectionTitle"
        )

        self.title_label.setWordWrap(
            True
        )

        self.description_label = QLabel(
            self._description_text,
            self.title_container,
        )

        self.description_label.setObjectName(
            "SectionDescription"
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

        self.header_layout.addWidget(
            self.title_container,
            1,
        )

        self.action_container = QFrame(
            self.header
        )

        self.action_container.setObjectName(
            "SectionActions"
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
            | Qt.AlignmentFlag.AlignTop
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
        Create section content area.
        """

        self.content = QFrame(
            self
        )

        self.content.setObjectName(
            "SectionContent"
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
            12
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
        Add a widget to the section content area.
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

    def insert_widget(
        self,
        index: int,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Insert a widget into the section content area.
        """

        if alignment is None:

            self.content_layout.insertWidget(
                index,
                widget,
                stretch,
            )

            return

        self.content_layout.insertWidget(
            index,
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
        Add a layout to the section content area.
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
        Add stretch to the section content area.
        """

        self.content_layout.addStretch(
            stretch
        )

    def clear_content(
        self,
    ) -> None:
        """
        Remove all widgets and nested layouts from section content.
        """

        self._clear_layout(
            self.content_layout
        )

    # ==========================================================
    # Header API
    # ==========================================================

    def set_title(
        self,
        title: str | None,
    ) -> None:
        """
        Update section title.
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
        Return current section title.
        """

        return self._title_text

    def set_description(
        self,
        description: str | None,
    ) -> None:
        """
        Update section description.
        """

        self._description_text = (
            description or ""
        )

        self.description_label.setText(
            self._description_text
        )

        self._update_header_visibility()

    def description(
        self,
    ) -> str:
        """
        Return current section description.
        """

        return self._description_text

    def add_action(
        self,
        widget: QWidget,
    ) -> None:
        """
        Add widget to section actions area.
        """

        self.action_layout.addWidget(
            widget
        )

        self._update_header_visibility()

    def clear_actions(
        self,
    ) -> None:
        """
        Remove all widgets from section actions area.
        """

        self._clear_layout(
            self.action_layout
        )

        self._update_header_visibility()

    def set_header_visible(
        self,
        visible: bool,
    ) -> None:
        """
        Explicitly control section header visibility.
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
        Set visual section variant.

        Supported values:

        - default
        - separated
        - panel
        - compact
        """

        normalized_variant = (
            variant.strip().casefold()
        )

        supported_variants = {
            "default",
            "separated",
            "panel",
            "compact",
        }

        if normalized_variant not in supported_variants:

            normalized_variant = "default"

        self.setProperty(
            "variant",
            normalized_variant,
        )

        if normalized_variant == "compact":

            self.main_layout.setSpacing(
                8
            )

            self.content_layout.setSpacing(
                8
            )

        else:

            self.main_layout.setSpacing(
                14
            )

            self.content_layout.setSpacing(
                12
            )

        self.style().unpolish(
            self
        )

        self.style().polish(
            self
        )

        self.update()

    def set_content_margins(
        self,
        left: int,
        top: int,
        right: int,
        bottom: int,
    ) -> None:
        """
        Set section content margins.
        """

        self.content_layout.setContentsMargins(
            left,
            top,
            right,
            bottom,
        )

    def set_content_spacing(
        self,
        spacing: int,
    ) -> None:
        """
        Set spacing between content items.
        """

        self.content_layout.setSpacing(
            spacing
        )

    # ==========================================================
    # Internal helpers
    # ==========================================================

    def _update_header_visibility(
        self,
    ) -> None:
        """
        Update section header visibility.
        """

        has_title = bool(
            self._title_text.strip()
        )

        has_description = bool(
            self._description_text.strip()
        )

        has_actions = (
            self.action_layout.count() > 0
        )

        self.title_label.setVisible(
            has_title
        )

        self.description_label.setVisible(
            has_description
        )

        self.title_container.setVisible(
            has_title or has_description
        )

        self.action_container.setVisible(
            has_actions
        )

        self.header.setVisible(
            has_title
            or has_description
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

                Section._clear_layout(
                    child_layout
                )

                child_layout.deleteLater()
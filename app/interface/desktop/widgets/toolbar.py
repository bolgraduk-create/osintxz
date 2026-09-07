"""
Reusable desktop toolbar component.

Responsible for:

- grouping page controls
- displaying primary and secondary actions
- hosting search and filter widgets
- supporting left, center and right content areas
- providing consistent spacing and appearance

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
    QSizePolicy,
    QSpacerItem,
    QWidget,
)


class Toolbar(QFrame):
    """
    Reusable application toolbar.

    The toolbar contains three logical areas:

    - left area
    - center area
    - right area

    Typical usage:

    - title or search on the left
    - filters in the center
    - actions on the right
    """

    SUPPORTED_VARIANTS = {
        "default",
        "panel",
        "transparent",
        "compact",
    }

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._variant = "default"

        self.setObjectName(
            "Toolbar"
        )

        self.setProperty(
            "variant",
            self._variant,
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._setup_ui()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Build toolbar structure.
        """

        self.main_layout = QHBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            12,
            10,
            12,
            10,
        )

        self.main_layout.setSpacing(
            12
        )

        self._create_left_area()
        self._create_center_area()
        self._create_right_area()

        self._update_area_visibility()

    def _create_left_area(
        self,
    ) -> None:
        """
        Create left toolbar area.
        """

        self.left_container = QFrame(
            self
        )

        self.left_container.setObjectName(
            "ToolbarLeft"
        )

        self.left_layout = QHBoxLayout(
            self.left_container
        )

        self.left_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.left_layout.setSpacing(
            8
        )

        self.left_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.main_layout.addWidget(
            self.left_container,
        )

    def _create_center_area(
        self,
    ) -> None:
        """
        Create center toolbar area.
        """

        self.center_container = QFrame(
            self
        )

        self.center_container.setObjectName(
            "ToolbarCenter"
        )

        self.center_layout = QHBoxLayout(
            self.center_container
        )

        self.center_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.center_layout.setSpacing(
            8
        )

        self.center_layout.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.main_layout.addWidget(
            self.center_container,
            1,
        )

    def _create_right_area(
        self,
    ) -> None:
        """
        Create right toolbar area.
        """

        self.right_container = QFrame(
            self
        )

        self.right_container.setObjectName(
            "ToolbarRight"
        )

        self.right_layout = QHBoxLayout(
            self.right_container
        )

        self.right_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.right_layout.setSpacing(
            8
        )

        self.right_layout.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.main_layout.addWidget(
            self.right_container,
        )

    # ==========================================================
    # Left area API
    # ==========================================================

    def add_left_widget(
        self,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Add widget to left toolbar area.
        """

        self._add_widget(
            layout=self.left_layout,
            widget=widget,
            stretch=stretch,
            alignment=alignment,
        )

        self._update_area_visibility()

    def insert_left_widget(
        self,
        index: int,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Insert widget into left toolbar area.
        """

        self._insert_widget(
            layout=self.left_layout,
            index=index,
            widget=widget,
            stretch=stretch,
            alignment=alignment,
        )

        self._update_area_visibility()

    def add_left_spacing(
        self,
        spacing: int,
    ) -> None:
        """
        Add fixed spacing to left toolbar area.
        """

        self.left_layout.addSpacing(
            spacing
        )

        self._update_area_visibility()

    def add_left_stretch(
        self,
        stretch: int = 1,
    ) -> None:
        """
        Add stretch to left toolbar area.
        """

        self.left_layout.addStretch(
            stretch
        )

        self._update_area_visibility()

    def clear_left(
        self,
    ) -> None:
        """
        Clear left toolbar area.
        """

        self._clear_layout(
            self.left_layout
        )

        self._update_area_visibility()

    # ==========================================================
    # Center area API
    # ==========================================================

    def add_center_widget(
        self,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Add widget to center toolbar area.
        """

        self._add_widget(
            layout=self.center_layout,
            widget=widget,
            stretch=stretch,
            alignment=alignment,
        )

        self._update_area_visibility()

    def insert_center_widget(
        self,
        index: int,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Insert widget into center toolbar area.
        """

        self._insert_widget(
            layout=self.center_layout,
            index=index,
            widget=widget,
            stretch=stretch,
            alignment=alignment,
        )

        self._update_area_visibility()

    def add_center_spacing(
        self,
        spacing: int,
    ) -> None:
        """
        Add fixed spacing to center toolbar area.
        """

        self.center_layout.addSpacing(
            spacing
        )

        self._update_area_visibility()

    def add_center_stretch(
        self,
        stretch: int = 1,
    ) -> None:
        """
        Add stretch to center toolbar area.
        """

        self.center_layout.addStretch(
            stretch
        )

        self._update_area_visibility()

    def clear_center(
        self,
    ) -> None:
        """
        Clear center toolbar area.
        """

        self._clear_layout(
            self.center_layout
        )

        self._update_area_visibility()

    # ==========================================================
    # Right area API
    # ==========================================================

    def add_right_widget(
        self,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Add widget to right toolbar area.
        """

        self._add_widget(
            layout=self.right_layout,
            widget=widget,
            stretch=stretch,
            alignment=alignment,
        )

        self._update_area_visibility()

    def insert_right_widget(
        self,
        index: int,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Insert widget into right toolbar area.
        """

        self._insert_widget(
            layout=self.right_layout,
            index=index,
            widget=widget,
            stretch=stretch,
            alignment=alignment,
        )

        self._update_area_visibility()

    def add_right_spacing(
        self,
        spacing: int,
    ) -> None:
        """
        Add fixed spacing to right toolbar area.
        """

        self.right_layout.addSpacing(
            spacing
        )

        self._update_area_visibility()

    def add_right_stretch(
        self,
        stretch: int = 1,
    ) -> None:
        """
        Add stretch to right toolbar area.
        """

        self.right_layout.addStretch(
            stretch
        )

        self._update_area_visibility()

    def clear_right(
        self,
    ) -> None:
        """
        Clear right toolbar area.
        """

        self._clear_layout(
            self.right_layout
        )

        self._update_area_visibility()

    # ==========================================================
    # General content API
    # ==========================================================

    def clear(
        self,
    ) -> None:
        """
        Clear all toolbar areas.
        """

        self._clear_layout(
            self.left_layout
        )

        self._clear_layout(
            self.center_layout
        )

        self._clear_layout(
            self.right_layout
        )

        self._update_area_visibility()

    def add_separator(
        self,
        area: str = "right",
    ) -> QFrame:
        """
        Add a vertical separator to a toolbar area.

        Supported areas:

        - left
        - center
        - right
        """

        separator = QFrame(
            self
        )

        separator.setObjectName(
            "ToolbarSeparator"
        )

        separator.setFrameShape(
            QFrame.Shape.VLine
        )

        separator.setFrameShadow(
            QFrame.Shadow.Plain
        )

        separator.setFixedWidth(
            1
        )

        normalized_area = (
            area or "right"
        ).strip().casefold()

        if normalized_area == "left":

            self.add_left_widget(
                separator
            )

        elif normalized_area == "center":

            self.add_center_widget(
                separator
            )

        else:

            self.add_right_widget(
                separator
            )

        return separator

    # ==========================================================
    # Appearance API
    # ==========================================================

    def set_variant(
        self,
        variant: str,
    ) -> None:
        """
        Set toolbar visual variant.

        Supported values:

        - default
        - panel
        - transparent
        - compact
        """

        normalized_variant = (
            variant or "default"
        ).strip().casefold()

        if normalized_variant not in self.SUPPORTED_VARIANTS:

            normalized_variant = "default"

        self._variant = normalized_variant

        self.setProperty(
            "variant",
            self._variant,
        )

        if self._variant == "compact":

            self.main_layout.setContentsMargins(
                8,
                6,
                8,
                6,
            )

            self.main_layout.setSpacing(
                8
            )

            self.left_layout.setSpacing(
                6
            )

            self.center_layout.setSpacing(
                6
            )

            self.right_layout.setSpacing(
                6
            )

        else:

            self.main_layout.setContentsMargins(
                12,
                10,
                12,
                10,
            )

            self.main_layout.setSpacing(
                12
            )

            self.left_layout.setSpacing(
                8
            )

            self.center_layout.setSpacing(
                8
            )

            self.right_layout.setSpacing(
                8
            )

        self._refresh_style()

    def variant(
        self,
    ) -> str:
        """
        Return current toolbar variant.
        """

        return self._variant

    def set_toolbar_margins(
        self,
        left: int,
        top: int,
        right: int,
        bottom: int,
    ) -> None:
        """
        Set toolbar content margins.
        """

        self.main_layout.setContentsMargins(
            left,
            top,
            right,
            bottom,
        )

    def set_toolbar_spacing(
        self,
        spacing: int,
    ) -> None:
        """
        Set spacing between toolbar areas.
        """

        self.main_layout.setSpacing(
            spacing
        )

    def set_area_spacing(
        self,
        spacing: int,
    ) -> None:
        """
        Set spacing inside all toolbar areas.
        """

        self.left_layout.setSpacing(
            spacing
        )

        self.center_layout.setSpacing(
            spacing
        )

        self.right_layout.setSpacing(
            spacing
        )

    # ==========================================================
    # Internal helpers
    # ==========================================================

    def _update_area_visibility(
        self,
    ) -> None:
        """
        Hide toolbar areas that contain no items.
        """

        self.left_container.setVisible(
            self.left_layout.count() > 0
        )

        self.center_container.setVisible(
            self.center_layout.count() > 0
        )

        self.right_container.setVisible(
            self.right_layout.count() > 0
        )

    def _refresh_style(
        self,
    ) -> None:
        """
        Reapply QSS after dynamic property changes.
        """

        style = self.style()

        if style is None:

            return

        style.unpolish(
            self
        )

        style.polish(
            self
        )

        self.updateGeometry()
        self.update()

    @staticmethod
    def _add_widget(
        layout: QHBoxLayout,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Add widget to the supplied layout.
        """

        if alignment is None:

            layout.addWidget(
                widget,
                stretch,
            )

            return

        layout.addWidget(
            widget,
            stretch,
            alignment,
        )

    @staticmethod
    def _insert_widget(
        layout: QHBoxLayout,
        index: int,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Insert widget into the supplied layout.
        """

        if alignment is None:

            layout.insertWidget(
                index,
                widget,
                stretch,
            )

            return

        layout.insertWidget(
            index,
            widget,
            stretch,
            alignment,
        )

    @staticmethod
    def _clear_layout(
        layout: QHBoxLayout,
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

                Toolbar._clear_nested_layout(
                    child_layout
                )

                child_layout.deleteLater()

            spacer = item.spacerItem()

            if isinstance(
                spacer,
                QSpacerItem,
            ):

                continue

    @staticmethod
    def _clear_nested_layout(
        layout,
    ) -> None:
        """
        Recursively clear any nested layout.
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

                Toolbar._clear_nested_layout(
                    child_layout
                )

                child_layout.deleteLater()
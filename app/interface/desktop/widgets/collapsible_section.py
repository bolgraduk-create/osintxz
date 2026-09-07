"""
Collapsible section widget.

Responsible for:

- displaying a section header
- expanding and collapsing section content
- displaying an optional subtitle
- emitting expansion state changes
- containing arbitrary child widgets

Does NOT:

- contain application business logic
- access database
- manage page state
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CollapsibleSection(
    QFrame,
):
    """
    Reusable expandable and collapsible interface section.

    The component contains:

    - a clickable title button;
    - an optional subtitle;
    - a content container;
    - an expansion-state signal.
    """

    expanded_changed = Signal(
        bool
    )

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        *,
        expanded: bool = True,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._expanded = bool(
            expanded
        )

        self._setup_ui()

        self.set_title(
            title
        )

        self.set_subtitle(
            subtitle
        )

        self.set_expanded(
            self._expanded,
            emit_signal=False,
        )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create collapsible section interface.
        """

        self.setObjectName(
            "CollapsibleSection"
        )

        self.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self.root_layout = QVBoxLayout(
            self
        )

        self.root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.root_layout.setSpacing(
            0
        )

        self._create_header()
        self._create_content()

    def _create_header(
        self,
    ) -> None:
        """
        Create section header.
        """

        self.header_container = QFrame(
            self
        )

        self.header_container.setObjectName(
            "CollapsibleSectionHeaderContainer"
        )

        self.header_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self.header_layout = QVBoxLayout(
            self.header_container
        )

        self.header_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.header_layout.setSpacing(
            0
        )

        self.header_button = QToolButton(
            self.header_container
        )

        self.header_button.setObjectName(
            "CollapsibleSectionHeader"
        )

        self.header_button.setCheckable(
            True
        )

        self.header_button.setAutoRaise(
            False
        )

        self.header_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )

        self.header_button.setArrowType(
            Qt.ArrowType.RightArrow
        )

        self.header_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.header_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.header_button.setMinimumHeight(
            38
        )

        self.header_button.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        self.header_button.clicked.connect(
            self.toggle
        )

        self.subtitle_label = QLabel(
            self.header_container
        )

        self.subtitle_label.setObjectName(
            "CollapsibleSectionSubtitle"
        )

        self.subtitle_label.setWordWrap(
            True
        )

        self.subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.subtitle_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )

        self.subtitle_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.subtitle_label.setContentsMargins(
            30,
            2,
            14,
            8,
        )

        self.header_layout.addWidget(
            self.header_button
        )

        self.header_layout.addWidget(
            self.subtitle_label
        )

        self.root_layout.addWidget(
            self.header_container
        )

    def _create_content(
        self,
    ) -> None:
        """
        Create section content container.
        """

        self.content_container = QFrame(
            self
        )

        self.content_container.setObjectName(
            "CollapsibleSectionContent"
        )

        self.content_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self.content_layout = QVBoxLayout(
            self.content_container
        )

        self.content_layout.setContentsMargins(
            14,
            12,
            14,
            14,
        )

        self.content_layout.setSpacing(
            10
        )

        self.root_layout.addWidget(
            self.content_container
        )

    # ==========================================================
    # Text
    # ==========================================================

    def set_title(
        self,
        title: str,
    ) -> None:
        """
        Set section title.
        """

        self.header_button.setText(
            str(
                title
            )
        )

        self.header_button.updateGeometry()
        self.header_container.updateGeometry()
        self.updateGeometry()

    def title(
        self,
    ) -> str:
        """
        Return section title.
        """

        return self.header_button.text()

    def set_subtitle(
        self,
        subtitle: str,
    ) -> None:
        """
        Set optional section subtitle.
        """

        normalized_subtitle = str(
            subtitle
        )

        has_subtitle = bool(
            normalized_subtitle.strip()
        )

        self.subtitle_label.setText(
            normalized_subtitle
        )

        self.subtitle_label.setVisible(
            has_subtitle
        )

        self.header_container.updateGeometry()
        self.updateGeometry()

    def subtitle(
        self,
    ) -> str:
        """
        Return section subtitle.
        """

        return self.subtitle_label.text()

    # ==========================================================
    # Content
    # ==========================================================

    def add_widget(
        self,
        widget: QWidget,
        stretch: int = 0,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> None:
        """
        Add widget to section content.
        """

        if not isinstance(
            widget,
            QWidget,
        ):
            raise TypeError(
                "widget must be a QWidget"
            )

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
        Add layout to section content.
        """

        self.content_layout.addLayout(
            layout,
            stretch,
        )

    def set_content_margins(
        self,
        left: int,
        top: int,
        right: int,
        bottom: int,
    ) -> None:
        """
        Set content layout margins.
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
        Set spacing between content widgets.
        """

        self.content_layout.setSpacing(
            spacing
        )

    # ==========================================================
    # Expansion
    # ==========================================================

    def is_expanded(
        self,
    ) -> bool:
        """
        Return current expansion state.
        """

        return self._expanded

    def set_expanded(
        self,
        expanded: bool,
        *,
        emit_signal: bool = True,
    ) -> None:
        """
        Set section expansion state.
        """

        normalized_expanded = bool(
            expanded
        )

        state_changed = (
            normalized_expanded
            != self._expanded
        )

        self._expanded = (
            normalized_expanded
        )

        self.header_button.blockSignals(
            True
        )

        self.header_button.setChecked(
            self._expanded
        )

        self.header_button.blockSignals(
            False
        )

        self.header_button.setArrowType(
            (
                Qt.ArrowType.DownArrow
                if self._expanded
                else Qt.ArrowType.RightArrow
            )
        )

        self.content_container.setVisible(
            self._expanded
        )

        self.header_button.setProperty(
            "expanded",
            self._expanded,
        )

        style = self.header_button.style()

        style.unpolish(
            self.header_button
        )

        style.polish(
            self.header_button
        )

        self.header_button.update()
        self.header_container.updateGeometry()
        self.updateGeometry()

        if (
            state_changed
            and emit_signal
        ):

            self.expanded_changed.emit(
                self._expanded
            )

    def expand(
        self,
    ) -> None:
        """
        Expand section.
        """

        self.set_expanded(
            True
        )

    def collapse(
        self,
    ) -> None:
        """
        Collapse section.
        """

        self.set_expanded(
            False
        )

    def toggle(
        self,
        *_,
    ) -> None:
        """
        Toggle section expansion state.
        """

        self.set_expanded(
            not self._expanded
        )
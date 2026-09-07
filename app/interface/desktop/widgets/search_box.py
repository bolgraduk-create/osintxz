"""
Reusable desktop search box component.

Responsible for:

- displaying a consistent search input
- emitting search text changes
- emitting submitted search queries
- supporting delayed search with debounce
- providing clear and busy states
- exposing a stable public API

Does NOT:

- perform searches
- access controllers
- access repositories
- load application data
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QObject,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QKeyEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class SearchBox(QFrame):
    """
    Reusable application search box.

    Signals:

    - search_changed:
        emitted after debounce delay

    - text_changed:
        emitted immediately when text changes

    - search_submitted:
        emitted when Enter or Return is pressed

    - cleared:
        emitted when the search field is cleared
    """

    search_changed = Signal(
        str
    )

    text_changed = Signal(
        str
    )

    search_submitted = Signal(
        str
    )

    cleared = Signal()

    def __init__(
        self,
        placeholder: str = "Search...",
        debounce_interval: int = 250,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._placeholder = (
            placeholder or "Search..."
        )

        self._debounce_interval = max(
            0,
            debounce_interval,
        )

        self._busy = False

        self.setObjectName(
            "SearchBox"
        )

        self.setProperty(
            "focused",
            False,
        )

        self.setProperty(
            "busy",
            False,
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._setup_timer()
        self._setup_ui()
        self._connect_signals()
        self._update_state()

    # ==========================================================
    # Setup
    # ==========================================================

    def _setup_timer(
        self,
    ) -> None:
        """
        Create debounce timer.
        """

        self._debounce_timer = QTimer(
            self
        )

        self._debounce_timer.setSingleShot(
            True
        )

        self._debounce_timer.setInterval(
            self._debounce_interval
        )

        self._debounce_timer.timeout.connect(
            self._emit_debounced_search
        )

    def _setup_ui(
        self,
    ) -> None:
        """
        Build search box structure.
        """

        self.main_layout = QHBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            12,
            0,
            8,
            0,
        )

        self.main_layout.setSpacing(
            8
        )

        self.search_marker = QLabel(
            "⌕",
            self,
        )

        self.search_marker.setObjectName(
            "SearchBoxMarker"
        )

        self.search_marker.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.search_marker.setFixedWidth(
            20
        )

        self.input = QLineEdit(
            self
        )

        self.input.setObjectName(
            "SearchBoxInput"
        )

        self.input.setPlaceholderText(
            self._placeholder
        )

        self.input.setClearButtonEnabled(
            False
        )

        self.input.setFrame(
            False
        )

        self.input.installEventFilter(
            self
        )

        self.busy_label = QLabel(
            "…",
            self,
        )

        self.busy_label.setObjectName(
            "SearchBoxBusy"
        )

        self.busy_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.busy_label.setFixedWidth(
            22
        )

        self.clear_button = QPushButton(
            "×",
            self,
        )

        self.clear_button.setObjectName(
            "SearchBoxClearButton"
        )

        self.clear_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.clear_button.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )

        self.clear_button.setFixedSize(
            26,
            26,
        )

        self.clear_button.setToolTip(
            "Clear search"
        )

        self.main_layout.addWidget(
            self.search_marker
        )

        self.main_layout.addWidget(
            self.input,
            1,
        )

        self.main_layout.addWidget(
            self.busy_label
        )

        self.main_layout.addWidget(
            self.clear_button
        )

    def _connect_signals(
        self,
    ) -> None:
        """
        Connect internal widget signals.
        """

        self.input.textChanged.connect(
            self._handle_text_changed
        )

        self.input.returnPressed.connect(
            self._handle_search_submitted
        )

        self.clear_button.clicked.connect(
            self.clear
        )

    # ==========================================================
    # Text API
    # ==========================================================

    def text(
        self,
    ) -> str:
        """
        Return current search text.
        """

        return self.input.text()

    def set_text(
        self,
        text: str | None,
        emit_search: bool = False,
    ) -> None:
        """
        Set search text.

        When emit_search is False, the debounce timer is stopped
        after the value is assigned.
        """

        normalized_text = (
            text or ""
        )

        self.input.setText(
            normalized_text
        )

        if not emit_search:

            self._debounce_timer.stop()

    def clear(
        self,
    ) -> None:
        """
        Clear search input.
        """

        had_text = bool(
            self.input.text()
        )

        self._debounce_timer.stop()

        self.input.clear()

        if had_text:

            self.cleared.emit()

    def set_placeholder(
        self,
        placeholder: str | None,
    ) -> None:
        """
        Update placeholder text.
        """

        self._placeholder = (
            placeholder or ""
        )

        self.input.setPlaceholderText(
            self._placeholder
        )

    def placeholder(
        self,
    ) -> str:
        """
        Return current placeholder text.
        """

        return self._placeholder

    def select_all(
        self,
    ) -> None:
        """
        Select all search text.
        """

        self.input.selectAll()

    # ==========================================================
    # Search API
    # ==========================================================

    def submit(
        self,
    ) -> None:
        """
        Submit current search query programmatically.
        """

        self._debounce_timer.stop()

        query = self.input.text().strip()

        self.search_submitted.emit(
            query
        )

    def set_debounce_interval(
        self,
        interval: int,
    ) -> None:
        """
        Set debounce delay in milliseconds.
        """

        self._debounce_interval = max(
            0,
            interval,
        )

        self._debounce_timer.setInterval(
            self._debounce_interval
        )

    def debounce_interval(
        self,
    ) -> int:
        """
        Return current debounce interval.
        """

        return self._debounce_interval

    # ==========================================================
    # State API
    # ==========================================================

    def set_busy(
        self,
        busy: bool,
    ) -> None:
        """
        Enable or disable busy state.
        """

        self._busy = bool(
            busy
        )

        self.setProperty(
            "busy",
            self._busy,
        )

        self._update_state()
        self._refresh_style()

    def is_busy(
        self,
    ) -> bool:
        """
        Return whether busy state is enabled.
        """

        return self._busy

    def set_enabled(
        self,
        enabled: bool,
    ) -> None:
        """
        Enable or disable the complete search box.
        """

        self.setEnabled(
            enabled
        )

        self.input.setEnabled(
            enabled
        )

        self.clear_button.setEnabled(
            enabled
        )

        self._update_state()

    def focus_search(
        self,
    ) -> None:
        """
        Focus the search input.
        """

        self.input.setFocus(
            Qt.FocusReason.ShortcutFocusReason
        )

    # ==========================================================
    # Qt overrides
    # ==========================================================

    def eventFilter(
        self,
        watched: QObject,
        event: QEvent,
    ) -> bool:
        """
        Track focus and keyboard events from the input.
        """

        if watched is self.input:

            if event.type() == QEvent.Type.FocusIn:

                self.setProperty(
                    "focused",
                    True,
                )

                self._refresh_style()

            elif event.type() == QEvent.Type.FocusOut:

                self.setProperty(
                    "focused",
                    False,
                )

                self._refresh_style()

            elif event.type() == QEvent.Type.KeyPress:

                key_event = event

                if isinstance(
                    key_event,
                    QKeyEvent,
                ):

                    if (
                        key_event.key()
                        == Qt.Key.Key_Escape
                    ):

                        if self.input.text():

                            self.clear()

                            return True

                        self.clearFocus()

                        return True

        return super().eventFilter(
            watched,
            event,
        )

    def mousePressEvent(
        self,
        event,
    ) -> None:
        """
        Focus input when clicking anywhere inside the component.
        """

        if self.isEnabled():

            self.focus_search()

        super().mousePressEvent(
            event
        )

    # ==========================================================
    # Internal handlers
    # ==========================================================

    def _handle_text_changed(
        self,
        text: str,
    ) -> None:
        """
        Handle immediate input changes.
        """

        self.text_changed.emit(
            text
        )

        self._update_state()

        if self._debounce_interval == 0:

            self.search_changed.emit(
                text.strip()
            )

            return

        self._debounce_timer.start()

    def _handle_search_submitted(
        self,
    ) -> None:
        """
        Handle Enter or Return.
        """

        self.submit()

    def _emit_debounced_search(
        self,
    ) -> None:
        """
        Emit delayed search query.
        """

        self.search_changed.emit(
            self.input.text().strip()
        )

    # ==========================================================
    # Internal helpers
    # ==========================================================

    def _update_state(
        self,
    ) -> None:
        """
        Update visibility of state controls.
        """

        has_text = bool(
            self.input.text()
        )

        self.busy_label.setVisible(
            self._busy
        )

        self.clear_button.setVisible(
            has_text and not self._busy
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

        self.update()
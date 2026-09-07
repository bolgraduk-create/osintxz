"""
Message workspace view.

Responsible for:

- displaying imported messages
- filtering messages
- showing message details
- providing a virtualized message table
- displaying message workspace states
- reacting to application language changes

Does NOT:

- access database
- execute business logic
- perform analysis
"""


from __future__ import annotations

import re

from PySide6.QtGui import (
    QAction,
    QGuiApplication,
)

from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QDate,
    QModelIndex,
    Qt,
    QSortFilterProxyModel,
    Signal,
)

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QMenu,
)

from app.interface.desktop.localization import (
    TranslatableMixin,
)

from app.localization import (
    TranslationManager,
    get_translation_manager,
)

from app.interface.desktop.widgets import (
    CollapsibleSection,
)



from app.interface.desktop.widgets import (
    Badge,
    Card,
    EmptyState,
    SearchBox,
    Section,
    Toolbar,
)


class MessageTableModel(
    QAbstractTableModel
):
    """
    Table model for investigation messages.

    QTableView requests only visible rows, so large message
    collections can be displayed without creating one widget
    for every message.
    """

    DEFAULT_HEADERS = [
        "Date",
        "Sender",
        "Receiver",
        "Chat",
        "Message",
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._messages: list[
            dict[str, Any]
        ] = []

        self._headers = list(
            self.DEFAULT_HEADERS
        )

    # ==========================================================
    # Data
    # ==========================================================

    def set_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> None:
        """
        Replace all displayed messages.
        """

        normalized_messages = [
            message
            for message in messages
            if isinstance(
                message,
                dict,
            )
        ]

        self.beginResetModel()

        self._messages = normalized_messages

        self.endResetModel()

    def clear(
        self,
    ) -> None:
        """
        Remove all messages.
        """

        self.set_messages(
            []
        )

    def get_message(
        self,
        row: int,
    ) -> dict[str, Any] | None:
        """
        Return a message by source row.
        """

        if row < 0:

            return None

        if row >= len(
            self._messages
        ):

            return None

        return self._messages[
            row
        ]

    def set_headers(
        self,
        headers: list[str],
    ) -> None:
        """
        Replace horizontal table headers.
        """

        normalized_headers = [
            str(header)
            for header in headers
        ]

        if (
            len(normalized_headers)
            != len(self.DEFAULT_HEADERS)
        ):

            normalized_headers = list(
                self.DEFAULT_HEADERS
            )

        self._headers = normalized_headers

        self.headerDataChanged.emit(
            Qt.Orientation.Horizontal,
            0,
            len(self._headers) - 1,
        )

    # ==========================================================
    # Qt model implementation
    # ==========================================================

    def rowCount(
        self,
        parent: QModelIndex = QModelIndex(),
    ) -> int:

        if parent.isValid():

            return 0

        return len(
            self._messages
        )

    def columnCount(
        self,
        parent: QModelIndex = QModelIndex(),
    ) -> int:

        if parent.isValid():

            return 0

        return len(
            self._headers
        )

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:

        if not index.isValid():

            return None

        message = self.get_message(
            index.row()
        )

        if message is None:

            return None

        column = index.column()

        value = self._get_column_value(
            message=message,
            column=column,
        )

        if role == Qt.ItemDataRole.DisplayRole:

            if column == 4:

                return self._compact_text(
                    value
                )

            return value

        if role == Qt.ItemDataRole.ToolTipRole:

            if column == 4:

                return value

            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:

            return (
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            )

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:

        if role != Qt.ItemDataRole.DisplayRole:

            return None

        if (
            orientation
            == Qt.Orientation.Horizontal
        ):

            if (
                0
                <= section
                < len(self._headers)
            ):

                return self._headers[
                    section
                ]

            return None

        return section + 1

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _get_column_value(
        message: dict[str, Any],
        column: int,
    ) -> str:
        """
        Extract visible value for a table column.
        """

        if column == 0:

            return (
                MessageTableModel
                ._format_date(
                    message.get(
                        "sent_at"
                    )
                )
            )

        if column == 1:

            return str(
                message.get(
                    "sender"
                )
                or ""
            )

        if column == 2:

            return str(
                message.get(
                    "receiver"
                )
                or ""
            )

        if column == 3:

            return str(
                message.get(
                    "chat_name"
                )
                or ""
            )

        if column == 4:

            return str(
                message.get(
                    "text"
                )
                or ""
            )

        return ""

    @staticmethod
    def _format_date(
        value: Any,
    ) -> str:
        """
        Make an ISO timestamp easier to read.
        """

        if value is None:

            return ""

        text = str(
            value
        ).replace(
            "T",
            " ",
        )

        if text.endswith(
            "Z"
        ):

            text = text[
                :-1
            ]

        date_part, separator, time_part = (
            text.partition(
                " "
            )
        )

        if separator:

            if "+" in time_part:

                time_part = time_part.split(
                    "+",
                    maxsplit=1,
                )[0]

            return (
                f"{date_part} {time_part}"
            ).strip()

        return text

    @staticmethod
    def _compact_text(
        value: str,
    ) -> str:
        """
        Prepare message text for one table row.
        """

        compact = " ".join(
            value.split()
        )

        maximum_length = 180

        if len(
            compact
        ) <= maximum_length:

            return compact

        return (
            compact[
                :maximum_length
            ]
            + "..."
        )


class MessageFilterProxyModel(
    QSortFilterProxyModel
):
    """
    Multi-criteria filter for investigation messages.

    Supports:

    - general text search
    - sender filtering
    - receiver filtering
    - chat filtering
    - date range filtering
    - case-sensitive search
    - regular expressions
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._search_text = ""

        self._sender: str | None = None
        self._receiver: str | None = None
        self._chat: str | None = None

        self._date_from: QDate | None = None
        self._date_to: QDate | None = None

        self._case_sensitive = False
        self._regex = False

        self.setDynamicSortFilter(
            True
        )

        self.setFilterCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )

    # ==========================================================
    # Search text
    # ==========================================================

    def set_search_text(
        self,
        text: str,
    ) -> None:
        """
        Update the general search query.

        The original text is preserved because case-sensitive
        and regular-expression modes may require it.
        """

        normalized_text = str(
            text or ""
        ).strip()

        if normalized_text == self._search_text:

            return

        self._search_text = normalized_text

        self.invalidateFilter()

    def search_text(
        self,
    ) -> str:
        """
        Return the current search query.
        """

        return self._search_text

    # ==========================================================
    # Participant and chat filters
    # ==========================================================

    def set_sender_filter(
        self,
        sender: str | None,
    ) -> None:
        """
        Filter messages by sender.
        """

        normalized_sender = self._normalize_optional_text(
            sender
        )

        if normalized_sender == self._sender:

            return

        self._sender = normalized_sender

        self.invalidateFilter()

    def set_receiver_filter(
        self,
        receiver: str | None,
    ) -> None:
        """
        Filter messages by receiver.
        """

        normalized_receiver = self._normalize_optional_text(
            receiver
        )

        if normalized_receiver == self._receiver:

            return

        self._receiver = normalized_receiver

        self.invalidateFilter()

    def set_chat_filter(
        self,
        chat: str | None,
    ) -> None:
        """
        Filter messages by chat.
        """

        normalized_chat = self._normalize_optional_text(
            chat
        )

        if normalized_chat == self._chat:

            return

        self._chat = normalized_chat

        self.invalidateFilter()

    # ==========================================================
    # Date filters
    # ==========================================================

    def set_date_from(
        self,
        value: QDate | None,
    ) -> None:
        """
        Set inclusive lower date boundary.

        The UI uses 1970-01-01 as the special "Any date" value.
        """

        normalized_date = self._normalize_filter_date(
            value
        )

        if normalized_date == self._date_from:

            return

        self._date_from = normalized_date

        self.invalidateFilter()

    def set_date_to(
        self,
        value: QDate | None,
    ) -> None:
        """
        Set inclusive upper date boundary.

        The UI uses 1970-01-01 as the special "Any date" value.
        """

        normalized_date = self._normalize_filter_date(
            value
        )

        if normalized_date == self._date_to:

            return

        self._date_to = normalized_date

        self.invalidateFilter()

    # ==========================================================
    # Search modes
    # ==========================================================

    def set_case_sensitive(
        self,
        enabled: bool,
    ) -> None:
        """
        Enable or disable case-sensitive matching.
        """

        normalized_enabled = bool(
            enabled
        )

        if normalized_enabled == self._case_sensitive:

            return

        self._case_sensitive = normalized_enabled

        self.setFilterCaseSensitivity(
            (
                Qt.CaseSensitivity.CaseSensitive
                if self._case_sensitive
                else Qt.CaseSensitivity.CaseInsensitive
            )
        )

        self.invalidateFilter()

    def set_regex(
        self,
        enabled: bool,
    ) -> None:
        """
        Enable or disable regular-expression search.
        """

        normalized_enabled = bool(
            enabled
        )

        if normalized_enabled == self._regex:

            return

        self._regex = normalized_enabled

        self.invalidateFilter()

    # ==========================================================
    # State
    # ==========================================================

    def has_active_filters(
        self,
    ) -> bool:
        """
        Return whether any search or filter is active.
        """

        return any(
            (
                bool(
                    self._search_text
                ),
                self._sender is not None,
                self._receiver is not None,
                self._chat is not None,
                self._date_from is not None,
                self._date_to is not None,
            )
        )

    def clear_filters(
        self,
    ) -> None:
        """
        Clear all filter state.
        """

        self._search_text = ""

        self._sender = None
        self._receiver = None
        self._chat = None

        self._date_from = None
        self._date_to = None

        self._case_sensitive = False
        self._regex = False

        self.setFilterCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )

        self.invalidateFilter()

    # ==========================================================
    # Qt filtering
    # ==========================================================

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex,
    ) -> bool:
        """
        Return whether a source message satisfies every active
        filter.
        """

        del source_parent

        source_model = self.sourceModel()

        if not isinstance(
            source_model,
            MessageTableModel,
        ):

            return True

        message = source_model.get_message(
            source_row
        )

        if message is None:

            return False

        if not self._matches_exact_filter(
            value=message.get(
                "sender"
            ),
            expected=self._sender,
        ):

            return False

        if not self._matches_exact_filter(
            value=message.get(
                "receiver"
            ),
            expected=self._receiver,
        ):

            return False

        if not self._matches_exact_filter(
            value=message.get(
                "chat_name"
            ),
            expected=self._chat,
        ):

            return False

        if not self._matches_date_range(
            message.get(
                "sent_at"
            )
        ):

            return False

        if not self._matches_search(
            message
        ):

            return False

        return True

    # ==========================================================
    # Matching helpers
    # ==========================================================

    def _matches_exact_filter(
        self,
        value: Any,
        expected: str | None,
    ) -> bool:
        """
        Match a value against an optional exact filter.
        """

        if expected is None:

            return True

        actual_text = str(
            value or ""
        ).strip()

        if self._case_sensitive:

            return actual_text == expected

        return (
            actual_text.casefold()
            == expected.casefold()
        )

    def _matches_date_range(
        self,
        value: Any,
    ) -> bool:
        """
        Match a message timestamp against the active date range.
        """

        if (
            self._date_from is None
            and self._date_to is None
        ):

            return True

        message_date = self._parse_message_date(
            value
        )

        if message_date is None:

            return False

        if (
            self._date_from is not None
            and message_date < self._date_from
        ):

            return False

        if (
            self._date_to is not None
            and message_date > self._date_to
        ):

            return False

        return True

    def _matches_search(
        self,
        message: dict[str, Any],
    ) -> bool:
        """
        Match the general query against all searchable fields.
        """

        if not self._search_text:

            return True

        searchable_values = (
            message.get(
                "sent_at"
            ),
            message.get(
                "sender"
            ),
            message.get(
                "receiver"
            ),
            message.get(
                "chat_name"
            ),
            message.get(
                "text"
            ),
            message.get(
                "external_id"
            ),
        )

        combined_text = " ".join(
            str(
                value
            )
            for value in searchable_values
            if value is not None
        )

        if self._regex:

            flags = (
                0
                if self._case_sensitive
                else re.IGNORECASE
            )

            try:

                return (
                    re.search(
                        self._search_text,
                        combined_text,
                        flags,
                    )
                    is not None
                )

            except re.error:

                return False

        if self._case_sensitive:

            return (
                self._search_text
                in combined_text
            )

        return (
            self._search_text.casefold()
            in combined_text.casefold()
        )

    # ==========================================================
    # Normalization helpers
    # ==========================================================

    @staticmethod
    def _normalize_optional_text(
        value: str | None,
    ) -> str | None:
        """
        Normalize an optional text filter.
        """

        if not isinstance(
            value,
            str,
        ):

            return None

        normalized_value = value.strip()

        if not normalized_value:

            return None

        return normalized_value

    @staticmethod
    def _normalize_filter_date(
        value: QDate | None,
    ) -> QDate | None:
        """
        Normalize a date-filter value.

        1970-01-01 is the special value used by the UI to mean
        that no date boundary is selected.
        """

        if not isinstance(
            value,
            QDate,
        ):

            return None

        if not value.isValid():

            return None

        if value == QDate(
            1970,
            1,
            1,
        ):

            return None

        return QDate(
            value
        )

    @staticmethod
    def _parse_message_date(
        value: Any,
    ) -> QDate | None:
        """
        Parse a message date from common ISO and display formats.
        """

        if value is None:

            return None

        if isinstance(
            value,
            QDate,
        ):

            if value.isValid():

                return QDate(
                    value
                )

            return None

        text = str(
            value
        ).strip()

        if not text:

            return None

        date_text = (
            text[
                :10
            ]
            if len(
                text
            ) >= 10
            else text
        )

        formats = (
            "yyyy-MM-dd",
            "dd.MM.yyyy",
            "dd/MM/yyyy",
            "MM/dd/yyyy",
        )

        for date_format in formats:

            parsed_date = QDate.fromString(
                date_text,
                date_format,
            )

            if parsed_date.isValid():

                return parsed_date

        return None


class MessageWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Workspace section for imported messages.
    """

    create_evidence_requested = Signal(
        dict
    )

    create_entity_requested = Signal(
        dict
    )

    add_timeline_event_requested = Signal(
        dict
    )

    ai_analysis_requested = Signal(
        dict
    )

    bulk_action_requested = Signal(
        str,
        list,
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._selected_message: (
            dict[str, Any] | None
        ) = None

        self._setup_ui()

        active_translation_manager = (
            translation_manager
            if translation_manager is not None
            else get_translation_manager()
        )

        self.initialize_translations(
            active_translation_manager
        )

        self._update_workspace_state()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create message workspace UI.
        """

        self.setObjectName(
            "MessageWorkspaceView"
        )

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
            16
        )

        self._create_section()
        self._create_toolbar()
        self._create_filter_panel()
        self._create_models()
        self._create_statistics_bar()
        self._create_content()
        self._create_connections()



    def _create_section(
        self,
    ) -> None:
        """
        Create main messages section.
        """

        self.messages_section = Section(
            title="Investigation Messages",
            description=(
                "Review imported communications, search message "
                "content and inspect complete message details."
            ),
            parent=self,
        )

        self.messages_section.setObjectName(
            "MessagesSection"
        )

        self.messages_section.set_variant(
            "default"
        )

        self.messages_section.set_content_spacing(
            14
        )

        self.messages_section.set_content_margins(

            0,
            0,
            0,
            0,
        )

        self.messages_section.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.main_layout.addWidget(
            self.messages_section,
            1,
        )

    def _create_toolbar(
        self,
    ) -> None:
        """
        Create search and statistics toolbar.
        """

        self.toolbar = Toolbar(
            parent=self.messages_section
        )

        self.toolbar.setObjectName(
            "MessagesToolbar"
        )

        self.toolbar.set_variant(
            "default"
        )

        self.search_box = SearchBox(
            placeholder=(
                "Search by text, sender, receiver, chat or date..."
            ),
            debounce_interval=200,
            parent=self.toolbar,
        )

        self.search_box.setObjectName(
            "MessagesSearchBox"
        )

        self.search_box.setMinimumWidth(
            320
        )

        self.search_box.setMaximumWidth(
            680
        )

        self.count_badge = Badge(
            text="0 messages",
            variant="neutral",
            size="medium",
            outlined=True,
            rounded=True,
            parent=self.toolbar,
        )

        self.count_badge.setObjectName(
            "MessagesCountBadge"
        )

        self.toolbar.add_left_widget(
            self.search_box,
            stretch=1,
        )

        self.toolbar.add_right_widget(
            self.count_badge
        )

        self.messages_section.add_widget(
            self.toolbar
        )

    def _create_filter_panel(
        self,
    ) -> None:
        """
        Create advanced message filtering controls.

        """

        self.filter_section = CollapsibleSection(
            title="Advanced Filters",
            subtitle=(
                "Restrict messages by participants, chat, "
                "date range and search mode."
            ),
            expanded=False,
            parent=self.messages_section,
        )

        self.filter_section.setObjectName(
            "MessageFilterSection"
        )

        self.filter_section.set_content_margins(
            0,
            0,
            0,
            0,
        )

        self.filter_section.set_content_spacing(
            0
        )


        self.filter_container = QWidget(
            self.filter_section
        )

        self.filter_container.setObjectName(
            "MessageFilterContainer"
        )

        self.filter_layout = QGridLayout(
            self.filter_container
        )

        self.filter_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.filter_layout.setHorizontalSpacing(
            12
        )

        self.filter_layout.setVerticalSpacing(
            10
        )

        # ------------------------------------------------------
        # Sender
        # ------------------------------------------------------

        self.sender_filter_label = QLabel(
            "Sender",
            self.filter_container,
        )

        self.sender_filter_label.setObjectName(
            "MessageFilterLabel"
        )

        self.sender_filter_combo = QComboBox(
            self.filter_container
        )

        self.sender_filter_combo.setObjectName(
            "MessageSenderFilter"
        )

        self.sender_filter_combo.setMinimumWidth(
            170
        )

        self.sender_filter_combo.addItem(
            "All senders",
            None,
        )

        # ------------------------------------------------------
        # Receiver
        # ------------------------------------------------------

        self.receiver_filter_label = QLabel(
            "Receiver",
            self.filter_container,
        )

        self.receiver_filter_label.setObjectName(
            "MessageFilterLabel"
        )

        self.receiver_filter_combo = QComboBox(
            self.filter_container
        )

        self.receiver_filter_combo.setObjectName(
            "MessageReceiverFilter"
        )

        self.receiver_filter_combo.setMinimumWidth(
            170
        )

        self.receiver_filter_combo.addItem(
            "All receivers",
            None,
        )

        # ------------------------------------------------------
        # Chat
        # ------------------------------------------------------

        self.chat_filter_label = QLabel(
            "Chat",
            self.filter_container,
        )

        self.chat_filter_label.setObjectName(
            "MessageFilterLabel"
        )

        self.chat_filter_combo = QComboBox(
            self.filter_container
        )

        self.chat_filter_combo.setObjectName(
            "MessageChatFilter"
        )

        self.chat_filter_combo.setMinimumWidth(
            170
        )

        self.chat_filter_combo.addItem(
            "All chats",
            None,
        )

        # ------------------------------------------------------
        # Date from
        # ------------------------------------------------------

        self.date_from_label = QLabel(
            "Date from",
            self.filter_container,
        )

        self.date_from_label.setObjectName(
            "MessageFilterLabel"
        )

        self.date_from_input = QDateEdit(
            self.filter_container
        )

        self.date_from_input.setObjectName(
            "MessageDateFromFilter"
        )

        self.date_from_input.setCalendarPopup(
            True
        )

        self.date_from_input.setDisplayFormat(
            "yyyy-MM-dd"
        )

        self.date_from_input.setMinimumDate(
            QDate(
                1970,
                1,
                1,
            )
        )

        self.date_from_input.setMaximumDate(
            QDate(
                2999,
                12,
                31,
            )
        )

        self.date_from_input.setDate(
            self.date_from_input.minimumDate()
        )

        self.date_from_input.setSpecialValueText(
            "Any date"
        )

        # ------------------------------------------------------
        # Date to
        # ------------------------------------------------------

        self.date_to_label = QLabel(
            "Date to",
            self.filter_container,
        )

        self.date_to_label.setObjectName(
            "MessageFilterLabel"
        )

        self.date_to_input = QDateEdit(
            self.filter_container
        )

        self.date_to_input.setObjectName(
            "MessageDateToFilter"
        )

        self.date_to_input.setCalendarPopup(
            True
        )

        self.date_to_input.setDisplayFormat(
            "yyyy-MM-dd"
        )

        self.date_to_input.setMinimumDate(
            QDate(
                1970,
                1,
                1,
            )
        )

        self.date_to_input.setMaximumDate(
            QDate(
                2999,
                12,
                31,
            )
        )

        self.date_to_input.setDate(
            self.date_to_input.minimumDate()
        )

        self.date_to_input.setSpecialValueText(
            "Any date"
        )

        # ------------------------------------------------------
        # Search options
        # ------------------------------------------------------

        self.case_sensitive_checkbox = QCheckBox(
            "Case sensitive",
            self.filter_container,
        )

        self.case_sensitive_checkbox.setObjectName(
            "MessageCaseSensitiveFilter"
        )

        self.regex_checkbox = QCheckBox(
            "Regular expression",
            self.filter_container,
        )

        self.regex_checkbox.setObjectName(
            "MessageRegexFilter"
        )

        # ------------------------------------------------------
        # Reset
        # ------------------------------------------------------

        self.reset_filters_button = QPushButton(
            "Reset Filters",
            self.filter_container,
        )

        self.reset_filters_button.setObjectName(
            "MessageResetFiltersButton"
        )

        self.reset_filters_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        # ------------------------------------------------------
        # Layout
        # ------------------------------------------------------

        self.filter_layout.addWidget(
            self.sender_filter_label,
            0,
            0,
        )

        self.filter_layout.addWidget(
            self.sender_filter_combo,
            1,
            0,
        )

        self.filter_layout.addWidget(
            self.receiver_filter_label,
            0,
            1,
        )

        self.filter_layout.addWidget(
            self.receiver_filter_combo,
            1,
            1,
        )

        self.filter_layout.addWidget(
            self.chat_filter_label,
            0,
            2,
        )

        self.filter_layout.addWidget(
            self.chat_filter_combo,
            1,
            2,
        )

        self.filter_layout.addWidget(
            self.date_from_label,
            0,
            3,
        )

        self.filter_layout.addWidget(
            self.date_from_input,
            1,
            3,
        )

        self.filter_layout.addWidget(
            self.date_to_label,
            0,
            4,
        )

        self.filter_layout.addWidget(
            self.date_to_input,
            1,
            4,
        )

        self.filter_layout.addWidget(
            self.case_sensitive_checkbox,
            2,
            0,
            1,
            2,
        )

        self.filter_layout.addWidget(
            self.regex_checkbox,
            2,
            2,
            1,
            2,
        )

        self.filter_layout.addWidget(
            self.reset_filters_button,
            2,
            4,
        )

        for column in range(
            5
        ):

            self.filter_layout.setColumnStretch(
                column,
                1,
            )

            self.messages_section.add_widget(
                self.filter_section
            )

        self.filter_section.add_widget(
            self.filter_container
        )

        self.messages_section.add_widget(
            self.filter_section
        )

    def _create_models(
        self,
    ) -> None:
        """
        Create source and filtering models.
        """

        self.message_model = MessageTableModel(
            self
        )

        self.proxy_model = MessageFilterProxyModel(
            self
        )

        self.proxy_model.setSourceModel(
            self.message_model
        )


    def _create_statistics_bar(
        self,
    ) -> None:
        """
        Create message statistics bar.
        """

        self.statistics_frame = QFrame(
            self.messages_section
        )

        self.statistics_frame.setObjectName(
            "MessagesStatisticsFrame"
        )

        self.statistics_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.statistics_layout = QHBoxLayout(
            self.statistics_frame
        )

        self.statistics_layout.setContentsMargins(
            14,
            8,
            14,
            8,
        )

        self.statistics_layout.setSpacing(
            20
        )

        self.total_messages_label = QLabel(
            self.statistics_frame
        )

        self.total_messages_label.setObjectName(
            "MessagesStatisticLabel"
        )

        self.visible_messages_label = QLabel(
            self.statistics_frame
        )

        self.visible_messages_label.setObjectName(
            "MessagesStatisticLabel"
        )

        self.selected_messages_label = QLabel(
            self.statistics_frame
        )

        self.selected_messages_label.setObjectName(
            "MessagesStatisticLabel"
        )

        self.senders_count_label = QLabel(
            self.statistics_frame
        )

        self.senders_count_label.setObjectName(
            "MessagesStatisticLabel"
        )

        self.receivers_count_label = QLabel(
            self.statistics_frame
        )

        self.receivers_count_label.setObjectName(
            "MessagesStatisticLabel"
        )

        self.chats_count_label = QLabel(
            self.statistics_frame
        )

        self.chats_count_label.setObjectName(
            "MessagesStatisticLabel"
        )

        statistic_labels = (
            self.total_messages_label,
            self.visible_messages_label,
            self.senders_count_label,
            self.receivers_count_label,
            self.chats_count_label,
            self.selected_messages_label,
        )

        for label in statistic_labels:

            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

            self.statistics_layout.addWidget(
                label
            )

        self.statistics_layout.addStretch(
            1
        )

        self.messages_section.add_widget(
            self.statistics_frame
        )

    def _create_content(
        self,
    ) -> None:
        """
        Create table, details view and empty state.
        """

        self.content_container = QFrame(
            self.messages_section
        )

        self.content_container.setObjectName(
            "MessagesContentContainer"
        )

        self.content_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.content_layout = QVBoxLayout(
            self.content_container
        )

        self.content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.content_layout.setSpacing(
            0
        )

        self._create_messages_splitter()
        self._create_empty_state()

        self.messages_section.add_widget(
            self.content_container,
            stretch=1,
        )

    def _create_messages_splitter(
        self,
    ) -> None:
        """
        Create horizontal messages and details workspace.
        """

        self.splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self.content_container,
        )

        self.splitter.setObjectName(
            "MessagesSplitter"
        )

        self.splitter.setChildrenCollapsible(
            False
        )

        self._create_message_table()
        self._create_details_card()

        self.splitter.addWidget(
            self.message_table
        )

        self.splitter.addWidget(
            self.details_card
        )

        self.splitter.setStretchFactor(
            0,
            3,
        )

        self.splitter.setStretchFactor(
            1,
            2,
        )

        self.splitter.setSizes(
            [
                760,
                420,
            ]
        )

        self.content_layout.addWidget(
            self.splitter,
            1,
        )

    def _create_message_table(
        self,
    ) -> None:
        """
        Create virtualized messages table.
        """

        self.message_table = QTableView(
            self.splitter
        )

        self.message_table.setObjectName(
            "MessagesTable"
        )

        self.message_table.setModel(
            self.proxy_model
        )

        self.message_table.setSortingEnabled(
            True
        )

        self.message_table.setAlternatingRowColors(
            True
        )

        self.message_table.setSelectionBehavior(
            QAbstractItemView
            .SelectionBehavior
            .SelectRows
        )

        self.message_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self.message_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self.message_table.setEditTriggers(
            QAbstractItemView
            .EditTrigger
            .NoEditTriggers
        )

        self.message_table.setWordWrap(
            False
        )

        self.message_table.setShowGrid(
            False
        )

        self.message_table.setVerticalScrollMode(
            QAbstractItemView
            .ScrollMode
            .ScrollPerPixel
        )

        self.message_table.setHorizontalScrollMode(
            QAbstractItemView
            .ScrollMode
            .ScrollPerPixel
        )

        self.message_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )


        self.message_table.setMinimumWidth(
            520
        )


        self.message_table.verticalHeader().setVisible(
            False
        )

        self.message_table.verticalHeader().setDefaultSectionSize(
            38
        )

        header = (
            self.message_table
            .horizontalHeader()
        )

        header.setHighlightSections(
            False
        )

        header.setStretchLastSection(
            True
        )

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Fixed,
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Interactive,
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Interactive,
        )

        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Interactive,
        )

        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )

        self.message_table.setColumnWidth(
            0,
            165,
        )

        self.message_table.setColumnWidth(
            1,
            170,
        )

        self.message_table.setColumnWidth(
            2,
            170,
        )

        self.message_table.setColumnWidth(
            3,
            180,
        )

    def _create_details_card(
        self,
    ) -> None:
        """
        Create selected message details panel.
        """

        self.details_card = Card(
            title="Message Details",
            subtitle=(
                "Select a message to inspect its complete metadata "
                "and original text."
            ),
            parent=self.splitter,
        )

        self.details_card.setObjectName(
            "MessageDetailsCard"
        )

        self.details_card.set_variant(
            "default"
        )

        self.details_view = QPlainTextEdit(
            self.details_card
        )

        self.details_view.setObjectName(
            "MessageDetailsView"
        )

        self.details_view.setReadOnly(
            True
        )

        self.details_view.setPlaceholderText(
            "Select a message to view its full contents."
        )

        self.details_card.setMinimumWidth(
            320
        )

        self.details_card.setMaximumWidth(
            620
        )

        self.details_view.setMinimumHeight(
            240
        )


        self.details_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.details_card.add_widget(
            self.details_view
        )

    def _create_empty_state(
        self,
    ) -> None:
        """
        Create empty messages placeholder.
        """

        self.empty_state = EmptyState(
            title="No messages imported",
            description=(
                "Import a Telegram result.json export to populate "
                "this investigation with messages."
            ),
            marker="✉",
            parent=self.content_container,
        )

        self.empty_state.setObjectName(
            "MessagesEmptyState"
        )

        self.empty_state.set_variant(
            "panel"
        )

        self.empty_state.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.content_layout.addWidget(
            self.empty_state,
            1,
        )

        self.empty_state.hide()

    def _create_connections(
        self,
    ) -> None:
        """
        Connect workspace interactions.
        """

        self.search_box.search_changed.connect(
            self._filter_messages
        )

        self.search_box.search_submitted.connect(
            self._filter_messages
        )

        self.sender_filter_combo.currentIndexChanged.connect(
            self._sender_filter_changed
        )

        self.receiver_filter_combo.currentIndexChanged.connect(
            self._receiver_filter_changed
        )

        self.chat_filter_combo.currentIndexChanged.connect(
            self._chat_filter_changed
        )

        self.date_from_input.dateChanged.connect(
            self._date_from_changed
        )

        self.date_to_input.dateChanged.connect(
            self._date_to_changed
        )

        self.case_sensitive_checkbox.toggled.connect(
            self._case_sensitive_changed
        )

        self.regex_checkbox.toggled.connect(
            self._regex_changed
        )

        self.reset_filters_button.clicked.connect(
            self._reset_filters
        )

        selection_model = (
            self.message_table
            .selectionModel()
        )

        if selection_model is not None:

            selection_model.selectionChanged.connect(
                self._show_selected_message
            )

        self.message_table.customContextMenuRequested.connect(
            self._show_message_context_menu
        )

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply the active application language.
        """

        self.messages_section.set_title(
            self.translate(
                "messages.section.title",
                default="Investigation Messages",
            )
        )

        self.messages_section.set_description(
            self.translate(
                "messages.section.description",
                default=(
                    "Review imported communications, search message "
                    "content and inspect complete message details."
                ),
            )
        )

        self.search_box.set_placeholder(
            self.translate(
                "messages.search.placeholder",
                default=(
                    "Search by text, sender, receiver, chat or date..."
                ),
            )
        )


        self.sender_filter_label.setText(
            self.translate(
                "messages.filters.sender",
                default="Sender",
            )
        )

        self.receiver_filter_label.setText(
            self.translate(
                "messages.filters.receiver",
                default="Receiver",
            )
        )

        self.chat_filter_label.setText(
            self.translate(
                "messages.filters.chat",
                default="Chat",
            )
        )

        self.date_from_label.setText(
            self.translate(
                "messages.filters.date_from",
                default="Date from",
            )
        )

        self.date_to_label.setText(
            self.translate(
                "messages.filters.date_to",
                default="Date to",
            )
        )

        self.case_sensitive_checkbox.setText(
            self.translate(
                "messages.filters.case_sensitive",
                default="Case sensitive",
            )
        )

        self.regex_checkbox.setText(
            self.translate(
                "messages.filters.regex",
                default="Regular expression",
            )
        )

        self.reset_filters_button.setText(
            self.translate(
                "messages.filters.reset",
                default="Reset Filters",
            )
        )

        self.date_from_input.setSpecialValueText(
            self.translate(
                "messages.filters.any_date",
                default="Any date",
            )
        )

        self.date_to_input.setSpecialValueText(
            self.translate(
                "messages.filters.any_date",
                default="Any date",
            )
        )

        self._retranslate_filter_combo_defaults()



        self.message_model.set_headers(
            [
                self.translate(
                    "messages.table.date",
                    default="Date",
                ),
                self.translate(
                    "messages.table.sender",
                    default="Sender",
                ),
                self.translate(
                    "messages.table.receiver",
                    default="Receiver",
                ),
                self.translate(
                    "messages.table.chat",
                    default="Chat",
                ),
                self.translate(
                    "messages.table.message",
                    default="Message",
                ),
            ]
        )

        self.details_card.set_title(
            self.translate(
                "messages.details.title",
                default="Message Details",
            )
        )

        self.details_card.set_subtitle(
            self.translate(
                "messages.details.subtitle",
                default=(
                    "Select a message to inspect its complete metadata "
                    "and original text."
                ),
            )
        )

        self.details_view.setPlaceholderText(
            self.translate(
                "messages.details.placeholder",
                default=(
                    "Select a message to view its full contents."
                ),
            )
        )

        self._update_workspace_state()
        self._refresh_selected_message_details()


    def _retranslate_filter_combo_defaults(
        self,
    ) -> None:
        """
        Translate default values of filter combo boxes without
        removing dynamically loaded participants and chats.
        """

        combo_defaults = (
            (
                self.sender_filter_combo,
                "messages.filters.all_senders",
                "All senders",
            ),
            (
                self.receiver_filter_combo,
                "messages.filters.all_receivers",
                "All receivers",
            ),
            (
                self.chat_filter_combo,
                "messages.filters.all_chats",
                "All chats",
            ),
        )

        for combo, key, default in combo_defaults:

            if combo.count() == 0:

                combo.addItem(
                    self.translate(
                        key,
                        default=default,
                    ),
                    None,
                )

                continue

            combo.setItemText(
                0,
                self.translate(
                    key,
                    default=default,
                ),
            )

    # ==========================================================
    # Public API
    # ==========================================================

    def set_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> None:
        """
        Display messages in the workspace.
        """

        normalized_messages = (
            messages
            if isinstance(
                messages,
                list,
            )
            else []
        )

        self._selected_message = None

        self.details_view.clear()

        self.message_table.clearSelection()

        self.message_model.set_messages(
            normalized_messages
        )

        self._populate_filter_combos()

        self.proxy_model.invalidate()

        self._update_workspace_state()

        if self.proxy_model.rowCount() > 0:

            self.message_table.selectRow(
                0
            )

    def clear_messages(
        self,
    ) -> None:
        """
        Clear all displayed messages.
        """

        self._selected_message = None

        self.details_view.clear()

        self.message_table.clearSelection()

        self.message_model.clear()

        self._populate_filter_combos()

        self.proxy_model.invalidate()

        self._update_workspace_state()

    # ==========================================================
    # Filtering
    # ==========================================================

    def _filter_messages(
        self,
        text: str,
    ) -> None:
        """
        Filter visible messages.
        """

        self.proxy_model.set_search_text(
            text
        )

        self._selected_message = None

        self.message_table.clearSelection()

        self.details_view.clear()

        self._update_workspace_state()

        if self.proxy_model.rowCount() > 0:

            self.message_table.selectRow(
                0
            )

    def _update_workspace_state(
        self,
    ) -> None:
        """
        Update counts and empty states.
        """

        total_count = (
            self.message_model.rowCount()
        )

        visible_count = (
            self.proxy_model.rowCount()
        )

        self._update_statistics()

        self._update_count_badge(
            visible_count=visible_count,
            total_count=total_count,
        )

        has_visible_messages = (
            visible_count > 0
        )

        self.splitter.setVisible(
            has_visible_messages
        )

        self.empty_state.setVisible(
            not has_visible_messages
        )

        if has_visible_messages:

            return

        has_search = bool(
            self.proxy_model
            .search_text()
        )

        if (
            total_count > 0
            and has_search
        ):

            self.empty_state.set_marker(
                "⌕"
            )

            self.empty_state.set_title(
                self.translate(
                    "messages.empty.search.title",
                    default="No matching messages",
                )
            )

            self.empty_state.set_description(
                self.translate(
                    "messages.empty.search.description",
                    default=(
                        "No messages match the current search. "
                        "Try another sender, chat, date or phrase."
                    ),
                )
            )

            return

        self.empty_state.set_marker(
            "✉"
        )

        self.empty_state.set_title(
            self.translate(
                "messages.empty.title",
                default="No messages imported",
            )
        )

        self.empty_state.set_description(
            self.translate(
                "messages.empty.description",
                default=(
                    "Import a Telegram result.json export to populate "
                    "this investigation with messages."
                ),
            )
        )

    def _update_count_badge(
        self,
        visible_count: int,
        total_count: int,
    ) -> None:
        """
        Update total and filtered message count.
        """

        if visible_count == total_count:

            if total_count == 1:

                text = self.translate(
                    "messages.count.single",
                    default="{count} message",
                    count=total_count,
                )

            else:

                text = self.translate(
                    "messages.count.multiple",
                    default="{count} messages",
                    count=total_count,
                )

            self.count_badge.set_text(
                text
            )

            return

        self.count_badge.set_text(
            self.translate(
                "messages.count.filtered",
                default=(
                    "{visible} of {total} messages"
                ),
                visible=visible_count,
                total=total_count,
            )
        )

    def _sender_filter_changed(
        self,
    ) -> None:

        self.proxy_model.set_sender_filter(
            self.sender_filter_combo.currentData()
        )


    def _receiver_filter_changed(
        self,
    ) -> None:

        self.proxy_model.set_receiver_filter(
            self.receiver_filter_combo.currentData()
        )


    def _chat_filter_changed(
        self,
    ) -> None:

        self.proxy_model.set_chat_filter(
            self.chat_filter_combo.currentData()
        )


    def _date_from_changed(
        self,
        value,
    ) -> None:

        self.proxy_model.set_date_from(
            value
        )


    def _date_to_changed(
        self,
        value,
    ) -> None:

        self.proxy_model.set_date_to(
            value
        )


    def _case_sensitive_changed(
        self,
        enabled: bool,
    ) -> None:

        self.proxy_model.set_case_sensitive(
            enabled
        )


    def _regex_changed(
        self,
        enabled: bool,
    ) -> None:

        self.proxy_model.set_regex(
            enabled
        )


    def _reset_filters(
        self,
    ) -> None:
        """
        Reset all message filters and search modes.
        """

        self.search_box.clear()

        controls = (
            self.sender_filter_combo,
            self.receiver_filter_combo,
            self.chat_filter_combo,
            self.date_from_input,
            self.date_to_input,
            self.case_sensitive_checkbox,
            self.regex_checkbox,
        )

        for control in controls:

            control.blockSignals(
                True
            )

        try:

            self.sender_filter_combo.setCurrentIndex(
                0
            )

            self.receiver_filter_combo.setCurrentIndex(
                0
            )

            self.chat_filter_combo.setCurrentIndex(
                0
            )

            self.date_from_input.setDate(
                self.date_from_input.minimumDate()
            )

            self.date_to_input.setDate(
                self.date_to_input.minimumDate()
            )

            self.case_sensitive_checkbox.setChecked(
                False
            )

            self.regex_checkbox.setChecked(
                False
            )

        finally:

            for control in controls:

                control.blockSignals(
                    False
                )

        self.proxy_model.clear_filters()

        self._selected_message = None

        self.message_table.clearSelection()

        self.details_view.clear()

        self._update_workspace_state()

        if self.proxy_model.rowCount() > 0:

            self.message_table.selectRow(
                0
            )

            # ==========================================================
    # Filter options
    # ==========================================================

    def _populate_filter_combos(
        self,
    ) -> None:
        """
        Populate sender, receiver and chat filters from loaded messages.

        Existing selections are preserved when possible.
        """

        selected_sender = (
            self.sender_filter_combo.currentData()
        )

        selected_receiver = (
            self.receiver_filter_combo.currentData()
        )

        selected_chat = (
            self.chat_filter_combo.currentData()
        )

        messages: list[dict[str, Any]] = []

        for row in range(
            self.message_model.rowCount()
        ):

            message = (
                self.message_model.get_message(
                    row
                )
            )

            if message is not None:

                messages.append(
                    message
                )

        senders = sorted(
            {
                str(
                    message.get(
                        "sender"
                    )
                    or ""
                ).strip()
                for message in messages
                if str(
                    message.get(
                        "sender"
                    )
                    or ""
                ).strip()
            },
            key=str.casefold,
        )

        receivers = sorted(
            {
                str(
                    message.get(
                        "receiver"
                    )
                    or ""
                ).strip()
                for message in messages
                if str(
                    message.get(
                        "receiver"
                    )
                    or ""
                ).strip()
            },
            key=str.casefold,
        )

        chats = sorted(
            {
                str(
                    message.get(
                        "chat_name"
                    )
                    or ""
                ).strip()
                for message in messages
                if str(
                    message.get(
                        "chat_name"
                    )
                    or ""
                ).strip()
            },
            key=str.casefold,
        )

        self._replace_filter_combo_items(
            combo=self.sender_filter_combo,
            values=senders,
            selected_value=selected_sender,
            default_key="messages.filters.all_senders",
            default_text="All senders",
        )

        self._replace_filter_combo_items(
            combo=self.receiver_filter_combo,
            values=receivers,
            selected_value=selected_receiver,
            default_key="messages.filters.all_receivers",
            default_text="All receivers",
        )

        self._replace_filter_combo_items(
            combo=self.chat_filter_combo,
            values=chats,
            selected_value=selected_chat,
            default_key="messages.filters.all_chats",
            default_text="All chats",
        )

    def _replace_filter_combo_items(
        self,
        *,
        combo: QComboBox,
        values: list[str],
        selected_value: str | None,
        default_key: str,
        default_text: str,
    ) -> None:
        """
        Replace combo-box items without emitting intermediate changes.
        """

        combo.blockSignals(
            True
        )

        combo.clear()

        combo.addItem(
            self.translate(
                default_key,
                default=default_text,
            ),
            None,
        )

        for value in values:

            combo.addItem(
                value,
                value,
            )

        selected_index = 0

        if selected_value is not None:

            found_index = combo.findData(
                selected_value
            )

            if found_index >= 0:

                selected_index = found_index

        combo.setCurrentIndex(
            selected_index
        )

        combo.blockSignals(
            False
        )

    # ==========================================================
    # Statistics
    # ==========================================================

    def _update_statistics(
        self,
    ) -> None:
        """
        Update statistics for currently loaded and visible messages.
        """

        total_messages = (
            self.message_model.rowCount()
        )

        visible_messages = (
            self.proxy_model.rowCount()
        )

        visible_items = (
            self._get_visible_messages()
        )

        selected_messages = len(
            self.get_selected_messages()
        )

        senders = {
            str(
                message.get(
                    "sender"
                )
            ).strip()
            for message in visible_items
            if str(
                message.get(
                    "sender"
                )
                or ""
            ).strip()
        }

        receivers = {
            str(
                message.get(
                    "receiver"
                )
            ).strip()
            for message in visible_items
            if str(
                message.get(
                    "receiver"
                )
                or ""
            ).strip()
        }

        chats = {
            str(
                message.get(
                    "chat_name"
                )
            ).strip()
            for message in visible_items
            if str(
                message.get(
                    "chat_name"
                )
                or ""
            ).strip()
        }

        self.total_messages_label.setText(
            self.translate(
                "messages.statistics.total",
                default="Messages: {count}",
                count=total_messages,
            )
        )

        self.visible_messages_label.setText(
            self.translate(
                "messages.statistics.visible",
                default="Visible: {count}",
                count=visible_messages,
            )
        )

        self.selected_messages_label.setText(
            self.translate(
                "messages.statistics.selected",
                default="Selected: {count}",
                count=selected_messages,
            )
        )

        self.senders_count_label.setText(
            self.translate(
                "messages.statistics.senders",
                default="Senders: {count}",
                count=len(
                    senders
                ),
            )
        )

        self.receivers_count_label.setText(
            self.translate(
                "messages.statistics.receivers",
                default="Receivers: {count}",
                count=len(
                    receivers
                ),
            )
        )

        self.chats_count_label.setText(
            self.translate(
                "messages.statistics.chats",
                default="Chats: {count}",
                count=len(
                    chats
                ),
            )
        )

    def _get_visible_messages(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return messages currently visible through the proxy model.
        """

        visible_messages: list[
            dict[str, Any]
        ] = []

        for proxy_row in range(
            self.proxy_model.rowCount()
        ):

            proxy_index = (
                self.proxy_model.index(
                    proxy_row,
                    0,
                )
            )

            source_index = (
                self.proxy_model.mapToSource(
                    proxy_index
                )
            )

            message = (
                self.message_model.get_message(
                    source_index.row()
                )
            )

            if message is not None:

                visible_messages.append(
                    message
                )

        return visible_messages

    # ==========================================================
    # Context menu
    # ==========================================================

    def _show_message_context_menu(
        self,
        position,
    ) -> None:
        """
        Display context actions for the message under the cursor.

        Preserves multiple selection when the user opens the menu
        on an already selected row.
        """

        proxy_index = self.message_table.indexAt(
            position
        )

        if not proxy_index.isValid():

            return

        selection_model = (
            self.message_table.selectionModel()
        )

        if selection_model is None:

            return

        selected_rows = (
            selection_model.selectedRows(
                0
            )
        )

        clicked_row_is_selected = any(
            selected_index.row()
            == proxy_index.row()
            for selected_index in selected_rows
        )

        if not clicked_row_is_selected:

            self.message_table.clearSelection()

            self.message_table.selectRow(
                proxy_index.row()
            )

        message = (
            self._get_message_from_proxy_index(
                proxy_index
            )
        )

        if message is None:

            return

        selected_messages = (
            self.get_selected_messages()
        )

        menu = QMenu(
            self.message_table
        )

        # ======================================================
        # Copy
        # ======================================================

        copy_menu = menu.addMenu(
            self.translate(
                "messages.context.copy",
                default="Copy",
            )
        )

        copy_text_action = QAction(
            self.translate(
                "messages.context.copy_text",
                default="Copy text",
            ),
            copy_menu,
        )

        copy_sender_action = QAction(
            self.translate(
                "messages.context.copy_sender",
                default="Copy sender",
            ),
            copy_menu,
        )

        copy_receiver_action = QAction(
            self.translate(
                "messages.context.copy_receiver",
                default="Copy receiver",
            ),
            copy_menu,
        )

        copy_external_id_action = QAction(
            self.translate(
                "messages.context.copy_external_id",
                default="Copy external ID",
            ),
            copy_menu,
        )

        copy_menu.addAction(
            copy_text_action
        )

        copy_menu.addAction(
            copy_sender_action
        )

        copy_menu.addAction(
            copy_receiver_action
        )

        copy_menu.addAction(
            copy_external_id_action
        )

        copy_text_action.setEnabled(
            bool(
                str(
                    message.get(
                        "text"
                    )
                    or ""
                ).strip()
            )
        )

        copy_sender_action.setEnabled(
            bool(
                str(
                    message.get(
                        "sender"
                    )
                    or ""
                ).strip()
            )
        )

        copy_receiver_action.setEnabled(
            bool(
                str(
                    message.get(
                        "receiver"
                    )
                    or ""
                ).strip()
            )
        )

        copy_external_id_action.setEnabled(
            bool(
                str(
                    message.get(
                        "external_id"
                    )
                    or ""
                ).strip()
            )
        )

        copy_text_action.triggered.connect(
            lambda checked=False,
            current_message=message:
                self._copy_message_field(
                    current_message,
                    "text",
                )
        )

        copy_sender_action.triggered.connect(
            lambda checked=False,
            current_message=message:
                self._copy_message_field(
                    current_message,
                    "sender",
                )
        )

        copy_receiver_action.triggered.connect(
            lambda checked=False,
            current_message=message:
                self._copy_message_field(
                    current_message,
                    "receiver",
                )
        )

        copy_external_id_action.triggered.connect(
            lambda checked=False,
            current_message=message:
                self._copy_message_field(
                    current_message,
                    "external_id",
                )
        )

        # ======================================================
        # Analysis
        # ======================================================

        menu.addSeparator()

        analysis_menu = menu.addMenu(
            self.translate(
                "messages.context.analysis",
                default="Analysis",
            )
        )

        same_sender_action = QAction(
            self.translate(
                "messages.context.same_sender",
                default=(
                    "Show messages from same sender"
                ),
            ),
            analysis_menu,
        )

        same_receiver_action = QAction(
            self.translate(
                "messages.context.same_receiver",
                default=(
                    "Show messages to same receiver"
                ),
            ),
            analysis_menu,
        )

        same_chat_action = QAction(
            self.translate(
                "messages.context.same_chat",
                default=(
                    "Show messages from same chat"
                ),
            ),
            analysis_menu,
        )

        clear_filters_action = QAction(
            self.translate(
                "messages.context.clear_filters",
                default="Clear all filters",
            ),
            analysis_menu,
        )

        analysis_menu.addAction(
            same_sender_action
        )

        analysis_menu.addAction(
            same_receiver_action
        )

        analysis_menu.addAction(
            same_chat_action
        )

        analysis_menu.addSeparator()

        analysis_menu.addAction(
            clear_filters_action
        )

        sender = str(
            message.get(
                "sender"
            )
            or ""
        ).strip()

        receiver = str(
            message.get(
                "receiver"
            )
            or ""
        ).strip()

        chat_name = str(
            message.get(
                "chat_name"
            )
            or ""
        ).strip()

        same_sender_action.setEnabled(
            bool(
                sender
            )
        )

        same_receiver_action.setEnabled(
            bool(
                receiver
            )
        )

        same_chat_action.setEnabled(
            bool(
                chat_name
            )
        )

        clear_filters_action.setEnabled(
            self.proxy_model.has_active_filters()
        )

        same_sender_action.triggered.connect(
            lambda checked=False,
            value=sender:
                self._apply_sender_quick_filter(
                    value
                )
        )

        same_receiver_action.triggered.connect(
            lambda checked=False,
            value=receiver:
                self._apply_receiver_quick_filter(
                    value
                )
        )

        same_chat_action.triggered.connect(
            lambda checked=False,
            value=chat_name:
                self._apply_chat_quick_filter(
                    value
                )
        )

        clear_filters_action.triggered.connect(
            self._reset_filters
        )

        # ======================================================
        # Investigation
        # ======================================================

        menu.addSeparator()

        investigation_menu = menu.addMenu(
            self.translate(
                "messages.context.investigation",
                default="Investigation",
            )
        )

        create_evidence_action = QAction(
            self.translate(
                "messages.context.create_evidence",
                default="Create evidence",
            ),
            investigation_menu,
        )

        create_entity_action = QAction(
            self.translate(
                "messages.context.create_entity",
                default="Create entity",
            ),
            investigation_menu,
        )

        add_timeline_action = QAction(
            self.translate(
                "messages.context.add_timeline",
                default="Add to timeline",
            ),
            investigation_menu,
        )

        investigation_menu.addAction(
            create_evidence_action
        )

        investigation_menu.addAction(
            create_entity_action
        )

        investigation_menu.addAction(
            add_timeline_action
        )

        create_evidence_action.triggered.connect(
            lambda checked=False,
            current_message=message:
                self._request_create_evidence(
                    current_message
                )
        )

        create_entity_action.triggered.connect(
            lambda checked=False,
            current_message=message:
                self._request_create_entity(
                    current_message
                )
        )

        add_timeline_action.triggered.connect(
            lambda checked=False,
            current_message=message:
                self._request_add_timeline_event(
                    current_message
                )
        )

        # ======================================================
        # Bulk investigation
        # ======================================================

        investigation_menu.addSeparator()

        bulk_menu = investigation_menu.addMenu(
            self.translate(
                "messages.context.bulk_investigation",
                default="Bulk Investigation",
            )
        )

        bulk_evidence_action = QAction(
            self.translate(
                "messages.context.bulk_create_evidence",
                default=(
                    "Create evidence from selected"
                ),
            ),
            bulk_menu,
        )

        bulk_entity_action = QAction(
            self.translate(
                "messages.context.bulk_create_entity",
                default=(
                    "Create entities from selected"
                ),
            ),
            bulk_menu,
        )

        bulk_timeline_action = QAction(
            self.translate(
                "messages.context.bulk_add_timeline",
                default=(
                    "Add selected to timeline"
                ),
            ),
            bulk_menu,
        )

        bulk_menu.addAction(
            bulk_evidence_action
        )

        bulk_menu.addAction(
            bulk_entity_action
        )

        bulk_menu.addAction(
            bulk_timeline_action
        )

        bulk_enabled = (
            len(
                selected_messages
            )
            > 1
        )

        bulk_menu.setEnabled(
            bulk_enabled
        )

        bulk_evidence_action.triggered.connect(
            lambda checked=False,
            messages=selected_messages:
                self.bulk_action_requested.emit(
                    "evidence",
                    messages,
                )
        )

        bulk_entity_action.triggered.connect(
            lambda checked=False,
            messages=selected_messages:
                self.bulk_action_requested.emit(
                    "entity",
                    messages,
                )
        )

        bulk_timeline_action.triggered.connect(
            lambda checked=False,
            messages=selected_messages:
                self.bulk_action_requested.emit(
                    "timeline",
                    messages,
                )
        )

        # ======================================================
        # AI
        # ======================================================

        menu.addSeparator()

        ai_action = QAction(
            self.translate(
                "messages.context.analyze_ai",
                default="Analyze message with AI",
            ),
            menu,
        )

        menu.addAction(
            ai_action
        )

        ai_action.triggered.connect(
            lambda checked=False,
            current_message=message:
                self._request_ai_analysis(
                    current_message
                )
        )

        # ======================================================
        # Display
        # ======================================================

        menu.exec(
            self.message_table
            .viewport()
            .mapToGlobal(
                position
            )
        )
    def _get_message_from_proxy_index(
        self,
        proxy_index: QModelIndex,
    ) -> dict[str, Any] | None:
        """
        Return the source message represented by a proxy index.
        """

        if not proxy_index.isValid():

            return None

        source_index = self.proxy_model.mapToSource(
            proxy_index
        )

        return self.message_model.get_message(
            source_index.row()
        )

    def get_selected_messages(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return all currently selected messages.

        Rows are returned in their visual order and without
        duplicates caused by selecting several cells in one row.
        """

        selection_model = (
            self.message_table.selectionModel()
        )

        if selection_model is None:

            return []

        selected_rows = sorted(
            selection_model.selectedRows(
                0
            ),
            key=lambda index: index.row(),
        )

        selected_messages: list[
            dict[str, Any]
        ] = []

        for proxy_index in selected_rows:

            message = (
                self._get_message_from_proxy_index(
                    proxy_index
                )
            )

            if message is not None:

                selected_messages.append(
                    dict(
                        message
                    )
                )

        return selected_messages

        self._update_statistics()

    @staticmethod
    def _copy_message_field(
        message: dict[str, Any],
        field_name: str,
    ) -> None:
        """
        Copy one message field to the system clipboard.
        """

        value = str(
            message.get(
                field_name
            )
            or ""
        )

        if not value:

            return

        clipboard = (
            QGuiApplication.clipboard()
        )

        clipboard.setText(
            value
        )

    def _apply_sender_quick_filter(
        self,
        sender: str,
    ) -> None:
        """
        Filter the table by one message sender.
        """

        normalized_sender = str(
            sender
        ).strip()

        if not normalized_sender:

            return

        index = (
            self.sender_filter_combo.findData(
                normalized_sender
            )
        )

        if index < 0:

            return

        self.filter_section.expand()

        self.sender_filter_combo.setCurrentIndex(
            index
        )

    def _apply_receiver_quick_filter(
        self,
        receiver: str,
    ) -> None:
        """
        Filter the table by one message receiver.
        """

        normalized_receiver = str(
            receiver
        ).strip()

        if not normalized_receiver:

            return

        index = (
            self.receiver_filter_combo.findData(
                normalized_receiver
            )
        )

        if index < 0:

            return

        self.filter_section.expand()

        self.receiver_filter_combo.setCurrentIndex(
            index
        )

    def _apply_chat_quick_filter(
        self,
        chat_name: str,
    ) -> None:
        """
        Filter the table by one message chat.
        """

        normalized_chat = str(
            chat_name
        ).strip()

        if not normalized_chat:

            return

        index = (
            self.chat_filter_combo.findData(
                normalized_chat
            )
        )

        if index < 0:

            return

        self.filter_section.expand()

        self.chat_filter_combo.setCurrentIndex(
            index
        )

    # ==========================================================
    # Investigation requests
    # ==========================================================

    def _request_create_evidence(
        self,
        message: dict[str, Any],
    ) -> None:
        """
        Request evidence creation from one message.
        """

        if not isinstance(
            message,
            dict,
        ):
            return

        self.create_evidence_requested.emit(
            dict(
                message
            )
        )

    def _request_create_entity(
        self,
        message: dict[str, Any],
    ) -> None:
        """
        Request entity creation from one message.
        """

        if not isinstance(
            message,
            dict,
        ):
            return

        self.create_entity_requested.emit(
            dict(
                message
            )
        )

    def _request_add_timeline_event(
        self,
        message: dict[str, Any],
    ) -> None:
        """
        Request creation of a timeline event from one message.
        """

        if not isinstance(
            message,
            dict,
        ):
            return

        self.add_timeline_event_requested.emit(
            dict(
                message
            )
        )

    def _request_ai_analysis(
        self,
        message: dict[str, Any],
    ) -> None:
        """
        Request AI analysis for one message.
        """

        if not isinstance(
            message,
            dict,
        ):
            return

        self.ai_analysis_requested.emit(
            dict(
                message
            )
        )

    # ==========================================================
    # Selection
    # ==========================================================

    def _show_selected_message(
        self,
        *_,
    ) -> None:
        """
        Display selected message in full.
        """

        selection_model = (
            self.message_table
            .selectionModel()
        )

        if selection_model is None:

            self._selected_message = None
            self.details_view.clear()

            return

        selected_rows = (
            selection_model
            .selectedRows()
        )

        if not selected_rows:

            self._selected_message = None
            self.details_view.clear()

            return

        proxy_index = selected_rows[
            0
        ]

        source_index = (
            self.proxy_model
            .mapToSource(
                proxy_index
            )
        )

        message = (
            self.message_model
            .get_message(
                source_index.row()
            )
        )

        if message is None:

            self._selected_message = None
            self.details_view.clear()

            return

        self._selected_message = message

        self._refresh_selected_message_details()

    def _refresh_selected_message_details(
        self,
    ) -> None:
        """
        Rebuild selected message details using active language.
        """

        if self._selected_message is None:

            return

        self.details_view.setPlainText(
            self._build_details_text(
                self._selected_message
            )
        )

    def _build_details_text(
        self,
        message: dict[str, Any],
    ) -> str:
        """
        Build readable full message details.
        """

        unavailable = self.translate(
            "messages.details.unavailable",
            default="Unavailable",
        )

        no_text = self.translate(
            "messages.details.no_text",
            default="No text content",
        )

        sent_at = str(
            message.get(
                "sent_at"
            )
            or ""
        )

        sender = str(
            message.get(
                "sender"
            )
            or ""
        )

        receiver = str(
            message.get(
                "receiver"
            )
            or ""
        )

        chat_name = str(
            message.get(
                "chat_name"
            )
            or ""
        )

        external_id = str(
            message.get(
                "external_id"
            )
            or ""
        )

        message_text = str(
            message.get(
                "text"
            )
            or ""
        )

        date_label = self.translate(
            "messages.details.date",
            default="Date",
        )

        sender_label = self.translate(
            "messages.details.sender",
            default="Sender",
        )

        receiver_label = self.translate(
            "messages.details.receiver",
            default="Receiver",
        )

        chat_label = self.translate(
            "messages.details.chat",
            default="Chat",
        )

        external_id_label = self.translate(
            "messages.details.external_id",
            default="External ID",
        )

        message_label = self.translate(
            "messages.details.message",
            default="Message",
        )

        return (
            f"{date_label}\n"
            f"{sent_at or unavailable}\n\n"
            f"{sender_label}\n"
            f"{sender or unavailable}\n\n"
            f"{receiver_label}\n"
            f"{receiver or unavailable}\n\n"
            f"{chat_label}\n"
            f"{chat_name or unavailable}\n\n"
            f"{external_id_label}\n"
            f"{external_id or unavailable}\n\n"
            f"{message_label}\n"
            f"{message_text or no_text}"
        )
"""
Application header bar.

Responsible for:

- displaying the current workspace title
- displaying application context
- displaying desktop version information
- displaying system status
- switching the active interface language
- reacting to language changes

Does NOT:

- execute business logic
- access repositories
- access services
- manage application pages
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QSignalBlocker,
    Qt,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.interface.desktop.localization import (
    TranslatableMixin,
)
from app.localization import (
    TranslationManager,
    get_translation_manager,
)


class HeaderBar(
    TranslatableMixin,
    QWidget,
):
    """
    Permanent top application header.

    The header uses the shared application TranslationManager
    and automatically updates its translated text whenever the
    active language changes.
    """

    def __init__(
        self,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        super().__init__()

        self._page_title_key: str | None = (
            "navigation.cases"
        )

        self._page_subtitle_key: str | None = (
            "header.investigation_workspace"
        )

        self._page_title_values: dict[str, Any] = {}
        self._page_subtitle_values: dict[str, Any] = {}

        self._status_key: str | None = (
            "header.system_ready"
        )

        self._status_values: dict[str, Any] = {}

        self.setObjectName(
            "HeaderBar"
        )

        self.setFixedHeight(
            72
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._setup_ui()

        active_translation_manager = (
            translation_manager
            if translation_manager is not None
            else get_translation_manager()
        )

        self.initialize_translations(
            active_translation_manager
        )

    # ==========================================================
    # UI setup
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Build the application header.
        """

        self.main_layout = QHBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            24,
            0,
            24,
            0,
        )

        self.main_layout.setSpacing(
            16
        )

        self._create_page_context()
        self._create_right_section()

    def _create_page_context(
        self,
    ) -> None:
        """
        Create the active page title and contextual subtitle.
        """

        self.page_context = QFrame(
            self
        )

        self.page_context.setObjectName(
            "HeaderPageContext"
        )

        context_layout = QVBoxLayout(
            self.page_context
        )

        context_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        context_layout.setSpacing(
            2
        )

        self.page_title = QLabel(
            self.page_context
        )

        self.page_title.setObjectName(
            "HeaderPageTitle"
        )

        self.page_subtitle = QLabel(
            self.page_context
        )

        self.page_subtitle.setObjectName(
            "HeaderPageSubtitle"
        )

        context_layout.addWidget(
            self.page_title
        )

        context_layout.addWidget(
            self.page_subtitle
        )

        self.main_layout.addWidget(
            self.page_context
        )

        self.main_layout.addStretch(
            1
        )

    def _create_right_section(
        self,
    ) -> None:
        """
        Create language, application status and version controls.
        """

        self.right_section = QFrame(
            self
        )

        self.right_section.setObjectName(
            "HeaderRightSection"
        )

        right_layout = QHBoxLayout(
            self.right_section
        )

        right_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        right_layout.setSpacing(
            12
        )

        self._create_language_selector(
            right_layout
        )

        self._create_system_status(
            right_layout
        )

        self.version_badge = QLabel(
            "v0.1.0",
            self.right_section,
        )

        self.version_badge.setObjectName(
            "HeaderVersionBadge"
        )

        self.version_badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        right_layout.addWidget(
            self.version_badge
        )

        self.main_layout.addWidget(
            self.right_section
        )

    def _create_language_selector(
        self,
        layout: QHBoxLayout,
    ) -> None:
        """
        Create the interface language selector.
        """

        self.language_section = QFrame(
            self.right_section
        )

        self.language_section.setObjectName(
            "HeaderLanguageSection"
        )

        language_layout = QHBoxLayout(
            self.language_section
        )

        language_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        language_layout.setSpacing(
            7
        )

        self.language_label = QLabel(
            self.language_section
        )

        self.language_label.setObjectName(
            "HeaderLanguageLabel"
        )

        self.language_selector = QComboBox(
            self.language_section
        )

        self.language_selector.setObjectName(
            "HeaderLanguageSelector"
        )

        self.language_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )

        self.language_selector.addItem(
            "",
            "en",
        )

        self.language_selector.addItem(
            "",
            "ru",
        )

        self.language_selector.addItem(
            "",
            "uk",
        )

        self.language_selector.currentIndexChanged.connect(
            self._on_language_selected
        )

        language_layout.addWidget(
            self.language_label
        )

        language_layout.addWidget(
            self.language_selector
        )

        layout.addWidget(
            self.language_section
        )

    def _create_system_status(
        self,
        layout: QHBoxLayout,
    ) -> None:
        """
        Create the system status indicator.
        """

        self.system_status = QFrame(
            self.right_section
        )

        self.system_status.setObjectName(
            "HeaderSystemStatus"
        )

        self.system_status.setProperty(
            "status",
            "ready",
        )

        status_layout = QHBoxLayout(
            self.system_status
        )

        status_layout.setContentsMargins(
            10,
            6,
            10,
            6,
        )

        status_layout.setSpacing(
            7
        )

        self.status_indicator = QLabel(
            "●",
            self.system_status,
        )

        self.status_indicator.setObjectName(
            "HeaderStatusIndicator"
        )

        self.status_indicator.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.status_text = QLabel(
            self.system_status
        )

        self.status_text.setObjectName(
            "HeaderStatusText"
        )

        status_layout.addWidget(
            self.status_indicator
        )

        status_layout.addWidget(
            self.status_text
        )

        layout.addWidget(
            self.system_status
        )

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply the active language to the header interface.
        """

        self.language_label.setText(
            self.translate(
                "header.language",
                default="Language",
            )
        )

        self._retranslate_language_selector()
        self._retranslate_page_context()
        self._retranslate_status()

    def _retranslate_language_selector(
        self,
    ) -> None:
        """
        Update language names and selected language.
        """

        signal_blocker = QSignalBlocker(
            self.language_selector
        )

        language_names = {
            "en": self.translate(
                "language.english",
                default="English",
            ),
            "ru": self.translate(
                "language.russian",
                default="Русский",
            ),
            "uk": self.translate(
                "language.ukrainian",
                default="Українська",
            ),
        }

        for index in range(
            self.language_selector.count()
        ):
            language_code = (
                self.language_selector.itemData(
                    index
                )
            )

            translated_name = language_names.get(
                language_code,
                str(language_code),
            )

            self.language_selector.setItemText(
                index,
                translated_name,
            )

        active_language = (
            self.translation_manager.current_language
        )

        active_language_code = getattr(
            active_language,
            "value",
            str(active_language),
        )

        active_index = (
            self.language_selector.findData(
                active_language_code
            )
        )

        if active_index >= 0:
            self.language_selector.setCurrentIndex(
                active_index
            )

        del signal_blocker

    def _retranslate_page_context(
        self,
    ) -> None:
        """
        Update page context when translation keys are active.
        """

        if self._page_title_key is not None:
            self.page_title.setText(
                self.translate(
                    self._page_title_key,
                    default=self._page_title_key,
                    **self._page_title_values,
                )
            )

        if self._page_subtitle_key is not None:
            subtitle = self.translate(
                self._page_subtitle_key,
                default=self._page_subtitle_key,
                **self._page_subtitle_values,
            )

            self.page_subtitle.setText(
                subtitle
            )

            self.page_subtitle.setVisible(
                bool(subtitle)
            )

    def _retranslate_status(
        self,
    ) -> None:
        """
        Update status text when a translation key is active.
        """

        if self._status_key is None:
            return

        self.status_text.setText(
            self.translate(
                self._status_key,
                default=self._status_key,
                **self._status_values,
            )
        )

    # ==========================================================
    # Language events
    # ==========================================================

    def _on_language_selected(
        self,
        index: int,
    ) -> None:
        """
        Change the active application language.
        """

        if index < 0:
            return

        language_code = (
            self.language_selector.itemData(
                index
            )
        )

        if language_code is None:
            return

        self.translation_manager.set_language(
            language_code
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def set_page_context(
        self,
        title: str,
        subtitle: str = "",
    ) -> None:
        """
        Update the active page context using literal text.

        Literal text is preserved during language changes.
        Use set_page_context_keys() for reactive translation.
        """

        self._page_title_key = None
        self._page_subtitle_key = None

        self._page_title_values = {}
        self._page_subtitle_values = {}

        self.page_title.setText(
            title
        )

        self.page_subtitle.setText(
            subtitle
        )

        self.page_subtitle.setVisible(
            bool(subtitle)
        )

    def set_page_context_keys(
        self,
        title_key: str,
        subtitle_key: str | None = None,
        *,
        title_values: dict[str, Any] | None = None,
        subtitle_values: dict[str, Any] | None = None,
    ) -> None:
        """
        Update page context using translation keys.

        The displayed title and subtitle will automatically update
        whenever the active language changes.
        """

        normalized_title_key = (
            title_key.strip()
        )

        if not normalized_title_key:
            raise ValueError(
                "title_key must not be empty."
            )

        normalized_subtitle_key = (
            subtitle_key.strip()
            if subtitle_key is not None
            else None
        )

        self._page_title_key = (
            normalized_title_key
        )

        self._page_subtitle_key = (
            normalized_subtitle_key
            if normalized_subtitle_key
            else None
        )

        self._page_title_values = dict(
            title_values or {}
        )

        self._page_subtitle_values = dict(
            subtitle_values or {}
        )

        self._retranslate_page_context()

        if self._page_subtitle_key is None:
            self.page_subtitle.clear()
            self.page_subtitle.setVisible(
                False
            )

    def set_status(
        self,
        text: str,
        status: str = "ready",
    ) -> None:
        """
        Update system status using literal text.

        Supported status values:

        - ready
        - working
        - warning
        - error

        Literal text is preserved during language changes.
        Use set_status_key() for reactive translation.
        """

        self._status_key = None
        self._status_values = {}

        self.status_text.setText(
            text
        )

        self._apply_status_style(
            status
        )

    def set_status_key(
        self,
        translation_key: str,
        status: str = "ready",
        **values: Any,
    ) -> None:
        """
        Update system status using a translation key.

        The displayed text will automatically update whenever the
        active language changes.
        """

        normalized_key = (
            translation_key.strip()
        )

        if not normalized_key:
            raise ValueError(
                "translation_key must not be empty."
            )

        self._status_key = normalized_key
        self._status_values = dict(
            values
        )

        self._retranslate_status()
        self._apply_status_style(
            status
        )

    def set_version(
        self,
        version: str,
    ) -> None:
        """
        Update displayed application version.
        """

        normalized_version = version.strip()

        if not normalized_version:
            return

        if not normalized_version.lower().startswith(
            "v"
        ):
            normalized_version = (
                f"v{normalized_version}"
            )

        self.version_badge.setText(
            normalized_version
        )

    # ==========================================================
    # Internal helpers
    # ==========================================================

    def _apply_status_style(
        self,
        status: str,
    ) -> None:
        """
        Normalize and apply the visual status property.
        """

        normalized_status = (
            status.strip().lower()
        )

        if normalized_status not in {
            "ready",
            "working",
            "warning",
            "error",
        }:
            normalized_status = "ready"

        self.system_status.setProperty(
            "status",
            normalized_status,
        )

        self.system_status.style().unpolish(
            self.system_status
        )

        self.system_status.style().polish(
            self.system_status
        )

        self.system_status.update()
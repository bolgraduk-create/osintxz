"""
Navigation panel.

Responsible for:

- application navigation UI
- displaying available desktop sections
- tracking the active navigation item
- emitting page change requests
- reacting to application language changes

Does NOT:

- execute business logic
- access database
- manage application pages directly
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
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


@dataclass(frozen=True)
class NavigationItem:
    """
    Navigation item configuration.
    """

    title_key: str
    default_title: str
    page_name: str
    symbol: str


class NavigationPanel(
    TranslatableMixin,
    QWidget,
):
    """
    Main left-side application navigation.

    The panel uses the shared application TranslationManager
    and automatically updates translated text whenever the
    active language changes.
    """

    page_changed = Signal(
        str
    )

    def __init__(
        self,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        super().__init__()

        self.setObjectName(
            "NavigationPanel"
        )

        self.setFixedWidth(
            240
        )

        self.buttons: dict[
            str,
            QPushButton,
        ] = {}

        self.navigation_items: dict[
            str,
            NavigationItem,
        ] = {}

        self._active_page: str | None = None

        self._setup_ui()

        active_translation_manager = (
            translation_manager
            if translation_manager is not None
            else get_translation_manager()
        )

        self.initialize_translations(
            active_translation_manager
        )

        self.set_active_page(
            "cases",
            emit_signal=False,
        )

    # ==========================================================
    # UI setup
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Build the navigation panel.
        """

        self.layout = QVBoxLayout(
            self
        )

        self.layout.setContentsMargins(
            14,
            18,
            14,
            16,
        )

        self.layout.setSpacing(
            8
        )

        self._create_brand_section()
        self._create_section_label()
        self._create_navigation_buttons()

        self.layout.addStretch(
            1
        )

        self._create_footer()

    def _create_brand_section(
        self,
    ) -> None:
        """
        Create compact application branding.
        """

        self.brand_container = QFrame(
            self
        )

        self.brand_container.setObjectName(
            "NavigationBrand"
        )

        brand_layout = QVBoxLayout(
            self.brand_container
        )

        brand_layout.setContentsMargins(
            12,
            10,
            12,
            18,
        )

        brand_layout.setSpacing(
            2
        )

        self.brand_title = QLabel(
            "OSINT",
            self.brand_container,
        )

        self.brand_title.setObjectName(
            "NavigationBrandTitle"
        )

        self.brand_subtitle = QLabel(
            self.brand_container
        )

        self.brand_subtitle.setObjectName(
            "NavigationBrandSubtitle"
        )

        brand_layout.addWidget(
            self.brand_title
        )

        brand_layout.addWidget(
            self.brand_subtitle
        )

        self.layout.addWidget(
            self.brand_container
        )

    def _create_section_label(
        self,
    ) -> None:
        """
        Create navigation section heading.
        """

        self.section_label = QLabel(
            self
        )

        self.section_label.setObjectName(
            "NavigationSectionLabel"
        )

        self.section_label.setContentsMargins(
            10,
            8,
            0,
            4,
        )

        self.layout.addWidget(
            self.section_label
        )

    def _create_navigation_buttons(
        self,
    ) -> None:
        """
        Create navigation buttons.
        """

        navigation_items = (
            NavigationItem(
                title_key="navigation.cases",
                default_title="Cases",
                page_name="cases",
                symbol="◫",
            ),
            NavigationItem(
                title_key="navigation.osint",
                default_title="OSINT Workspace",
                page_name="osint",
                symbol="⌖",
            ),
            NavigationItem(
                title_key="navigation.evidence",
                default_title="Evidence",
                page_name="evidence",
                symbol="◈",
            ),
            NavigationItem(
                title_key="navigation.entities",
                default_title="Entities",
                page_name="entities",
                symbol="◎",
            ),
            NavigationItem(
                title_key="navigation.reports",
                default_title="Reports",
                page_name="reports",
                symbol="▤",
            ),
            NavigationItem(
                title_key="navigation.ai",
                default_title="AI Assistant",
                page_name="ai",
                symbol="✦",
            ),
        )

        for item in navigation_items:
            button = self._create_navigation_button(
                item
            )

            self.navigation_items[
                item.page_name
            ] = item

            self.buttons[
                item.page_name
            ] = button

            self.layout.addWidget(
                button
            )

    def _create_navigation_button(
        self,
        item: NavigationItem,
    ) -> QPushButton:
        """
        Create one navigation button.
        """

        button = QPushButton(
            self
        )

        button.setObjectName(
            "NavigationButton"
        )

        button.setProperty(
            "pageName",
            item.page_name,
        )

        button.setCheckable(
            True
        )

        button.setAutoExclusive(
            True
        )

        button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        button.setMinimumHeight(
            46
        )

        button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        button.clicked.connect(
            lambda checked=False, name=item.page_name: (
                self.set_active_page(
                    name
                )
            )
        )

        return button

    def _create_footer(
        self,
    ) -> None:
        """
        Create navigation footer.
        """

        self.footer = QFrame(
            self
        )

        self.footer.setObjectName(
            "NavigationFooter"
        )

        footer_layout = QVBoxLayout(
            self.footer
        )

        footer_layout.setContentsMargins(
            10,
            12,
            10,
            4,
        )

        footer_layout.setSpacing(
            2
        )

        self.footer_status = QLabel(
            self.footer
        )

        self.footer_status.setObjectName(
            "NavigationFooterStatus"
        )

        self.footer_version = QLabel(
            self.footer
        )

        self.footer_version.setObjectName(
            "NavigationFooterVersion"
        )

        footer_layout.addWidget(
            self.footer_status
        )

        footer_layout.addWidget(
            self.footer_version
        )

        self.layout.addWidget(
            self.footer
        )

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply the active language to navigation controls.
        """

        self.brand_subtitle.setText(
            self.translate(
                "navigation.brand_subtitle",
                default="Intelligence Platform",
            )
        )

        self.section_label.setText(
            self.translate(
                "navigation.workspace_section",
                default="WORKSPACE",
            )
        )

        for (
            page_name,
            button,
        ) in self.buttons.items():
            item = self.navigation_items.get(
                page_name
            )

            if item is None:
                continue

            translated_title = self.translate(
                item.title_key,
                default=item.default_title,
            )

            button.setText(
                f"{item.symbol}    {translated_title}"
            )

        self.footer_status.setText(
            self.translate(
                "navigation.system_ready",
                default="●  System ready",
            )
        )

        self.footer_version.setText(
            self.translate(
                "navigation.desktop_workspace",
                default="Desktop Intelligence Workspace",
            )
        )

    # ==========================================================
    # Active page
    # ==========================================================

    def set_active_page(
        self,
        page_name: str,
        emit_signal: bool = True,
    ) -> None:
        """
        Set the active navigation page.
        """

        button = self.buttons.get(
            page_name
        )

        if button is None:
            return

        self._active_page = page_name

        button.setChecked(
            True
        )

        for (
            name,
            navigation_button,
        ) in self.buttons.items():
            is_active = (
                name == page_name
            )

            navigation_button.setProperty(
                "active",
                is_active,
            )

            navigation_button.style().unpolish(
                navigation_button
            )

            navigation_button.style().polish(
                navigation_button
            )

            navigation_button.update()

        if emit_signal:
            self.page_changed.emit(
                page_name
            )

    def active_page(
        self,
    ) -> str | None:
        """
        Return the currently selected page.
        """

        return self._active_page

    # ==========================================================
    # Qt lifecycle
    # ==========================================================

    def closeEvent(
        self,
        event,
    ) -> None:
        """
        Release translation subscriptions before closing.
        """

        self.dispose_translations()

        super().closeEvent(
            event
        )
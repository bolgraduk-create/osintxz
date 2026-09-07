"""
Global desktop application stylesheet.

Builds the global QSS theme used by all desktop interface
components.

Views should rely on:

- widget classes
- object names
- dynamic properties

instead of defining local stylesheets.
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)

from app.interface.desktop.theme.styles.navigation import (
    build_navigation_stylesheet,
)

from app.interface.desktop.theme.styles.workspace import (
    build_workspace_stylesheet,
)

from app.interface.desktop.theme.styles.header import (
    build_header_stylesheet,
)

from app.interface.desktop.theme.styles.cases import (
    build_cases_stylesheet,
)

from app.interface.desktop.theme.styles.cards import (
    build_cards_stylesheet,
)

from app.interface.desktop.theme.styles.sections import (
    build_sections_stylesheet,
)

from app.interface.desktop.theme.styles.empty_states import (
    build_empty_states_stylesheet,
)

from app.interface.desktop.theme.styles.badges import (
    build_badges_stylesheet,
)

from app.interface.desktop.theme.styles.search_boxes import (
    build_search_boxes_stylesheet,
)

from app.interface.desktop.theme.styles.toolbars import (
    build_toolbars_stylesheet,
)


def build_application_stylesheet() -> str:
    """
    Build and return the complete application stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Global
       ========================================================= */

    QWidget {{
        color: {colors.TEXT_PRIMARY};
        background-color: transparent;
        font-family: "{metrics.FONT_FAMILY}";
        font-size: {metrics.FONT_SIZE_NORMAL}px;
    }}

    QMainWindow,
    QDialog {{
        background-color: {colors.BACKGROUND};
    }}

    QWidget#applicationRoot,
    QWidget#pageRoot,
    QWidget#workspaceRoot {{
        background-color: {colors.BACKGROUND};
    }}

    /* =========================================================
       Labels
       ========================================================= */

    QLabel {{
        color: {colors.TEXT_SECONDARY};
        background-color: transparent;
    }}

    QLabel[role="pageTitle"] {{
        color: {colors.TEXT_PRIMARY};
        font-size: {metrics.FONT_SIZE_PAGE_TITLE}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel[role="title"] {{
        color: {colors.TEXT_PRIMARY};
        font-size: {metrics.FONT_SIZE_LARGE}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel[role="sectionTitle"] {{
        color: {colors.TEXT_PRIMARY};
        font-size: {metrics.FONT_SIZE_MEDIUM}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel[role="secondary"] {{
        color: {colors.TEXT_SECONDARY};
    }}

    QLabel[role="muted"] {{
        color: {colors.TEXT_MUTED};
        font-size: {metrics.FONT_SIZE_SMALL}px;
    }}

    QLabel[role="accent"] {{
        color: {colors.ACCENT_LIGHT};
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel[role="success"] {{
        color: {colors.SUCCESS};
    }}

    QLabel[role="warning"] {{
        color: {colors.WARNING};
    }}

    QLabel[role="danger"] {{
        color: {colors.DANGER};
    }}

    /* =========================================================
       Frames and surfaces
       ========================================================= */

    QFrame[role="panel"] {{
        background-color: {colors.PANEL};
        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_LARGE}px;
    }}

    QFrame[role="card"] {{
        background-color: {colors.SURFACE};
        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_CARD}px;
    }}

    QFrame[role="toolbar"] {{
        background-color: {colors.PANEL};
        border: none;
        border-bottom: 1px solid {colors.BORDER};
    }}

    QFrame[role="statisticsBar"] {{
        background-color: {colors.PANEL_SECONDARY};
        border: none;
        border-bottom: 1px solid {colors.BORDER};
    }}

    QFrame[role="detailsPanel"] {{
        background-color: {colors.PANEL};
        border: none;
        border-left: 1px solid {colors.BORDER};
    }}

    QFrame[role="separator"] {{
        background-color: {colors.BORDER};
        border: none;
        min-height: 1px;
        max-height: 1px;
    }}

    /* =========================================================
       Buttons
       ========================================================= */

    QPushButton {{
        min-height: {metrics.CONTROL_HEIGHT}px;
        padding: 0 12px;

        color: {colors.TEXT_SECONDARY};
        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER_LIGHT};
        border-radius: {metrics.RADIUS}px;
    }}

    QPushButton:hover {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SURFACE_HOVER};
        border-color: {colors.BORDER_HOVER};
    }}

    QPushButton:pressed {{
        background-color: {colors.SURFACE_PRESSED};
    }}

    QPushButton:focus {{
        border-color: {colors.BORDER_FOCUS};
    }}

    QPushButton:disabled {{
        color: {colors.TEXT_DISABLED};
        background-color: {colors.SURFACE_PRESSED};
        border-color: {colors.BORDER};
    }}

    QPushButton[role="primary"] {{
        color: {colors.TEXT_ON_ACCENT};
        background-color: {colors.ACCENT};
        border-color: {colors.ACCENT_BORDER};
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QPushButton[role="primary"]:hover {{
        background-color: {colors.ACCENT_HOVER};
        border-color: {colors.ACCENT_LIGHT};
    }}

    QPushButton[role="primary"]:pressed {{
        background-color: {colors.ACCENT};
    }}

    QPushButton[role="primary"]:disabled {{
        color: {colors.TEXT_DISABLED};
        background-color: {colors.SURFACE};
        border-color: {colors.BORDER};
    }}

    QPushButton[role="secondary"] {{
        color: {colors.TEXT_SECONDARY};
        background-color: {colors.SURFACE};
        border-color: {colors.BORDER_LIGHT};
    }}

    QPushButton[role="ghost"] {{
        color: {colors.TEXT_SECONDARY};
        background-color: transparent;
        border-color: transparent;
    }}

    QPushButton[role="ghost"]:hover {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SURFACE};
        border-color: {colors.BORDER};
    }}

    QPushButton[role="danger"] {{
        color: {colors.TEXT_ON_ACCENT};
        background-color: {colors.DANGER};
        border-color: {colors.DANGER};
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QPushButton[role="danger"]:hover {{
        background-color: {colors.DANGER_HOVER};
        border-color: {colors.DANGER_HOVER};
    }}

    QPushButton[role="icon"] {{
        min-width: {metrics.ICON_BUTTON_SIZE}px;
        max-width: {metrics.ICON_BUTTON_SIZE}px;

        min-height: {metrics.ICON_BUTTON_SIZE}px;
        max-height: {metrics.ICON_BUTTON_SIZE}px;

        padding: 0;

        font-size: {metrics.FONT_SIZE_LARGE}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    /* =========================================================
       Text inputs
       ========================================================= */

    QLineEdit,
    QTextEdit,
    QPlainTextEdit {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.INPUT_BACKGROUND};

        border: 1px solid {colors.BORDER_LIGHT};
        border-radius: {metrics.RADIUS}px;

        selection-color: {colors.TEXT_ON_ACCENT};
        selection-background-color: {colors.SELECTION};
    }}

    QLineEdit {{
        min-height: {metrics.CONTROL_HEIGHT}px;
        padding: 0 10px;
    }}

    QTextEdit,
    QPlainTextEdit {{
        padding: 8px;
    }}

    QLineEdit:hover,
    QTextEdit:hover,
    QPlainTextEdit:hover {{
        border-color: {colors.BORDER_HOVER};
    }}

    QLineEdit:focus,
    QTextEdit:focus,
    QPlainTextEdit:focus {{
        border-color: {colors.BORDER_FOCUS};
    }}

    QLineEdit:disabled,
    QTextEdit:disabled,
    QPlainTextEdit:disabled {{
        color: {colors.TEXT_DISABLED};
        background-color: {colors.SURFACE_PRESSED};
        border-color: {colors.BORDER};
    }}

    /* =========================================================
       Combo boxes
       ========================================================= */

    QComboBox {{
        min-height: {metrics.CONTROL_HEIGHT}px;
        padding: 0 30px 0 10px;

        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER_LIGHT};
        border-radius: {metrics.RADIUS}px;
    }}

    QComboBox:hover {{
        background-color: {colors.SURFACE_HOVER};
        border-color: {colors.BORDER_HOVER};
    }}

    QComboBox:focus {{
        border-color: {colors.BORDER_FOCUS};
    }}

    QComboBox:disabled {{
        color: {colors.TEXT_DISABLED};
        background-color: {colors.SURFACE_PRESSED};
        border-color: {colors.BORDER};
    }}

    QComboBox::drop-down {{
        width: 26px;
        border: none;
    }}

    QComboBox QAbstractItemView {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER_LIGHT};

        outline: none;
        selection-color: {colors.TEXT_PRIMARY};
        selection-background-color: {colors.SELECTION_INACTIVE};
    }}

    /* =========================================================
       Checkboxes and radio buttons
       ========================================================= */

    QCheckBox,
    QRadioButton {{
        color: {colors.TEXT_SECONDARY};
        spacing: 8px;
    }}

    QCheckBox:hover,
    QRadioButton:hover {{
        color: {colors.TEXT_PRIMARY};
    }}

    QCheckBox:disabled,
    QRadioButton:disabled {{
        color: {colors.TEXT_DISABLED};
    }}

    /* =========================================================
       Tabs
       ========================================================= */

    QTabWidget::pane {{
        background-color: {colors.BACKGROUND};
        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_LARGE}px;
        top: -1px;
    }}

    QTabBar::tab {{
        min-height: 34px;
        padding: 0 16px;

        color: {colors.TEXT_MUTED};
        background-color: transparent;

        border: none;
        border-bottom: 2px solid transparent;
    }}

    QTabBar::tab:hover {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SURFACE};
    }}

    QTabBar::tab:selected {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.PANEL};
        border-bottom-color: {colors.ACCENT_LIGHT};
    }}

    QTabBar::tab:disabled {{
        color: {colors.TEXT_DISABLED};
    }}

    /* =========================================================
       Tables and lists
       ========================================================= */

    QTableView,
    QTreeView,
    QListView,
    QListWidget,
    QTreeWidget,
    QTableWidget {{
        color: {colors.TEXT_SECONDARY};
        background-color: {colors.BACKGROUND_DEEP};

        alternate-background-color: {colors.PANEL_SECONDARY};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_LARGE}px;

        gridline-color: {colors.BORDER};
        outline: none;

        selection-color: {colors.TEXT_PRIMARY};
        selection-background-color: {colors.SELECTION_INACTIVE};
    }}

    QTableView::item,
    QTreeView::item,
    QListView::item {{
        min-height: 32px;
        padding: 4px 8px;
        border: none;
    }}

    QTableView::item:hover,
    QTreeView::item:hover,
    QListView::item:hover {{
        background-color: {colors.SURFACE};
    }}

    QHeaderView::section {{
        min-height: 34px;
        padding: 0 8px;

        color: {colors.TEXT_SECONDARY};
        background-color: {colors.PANEL};

        border: none;
        border-right: 1px solid {colors.BORDER};
        border-bottom: 1px solid {colors.BORDER};

        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    /* =========================================================
       Menus
       ========================================================= */

    QMenu {{
        color: {colors.TEXT_SECONDARY};
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER_LIGHT};
        border-radius: {metrics.RADIUS}px;

        padding: 6px;
    }}

    QMenu::item {{
        min-height: 28px;
        padding: 4px 28px 4px 10px;
        border-radius: {metrics.RADIUS_SMALL}px;
    }}

    QMenu::item:selected {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SELECTION_INACTIVE};
    }}

    QMenu::item:disabled {{
        color: {colors.TEXT_DISABLED};
    }}

    QMenu::separator {{
        height: 1px;
        margin: 5px 8px;
        background-color: {colors.BORDER};
    }}

    QMenuBar {{
        color: {colors.TEXT_SECONDARY};
        background-color: {colors.PANEL};
        border-bottom: 1px solid {colors.BORDER};
    }}

    QMenuBar::item {{
        padding: 6px 10px;
        background-color: transparent;
    }}

    QMenuBar::item:selected {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SURFACE};
    }}

    /* =========================================================
       Scrollbars
       ========================================================= */

    QScrollBar:vertical {{
        width: 12px;
        margin: 0;
        background-color: {colors.SCROLLBAR_BACKGROUND};
        border: none;
    }}

    QScrollBar::handle:vertical {{
        min-height: 28px;
        margin: 2px;
        background-color: {colors.SCROLLBAR_HANDLE};
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {colors.SCROLLBAR_HANDLE_HOVER};
    }}

    QScrollBar:add-line:vertical,
    QScrollBar:sub-line:vertical,
    QScrollBar:add-page:vertical,
    QScrollBar:sub-page:vertical {{
        height: 0;
        background: none;
    }}

    QScrollBar:horizontal {{
        height: 12px;
        margin: 0;
        background-color: {colors.SCROLLBAR_BACKGROUND};
        border: none;
    }}

    QScrollBar::handle:horizontal {{
        min-width: 28px;
        margin: 2px;
        background-color: {colors.SCROLLBAR_HANDLE};
        border-radius: 4px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {colors.SCROLLBAR_HANDLE_HOVER};
    }}

    QScrollBar:add-line:horizontal,
    QScrollBar:sub-line:horizontal,
    QScrollBar:add-page:horizontal,
    QScrollBar:sub-page:horizontal {{
        width: 0;
        background: none;
    }}

    /* =========================================================
       Splitters
       ========================================================= */

    QSplitter::handle {{
        background-color: {colors.BORDER};
    }}

    QSplitter::handle:horizontal {{
        width: 1px;
    }}

    QSplitter::handle:vertical {{
        height: 1px;
    }}

    QSplitter::handle:hover {{
        background-color: {colors.ACCENT_LIGHT};
    }}

    /* =========================================================
       Tooltips
       ========================================================= */

    QToolTip {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER_LIGHT};
        border-radius: {metrics.RADIUS_SMALL}px;

        padding: 5px 8px;
    }}

    /* =========================================================
       Progress bars
       ========================================================= */

    QProgressBar {{
        min-height: 8px;
        max-height: 8px;

        color: transparent;
        background-color: {colors.SURFACE_PRESSED};

        border: none;
        border-radius: 4px;
    }}

    QProgressBar::chunk {{
        background-color: {colors.ACCENT};
        border-radius: 4px;
    }}

    /* =========================================================
       Status bar
       ========================================================= */

    QStatusBar {{
        color: {colors.TEXT_MUTED};
        background-color: {colors.PANEL_SECONDARY};
        border-top: 1px solid {colors.BORDER};
    }}

    QStatusBar::item {{
        border: none;
    }}

    /* =========================================================
       Existing entity graph compatibility
       ========================================================= */

    QFrame#graphToolbar {{
        background-color: {colors.PANEL};
        border: none;
        border-bottom: 1px solid {colors.BORDER};
    }}

    QLabel#graphTitle {{
        color: {colors.TEXT_PRIMARY};
        font-size: {metrics.FONT_SIZE_LARGE}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLineEdit#graphSearchInput {{
        min-height: {metrics.CONTROL_HEIGHT}px;
        padding: 0 10px;

        color: {colors.TEXT_PRIMARY};
        background-color: {colors.INPUT_BACKGROUND};

        border: 1px solid {colors.BORDER_LIGHT};
        border-radius: {metrics.RADIUS}px;
    }}

    QLineEdit#graphSearchInput:focus {{
        border-color: {colors.BORDER_FOCUS};
    }}

    QPushButton#graphToolbarButton,
    QPushButton#graphSecondaryButton {{
        min-height: {metrics.CONTROL_HEIGHT}px;
        padding: 0 12px;

        color: {colors.TEXT_SECONDARY};
        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER_LIGHT};
        border-radius: {metrics.RADIUS}px;
    }}

    QPushButton#graphToolbarButton:hover,
    QPushButton#graphSecondaryButton:hover {{
        background-color: {colors.SURFACE_HOVER};
        border-color: {colors.BORDER_HOVER};
    }}

    QPushButton#graphZoomButton {{
        min-width: {metrics.ICON_BUTTON_SIZE}px;
        max-width: {metrics.ICON_BUTTON_SIZE}px;

        min-height: {metrics.ICON_BUTTON_SIZE}px;
        max-height: {metrics.ICON_BUTTON_SIZE}px;

        padding: 0;

        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER_LIGHT};
        border-radius: {metrics.RADIUS}px;

        font-size: {metrics.FONT_SIZE_LARGE}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QPushButton#graphZoomButton:hover {{
        background-color: {colors.SURFACE_HOVER};
    }}

    QLabel#graphZoomLabel {{
        color: {colors.TEXT_SECONDARY};
        font-size: {metrics.FONT_SIZE_SMALL}px;
    }}

    QComboBox#graphLayoutSelector {{
        min-height: {metrics.CONTROL_HEIGHT}px;
        padding: 0 30px 0 10px;

        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER_LIGHT};
        border-radius: {metrics.RADIUS}px;
    }}

    QFrame#graphStatisticsBar {{
        background-color: {colors.PANEL_SECONDARY};
        border: none;
        border-bottom: 1px solid {colors.BORDER};
    }}

    QLabel#graphStatisticLabel {{
        color: {colors.TEXT_SECONDARY};
        font-size: {metrics.FONT_SIZE_SMALL}px;
    }}

    QLabel#graphStatusLabel {{
        color: {colors.TEXT_MUTED};
        font-size: {metrics.FONT_SIZE_SMALL}px;
    }}

    QFrame#graphContainer {{
        background-color: {colors.GRAPH_BACKGROUND};
    }}

    QFrame#graphDetailsPanel {{
        background-color: {colors.PANEL};
        border: none;
        border-left: 1px solid {colors.BORDER};
    }}

    QLabel#graphDetailsTitle {{
        color: {colors.TEXT_PRIMARY};
        font-size: 17px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#graphDetailsType {{
        color: {colors.ACCENT_LIGHT};
        font-size: {metrics.FONT_SIZE_SMALL}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#graphDetailsBody {{
        color: {colors.TEXT_SECONDARY};
        font-size: {metrics.FONT_SIZE_NORMAL}px;
    }}

    QPushButton#graphPrimaryButton {{
        min-height: {metrics.CONTROL_HEIGHT_LARGE}px;
        padding: 0 12px;

        color: {colors.TEXT_ON_ACCENT};
        background-color: {colors.ACCENT};

        border: 1px solid {colors.ACCENT_BORDER};
        border-radius: {metrics.RADIUS}px;

        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QPushButton#graphPrimaryButton:hover {{
        background-color: {colors.ACCENT_HOVER};
    }}

    QPushButton#graphPrimaryButton:disabled {{
        color: {colors.TEXT_DISABLED};
        background-color: {colors.SURFACE};
        border-color: {colors.BORDER};
    }}

    QSplitter#graphSplitter::handle {{
        width: 1px;
        background-color: {colors.BORDER};
    }}
    """ + (
         build_workspace_stylesheet()
        + build_navigation_stylesheet()
        + build_header_stylesheet()
        + build_cases_stylesheet()
        + build_cards_stylesheet()
        + build_sections_stylesheet()
        + build_empty_states_stylesheet()
        + build_badges_stylesheet()
        + build_search_boxes_stylesheet()
        + build_toolbars_stylesheet()
    )

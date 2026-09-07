"""
Cases workspace stylesheet.

Contains QSS rules for:

- cases page toolbar
- investigation summary bar
- cases search input
- investigation cards
- investigation status badges
- empty state
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)


def build_cases_stylesheet() -> str:
    """
    Build and return cases-specific stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Cases workspace
       ========================================================= */

    QWidget#CasesPage {{
        background-color: transparent;
        border: none;
    }}

    QFrame#CasesToolbar,
    QFrame#CasesTitleContainer {{
        background-color: transparent;
        border: none;
    }}

    QLabel#CasesPageTitle {{
        color: {colors.TEXT_PRIMARY};
        background-color: transparent;

        font-size: 24px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#CasesPageDescription {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        font-size: 13px;
    }}

    /* =========================================================
       Toolbar actions
       ========================================================= */

    QPushButton#CasesRefreshButton {{
        min-height: 38px;
        padding: 0 16px;

        color: {colors.TEXT_SECONDARY};
        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS}px;

        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QPushButton#CasesRefreshButton:hover {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SELECTION_INACTIVE};
        border-color: {colors.ACCENT_BORDER};
    }}

    QPushButton#CasesRefreshButton:pressed {{
        background-color: {colors.BACKGROUND_DEEP};
    }}

    QPushButton#CasesCreateButton {{
        min-height: 38px;
        padding: 0 18px;

        color: {colors.TEXT_PRIMARY};
        background-color: {colors.ACCENT_BORDER};

        border: 1px solid {colors.ACCENT_LIGHT};
        border-radius: {metrics.RADIUS}px;

        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QPushButton#CasesCreateButton:hover {{
        background-color: {colors.ACCENT_LIGHT};
    }}

    QPushButton#CasesCreateButton:pressed {{
        background-color: {colors.ACCENT_BORDER};
    }}

    /* =========================================================
       Summary and search
       ========================================================= */

    QFrame#CasesSummaryBar {{
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_LARGE}px;
    }}

    QLabel#CasesCountLabel {{
        color: {colors.TEXT_SECONDARY};
        background-color: transparent;

        font-size: 13px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLineEdit#CasesSearchInput {{
        min-height: 34px;
        padding: 0 12px;

        color: {colors.TEXT_PRIMARY};
        background-color: {colors.BACKGROUND_DEEP};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS}px;

        selection-background-color: {colors.ACCENT_BORDER};
    }}

    QLineEdit#CasesSearchInput:hover {{
        border-color: {colors.ACCENT_BORDER};
    }}

    QLineEdit#CasesSearchInput:focus {{
        border-color: {colors.ACCENT_LIGHT};
    }}

    /* =========================================================
       Cases list
       ========================================================= */

    QListWidget#CasesList {{
        background-color: transparent;
        border: none;
        outline: none;
    }}

    QListWidget#CasesList::item {{
        background-color: transparent;
        border: none;
        padding: 0;
    }}

    QListWidget#CasesList::item:selected {{
        background-color: transparent;
        border: none;
    }}

    /* =========================================================
       Case card
       ========================================================= */

    QFrame#CaseCard {{
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_LARGE}px;
    }}

    QFrame#CaseCard:hover {{
        background-color: {colors.SURFACE};
        border-color: {colors.ACCENT_BORDER};
    }}

    QFrame#CaseCardAccent {{
        background-color: {colors.ACCENT_LIGHT};

        border: none;
        border-radius: 2px;
    }}

    QFrame#CaseCardContent,
    QFrame#CaseCardActions {{
        background-color: transparent;
        border: none;
    }}

    QLabel#CaseCardTitle {{
        color: {colors.TEXT_PRIMARY};
        background-color: transparent;

        font-size: 17px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#CaseCardDescription {{
        color: {colors.TEXT_SECONDARY};
        background-color: transparent;

        font-size: 13px;
    }}

    QLabel#CaseCardMetadata {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        font-size: 12px;
    }}

    /* =========================================================
       Case status
       ========================================================= */

    QLabel#CaseCardStatus {{
        min-width: 64px;
        min-height: 24px;
        padding: 0 9px;

        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER};
        border-radius: 12px;

        font-size: 11px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#CaseCardStatus[status="active"] {{
        color: {colors.SUCCESS};
        border-color: {colors.SUCCESS};
    }}

    QLabel#CaseCardStatus[status="closed"] {{
        color: {colors.TEXT_MUTED};
        border-color: {colors.BORDER};
    }}

    QLabel#CaseCardStatus[status="archived"] {{
        color: {colors.WARNING};
        border-color: {colors.WARNING};
    }}

    /* =========================================================
       Case actions
       ========================================================= */

    QPushButton#CaseCardOpenButton {{
        min-height: 34px;
        padding: 0 14px;

        color: {colors.TEXT_SECONDARY};
        background-color: {colors.BACKGROUND_DEEP};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS}px;

        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QPushButton#CaseCardOpenButton:hover {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SELECTION_INACTIVE};
        border-color: {colors.ACCENT_LIGHT};
    }}

    QPushButton#CaseCardOpenButton:pressed {{
        background-color: {colors.BACKGROUND_DEEP};
    }}

    /* =========================================================
       Empty state
       ========================================================= */

    QFrame#CasesEmptyState {{
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_LARGE}px;
    }}

    QLabel#CasesEmptyTitle {{
        color: {colors.TEXT_PRIMARY};
        background-color: transparent;

        font-size: 18px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#CasesEmptyDescription {{
        max-width: 430px;

        color: {colors.TEXT_MUTED};
        background-color: transparent;

        font-size: 13px;
    }}
    """
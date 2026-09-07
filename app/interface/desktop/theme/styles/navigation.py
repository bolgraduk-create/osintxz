"""
Navigation panel stylesheet.

Contains QSS rules for:

- navigation container
- application branding
- navigation section labels
- navigation buttons
- active page state
- navigation footer
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)


def build_navigation_stylesheet() -> str:
    """
    Build and return navigation-specific stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Navigation panel
       ========================================================= */

    QFrame#NavigationContainer,
    QWidget#NavigationPanel,
    QWidget#MainNavigation {{
        background-color: {colors.BACKGROUND_DEEP};
        border: none;
    }}

    /* =========================================================
       Navigation branding
       ========================================================= */

    QFrame#NavigationBrand {{
        background-color: transparent;
        border: none;
    }}

    QLabel#NavigationBrandTitle {{
        color: {colors.TEXT_PRIMARY};
        background-color: transparent;

        font-size: {metrics.FONT_SIZE_PAGE_TITLE}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#NavigationBrandSubtitle {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        font-size: {metrics.FONT_SIZE_SMALL}px;
    }}

    /* =========================================================
       Navigation section label
       ========================================================= */

    QLabel#NavigationSectionLabel {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        font-size: {metrics.FONT_SIZE_SMALL}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    /* =========================================================
       Navigation buttons
       ========================================================= */

    QPushButton#NavigationButton {{
        min-height: 46px;
        padding: 0 14px;

        color: {colors.TEXT_SECONDARY};
        background-color: transparent;

        border: 1px solid transparent;
        border-radius: {metrics.RADIUS}px;

        text-align: left;

        font-size: {metrics.FONT_SIZE_NORMAL}px;
        font-weight: {metrics.FONT_WEIGHT_NORMAL};
    }}

    QPushButton#NavigationButton:hover {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SURFACE};

        border-color: {colors.BORDER};
    }}

    QPushButton#NavigationButton:pressed {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SURFACE_PRESSED};

        border-color: {colors.BORDER_LIGHT};
    }}

    QPushButton#NavigationButton:checked,
    QPushButton#NavigationButton[active="true"] {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SELECTION_INACTIVE};

        border-color: {colors.BORDER_FOCUS};

        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QPushButton#NavigationButton:checked:hover,
    QPushButton#NavigationButton[active="true"]:hover {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SELECTION};

        border-color: {colors.ACCENT_LIGHT};
    }}

    QPushButton#NavigationButton:focus {{
        border-color: {colors.BORDER_FOCUS};
    }}

    /* =========================================================
       Navigation footer
       ========================================================= */

    QFrame#NavigationFooter {{
        background-color: transparent;

        border: none;
        border-top: 1px solid {colors.BORDER};
    }}

    QLabel#NavigationFooterStatus {{
        color: {colors.SUCCESS};
        background-color: transparent;

        font-size: {metrics.FONT_SIZE_SMALL}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#NavigationFooterVersion {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        font-size: {metrics.FONT_SIZE_SMALL}px;
    }}
    """
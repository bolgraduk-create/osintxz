"""
Reusable toolbar component stylesheet.

Contains QSS rules for:

- default toolbars
- panel toolbars
- transparent toolbars
- compact toolbars
- toolbar content areas
- toolbar separators
- buttons placed inside toolbars
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)


def build_toolbars_stylesheet() -> str:
    """
    Build and return reusable toolbar stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Base toolbar
       ========================================================= */

    QFrame#Toolbar {{
        min-height: 42px;

        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_MEDIUM}px;
    }}

    QFrame#ToolbarLeft,
    QFrame#ToolbarCenter,
    QFrame#ToolbarRight {{
        background-color: transparent;
        border: none;
    }}

    /* =========================================================
       Toolbar variants
       ========================================================= */

    QFrame#Toolbar[variant="default"] {{
        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER};
    }}

    QFrame#Toolbar[variant="panel"] {{
        background-color: {colors.PANEL};

        border: 1px solid {colors.ACCENT_BORDER};
    }}

    QFrame#Toolbar[variant="transparent"] {{
        background-color: transparent;

        border: none;
    }}

    QFrame#Toolbar[variant="compact"] {{
        min-height: 34px;

        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_SMALL}px;
    }}

    /* =========================================================
       Separator
       ========================================================= */

    QFrame#ToolbarSeparator {{
        min-width: 1px;
        max-width: 1px;
        min-height: 22px;
        max-height: 22px;

        background-color: {colors.BORDER};

        border: none;
    }}

    /* =========================================================
       Buttons inside toolbar
       ========================================================= */

    QFrame#Toolbar QPushButton {{
        min-height: 32px;

        color: {colors.TEXT_SECONDARY};
        background-color: transparent;

        border: 1px solid transparent;
        border-radius: {metrics.RADIUS_SMALL}px;

        padding: 0 12px;

        font-size: 12px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QFrame#Toolbar QPushButton:hover {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SELECTION_INACTIVE};

        border-color: {colors.BORDER};
    }}

    QFrame#Toolbar QPushButton:pressed {{
        color: {colors.ACCENT_LIGHT};
        background-color: {colors.PANEL};

        border-color: {colors.ACCENT_BORDER};
    }}

    QFrame#Toolbar QPushButton:disabled {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        border-color: transparent;
    }}

    QFrame#Toolbar[variant="compact"] QPushButton {{
        min-height: 28px;

        padding: 0 9px;

        font-size: 11px;
    }}

    /* =========================================================
       Combo boxes inside toolbar
       ========================================================= */

    QFrame#Toolbar QComboBox {{
        min-height: 32px;

        color: {colors.TEXT_SECONDARY};
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_SMALL}px;

        padding: 0 10px;

        font-size: 12px;
    }}

    QFrame#Toolbar QComboBox:hover {{
        color: {colors.TEXT_PRIMARY};

        border-color: {colors.ACCENT_BORDER};
    }}

    QFrame#Toolbar QComboBox:focus {{
        color: {colors.TEXT_PRIMARY};

        border-color: {colors.ACCENT_LIGHT};
    }}

    QFrame#Toolbar QComboBox:disabled {{
        color: {colors.TEXT_MUTED};
        background-color: {colors.SURFACE};

        border-color: {colors.BORDER};
    }}

    QFrame#Toolbar[variant="compact"] QComboBox {{
        min-height: 28px;

        font-size: 11px;
    }}
    """
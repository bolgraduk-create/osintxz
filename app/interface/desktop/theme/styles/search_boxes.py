"""
Reusable search box component stylesheet.

Contains QSS rules for:

- default search boxes
- focused search boxes
- disabled search boxes
- busy search boxes
- search input
- marker
- clear button
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)


def build_search_boxes_stylesheet() -> str:
    """
    Build and return search box stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Search box container
       ========================================================= */

    QFrame#SearchBox {{
        min-height: 40px;

        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_MEDIUM}px;
    }}

    QFrame#SearchBox:hover {{
        border-color: {colors.ACCENT_BORDER};
    }}

    QFrame#SearchBox[focused="true"] {{
        background-color: {colors.PANEL};

        border: 1px solid {colors.ACCENT_LIGHT};
    }}

    QFrame#SearchBox[busy="true"] {{
        border-color: {colors.ACCENT_BORDER};
    }}

    QFrame#SearchBox:disabled {{
        background-color: {colors.PANEL};
        border-color: {colors.BORDER};
    }}

    /* =========================================================
       Input
       ========================================================= */

    QLineEdit#SearchBoxInput {{
        min-height: 36px;

        color: {colors.TEXT_PRIMARY};
        background-color: transparent;

        border: none;
        padding: 0;

        font-size: 13px;
        font-weight: {metrics.FONT_WEIGHT_NORMAL};

        selection-color: {colors.TEXT_PRIMARY};
        selection-background-color: {colors.SELECTION_INACTIVE};
    }}

    QLineEdit#SearchBoxInput:disabled {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;
    }}

    /* =========================================================
       Search marker
       ========================================================= */

    QLabel#SearchBoxMarker {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        border: none;

        font-size: 18px;
        font-weight: {metrics.FONT_WEIGHT_NORMAL};
    }}

    QFrame#SearchBox[focused="true"] QLabel#SearchBoxMarker {{
        color: {colors.ACCENT_LIGHT};
    }}

    QFrame#SearchBox:disabled QLabel#SearchBoxMarker {{
        color: {colors.TEXT_MUTED};
    }}

    /* =========================================================
       Busy indicator
       ========================================================= */

    QLabel#SearchBoxBusy {{
        color: {colors.ACCENT_LIGHT};
        background-color: transparent;

        border: none;

        font-size: 18px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    /* =========================================================
       Clear button
       ========================================================= */

    QPushButton#SearchBoxClearButton {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        border: none;
        border-radius: {metrics.RADIUS_SMALL}px;

        padding: 0;

        font-size: 18px;
        font-weight: {metrics.FONT_WEIGHT_NORMAL};
    }}

    QPushButton#SearchBoxClearButton:hover {{
        color: {colors.TEXT_PRIMARY};
        background-color: {colors.SELECTION_INACTIVE};
    }}

    QPushButton#SearchBoxClearButton:pressed {{
        color: {colors.ACCENT_LIGHT};
        background-color: {colors.PANEL};
    }}

    QPushButton#SearchBoxClearButton:disabled {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;
    }}
    """
"""
Application header stylesheet.

Contains QSS rules for:

- global desktop header
- active page title
- contextual subtitle
- system status badge
- application version badge
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)


def build_header_stylesheet() -> str:
    """
    Build and return header-specific stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Application header
       ========================================================= */

    QWidget#ApplicationHeader,
    QWidget#HeaderBar {{
        background-color: {colors.PANEL};
        border: none;
        border-bottom: 1px solid {colors.BORDER};
    }}

    QFrame#HeaderPageContext,
    QFrame#HeaderRightSection {{
        background-color: transparent;
        border: none;
    }}

    /* =========================================================
       Page context
       ========================================================= */

    QLabel#HeaderPageTitle {{
        color: {colors.TEXT_PRIMARY};
        background-color: transparent;

        font-size: {metrics.FONT_SIZE_LARGE}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#HeaderPageSubtitle {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        font-size: {metrics.FONT_SIZE_SMALL}px;
        font-weight: {metrics.FONT_WEIGHT_NORMAL};
    }}

    /* =========================================================
       System status
       ========================================================= */

    QFrame#HeaderSystemStatus {{
        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_LARGE}px;
    }}

    QLabel#HeaderStatusIndicator {{
        color: {colors.SUCCESS};
        background-color: transparent;

        font-size: {metrics.FONT_SIZE_SMALL}px;
    }}

    QLabel#HeaderStatusText {{
        color: {colors.TEXT_SECONDARY};
        background-color: transparent;

        font-size: {metrics.FONT_SIZE_SMALL}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QFrame#HeaderSystemStatus[status="ready"] {{
        background-color: {colors.SURFACE};
        border-color: {colors.BORDER};
    }}

    QFrame#HeaderSystemStatus[status="ready"]
    QLabel#HeaderStatusIndicator {{
        color: {colors.SUCCESS};
    }}

    QFrame#HeaderSystemStatus[status="working"] {{
        background-color: {colors.SELECTION_INACTIVE};
        border-color: {colors.ACCENT_BORDER};
    }}

    QFrame#HeaderSystemStatus[status="working"]
    QLabel#HeaderStatusIndicator {{
        color: {colors.ACCENT_LIGHT};
    }}

    QFrame#HeaderSystemStatus[status="warning"] {{
        background-color: {colors.SURFACE};
        border-color: {colors.WARNING};
    }}

    QFrame#HeaderSystemStatus[status="warning"]
    QLabel#HeaderStatusIndicator {{
        color: {colors.WARNING};
    }}

    QFrame#HeaderSystemStatus[status="error"] {{
        background-color: {colors.SURFACE};
        border-color: {colors.DANGER};
    }}

    QFrame#HeaderSystemStatus[status="error"]
    QLabel#HeaderStatusIndicator {{
        color: {colors.DANGER};
    }}

    /* =========================================================
       Version badge
       ========================================================= */

    QLabel#HeaderVersionBadge {{
        min-width: 54px;
        min-height: 28px;
        padding: 0 8px;

        color: {colors.TEXT_MUTED};
        background-color: {colors.BACKGROUND_DEEP};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS}px;

        font-size: {metrics.FONT_SIZE_SMALL}px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}
    """
"""
Reusable card component stylesheet.

Contains QSS rules for:

- standard cards
- elevated cards
- interactive cards
- semantic card variants
- card headers
- card content
- card action containers
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)


def build_cards_stylesheet() -> str:
    """
    Build and return reusable card stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Base card
       ========================================================= */

    QFrame#Card {{
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_LARGE}px;
    }}

    QFrame#CardHeader,
    QFrame#CardTitleContainer,
    QFrame#CardActions,
    QFrame#CardContent {{
        background-color: transparent;
        border: none;
    }}

    /* =========================================================
       Card typography
       ========================================================= */

    QLabel#CardTitle {{
        color: {colors.TEXT_PRIMARY};
        background-color: transparent;

        font-size: 16px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#CardSubtitle {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        font-size: 12px;
        font-weight: {metrics.FONT_WEIGHT_NORMAL};
    }}

    /* =========================================================
       Card variants
       ========================================================= */

    QFrame#Card[variant="default"] {{
        background-color: {colors.PANEL};
        border-color: {colors.BORDER};
    }}

    QFrame#Card[variant="elevated"] {{
        background-color: {colors.SURFACE};
        border-color: {colors.ACCENT_BORDER};
    }}

    QFrame#Card[variant="interactive"] {{
        background-color: {colors.PANEL};
        border-color: {colors.BORDER};
    }}

    QFrame#Card[variant="interactive"]:hover {{
        background-color: {colors.SURFACE};
        border-color: {colors.ACCENT_LIGHT};
    }}

    QFrame#Card[variant="danger"] {{
        background-color: {colors.PANEL};
        border-color: {colors.DANGER};
    }}

    QFrame#Card[variant="warning"] {{
        background-color: {colors.PANEL};
        border-color: {colors.WARNING};
    }}

    QFrame#Card[variant="success"] {{
        background-color: {colors.PANEL};
        border-color: {colors.SUCCESS};
    }}

    /* =========================================================
       Compact card
       ========================================================= */

    QFrame#Card[compact="true"] QLabel#CardTitle {{
        font-size: 14px;
    }}

    QFrame#Card[compact="true"] QLabel#CardSubtitle {{
        font-size: 11px;
    }}
    """
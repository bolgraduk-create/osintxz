"""
Reusable section component stylesheet.

Contains QSS rules for:

- standard sections
- separated sections
- panel sections
- compact sections
- section headers
- section actions
- section content areas
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)


def build_sections_stylesheet() -> str:
    """
    Build and return reusable section stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Base section
       ========================================================= */

    QFrame#Section {{
        background-color: transparent;
        border: none;
    }}

    QFrame#SectionHeader,
    QFrame#SectionTitleContainer,
    QFrame#SectionActions,
    QFrame#SectionContent {{
        background-color: transparent;
        border: none;
    }}

    /* =========================================================
       Section typography
       ========================================================= */

    QLabel#SectionTitle {{
        color: {colors.TEXT_PRIMARY};
        background-color: transparent;

        font-size: 18px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#SectionDescription {{
        color: {colors.TEXT_MUTED};
        background-color: transparent;

        font-size: 12px;
        font-weight: {metrics.FONT_WEIGHT_NORMAL};
    }}

    /* =========================================================
       Section variants
       ========================================================= */

    QFrame#Section[variant="default"] {{
        background-color: transparent;
        border: none;
    }}

    QFrame#Section[variant="separated"] {{
        background-color: transparent;

        border: none;
        border-bottom: 1px solid {colors.BORDER};
    }}

    QFrame#Section[variant="panel"] {{
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_LARGE}px;
    }}

    QFrame#Section[variant="panel"] > QFrame#SectionHeader {{
        padding: 16px 16px 0 16px;
    }}

    QFrame#Section[variant="panel"] > QFrame#SectionContent {{
        padding: 0 16px 16px 16px;
    }}

    QFrame#Section[variant="compact"] QLabel#SectionTitle {{
        font-size: 15px;
    }}

    QFrame#Section[variant="compact"] QLabel#SectionDescription {{
        font-size: 11px;
    }}
    """
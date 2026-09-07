"""
Reusable badge component stylesheet.

Contains QSS rules for:

- semantic badge variants
- badge sizes
- filled badges
- outlined badges
- transparent badges
- rounded and rectangular badges
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)


def build_badges_stylesheet() -> str:
    """
    Build and return reusable badge stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Base badge
       ========================================================= */

    QLabel#Badge {{
        color: {colors.TEXT_SECONDARY};
        background-color: {colors.SURFACE};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_MEDIUM}px;

        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    /* =========================================================
       Sizes
       ========================================================= */

    QLabel#Badge[badgeSize="small"] {{
        min-height: 20px;

        padding: 1px 7px;

        font-size: 10px;
    }}

    QLabel#Badge[badgeSize="medium"] {{
        min-height: 24px;

        padding: 2px 9px;

        font-size: 11px;
    }}

    QLabel#Badge[badgeSize="large"] {{
        min-height: 30px;

        padding: 3px 12px;

        font-size: 12px;
    }}

    /* =========================================================
       Corner shape
       ========================================================= */

    QLabel#Badge[rounded="true"][badgeSize="small"] {{
        border-radius: 10px;
    }}

    QLabel#Badge[rounded="true"][badgeSize="medium"] {{
        border-radius: 12px;
    }}

    QLabel#Badge[rounded="true"][badgeSize="large"] {{
        border-radius: 15px;
    }}

    QLabel#Badge[rounded="false"] {{
        border-radius: {metrics.RADIUS_SMALL}px;
    }}

    /* =========================================================
       Default variant
       ========================================================= */

    QLabel#Badge[variant="default"] {{
        color: {colors.TEXT_SECONDARY};
        background-color: {colors.SURFACE};

        border-color: {colors.BORDER};
    }}

    /* =========================================================
       Primary variant
       ========================================================= */

    QLabel#Badge[variant="primary"] {{
        color: {colors.ACCENT_LIGHT};
        background-color: {colors.SELECTION_INACTIVE};

        border-color: {colors.ACCENT_BORDER};
    }}

    /* =========================================================
       Success variant
       ========================================================= */

    QLabel#Badge[variant="success"] {{
        color: {colors.SUCCESS};
        background-color: {colors.PANEL};

        border-color: {colors.SUCCESS};
    }}

    /* =========================================================
       Warning variant
       ========================================================= */

    QLabel#Badge[variant="warning"] {{
        color: {colors.WARNING};
        background-color: {colors.PANEL};

        border-color: {colors.WARNING};
    }}

    /* =========================================================
       Danger variant
       ========================================================= */

    QLabel#Badge[variant="danger"] {{
        color: {colors.DANGER};
        background-color: {colors.PANEL};

        border-color: {colors.DANGER};
    }}

    /* =========================================================
       Info variant
       ========================================================= */

    QLabel#Badge[variant="info"] {{
        color: {colors.INFO};
        background-color: {colors.PANEL};

        border-color: {colors.INFO};
    }}

    /* =========================================================
       Neutral variant
       ========================================================= */

    QLabel#Badge[variant="neutral"] {{
        color: {colors.TEXT_MUTED};
        background-color: {colors.SURFACE};

        border-color: {colors.BORDER};
    }}

    /* =========================================================
       Outlined appearance
       ========================================================= */

    QLabel#Badge[outlined="true"] {{
        background-color: transparent;
    }}

    QLabel#Badge[outlined="true"][variant="default"] {{
        color: {colors.TEXT_SECONDARY};
        border-color: {colors.BORDER};
    }}

    QLabel#Badge[outlined="true"][variant="primary"] {{
        color: {colors.ACCENT_LIGHT};
        border-color: {colors.ACCENT_BORDER};
    }}

    QLabel#Badge[outlined="true"][variant="success"] {{
        color: {colors.SUCCESS};
        border-color: {colors.SUCCESS};
    }}

    QLabel#Badge[outlined="true"][variant="warning"] {{
        color: {colors.WARNING};
        border-color: {colors.WARNING};
    }}

    QLabel#Badge[outlined="true"][variant="danger"] {{
        color: {colors.DANGER};
        border-color: {colors.DANGER};
    }}

    QLabel#Badge[outlined="true"][variant="info"] {{
        color: {colors.INFO};
        border-color: {colors.INFO};
    }}

    QLabel#Badge[outlined="true"][variant="neutral"] {{
        color: {colors.TEXT_MUTED};
        border-color: {colors.BORDER};
    }}

    /* =========================================================
       Transparent appearance
       ========================================================= */

    QLabel#Badge[transparent="true"] {{
        background-color: transparent;
        border-color: transparent;
    }}

    QLabel#Badge[transparent="true"][variant="default"] {{
        color: {colors.TEXT_SECONDARY};
    }}

    QLabel#Badge[transparent="true"][variant="primary"] {{
        color: {colors.ACCENT_LIGHT};
    }}

    QLabel#Badge[transparent="true"][variant="success"] {{
        color: {colors.SUCCESS};
    }}

    QLabel#Badge[transparent="true"][variant="warning"] {{
        color: {colors.WARNING};
    }}

    QLabel#Badge[transparent="true"][variant="danger"] {{
        color: {colors.DANGER};
    }}

    QLabel#Badge[transparent="true"][variant="info"] {{
        color: {colors.INFO};
    }}

    QLabel#Badge[transparent="true"][variant="neutral"] {{
        color: {colors.TEXT_MUTED};
    }}
    """
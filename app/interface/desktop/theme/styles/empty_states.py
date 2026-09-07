"""
Reusable empty-state component stylesheet.

Contains QSS rules for:

- default empty states
- panel empty states
- compact empty states
- illustrated empty states
- markers
- titles
- descriptions
- custom content
- actions
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)


def build_empty_states_stylesheet() -> str:
    """
    Build and return empty-state stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Base empty state
       ========================================================= */

    QFrame#EmptyState {{
        background-color: transparent;
        border: none;
    }}

    QFrame#EmptyStateMarkerContainer,
    QFrame#EmptyStateTextContainer,
    QFrame#EmptyStateContent,
    QFrame#EmptyStateActions {{
        background-color: transparent;
        border: none;
    }}

    /* =========================================================
       Marker
       ========================================================= */

    QLabel#EmptyStateMarker {{
        min-width: 56px;
        min-height: 56px;

        color: {colors.ACCENT_LIGHT};
        background-color: {colors.SELECTION_INACTIVE};

        border: 1px solid {colors.ACCENT_BORDER};
        border-radius: 28px;

        font-size: 24px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    /* =========================================================
       Typography
       ========================================================= */

    QLabel#EmptyStateTitle {{
        max-width: 520px;

        color: {colors.TEXT_PRIMARY};
        background-color: transparent;

        font-size: 18px;
        font-weight: {metrics.FONT_WEIGHT_SEMIBOLD};
    }}

    QLabel#EmptyStateDescription {{
        max-width: 520px;

        color: {colors.TEXT_MUTED};
        background-color: transparent;

        font-size: 13px;
        font-weight: {metrics.FONT_WEIGHT_NORMAL};
    }}

    /* =========================================================
       Variants
       ========================================================= */

    QFrame#EmptyState[variant="default"] {{
        background-color: transparent;
        border: none;
    }}

    QFrame#EmptyState[variant="panel"] {{
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER};
        border-radius: {metrics.RADIUS_LARGE}px;
    }}

    QFrame#EmptyState[variant="compact"] QLabel#EmptyStateMarker {{
        min-width: 42px;
        min-height: 42px;

        border-radius: 21px;

        font-size: 18px;
    }}

    QFrame#EmptyState[variant="compact"] QLabel#EmptyStateTitle {{
        font-size: 15px;
    }}

    QFrame#EmptyState[variant="compact"] QLabel#EmptyStateDescription {{
        max-width: 420px;
        font-size: 12px;
    }}

    QFrame#EmptyState[variant="illustrated"] QLabel#EmptyStateMarker {{
        min-width: 72px;
        min-height: 72px;

        border-radius: 36px;

        font-size: 30px;
    }}

    QFrame#EmptyState[variant="illustrated"] QLabel#EmptyStateTitle {{
        font-size: 20px;
    }}
    """
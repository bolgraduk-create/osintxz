"""
Application workspace stylesheet.

Contains styles for:

- main application shell
- central workspace
- content area
- page surface
"""

from __future__ import annotations

from app.interface.desktop.theme.colors import (
    AppColors,
)
from app.interface.desktop.theme.metrics import (
    AppMetrics,
)


def build_workspace_stylesheet() -> str:
    """
    Build workspace stylesheet.
    """

    colors = AppColors
    metrics = AppMetrics

    return f"""
    /* =========================================================
       Main application shell
       ========================================================= */

    QMainWindow#MainWindow {{
        background-color: {colors.BACKGROUND};
    }}

    QWidget#ApplicationRoot {{
        background-color: {colors.BACKGROUND};
    }}

    /* =========================================================
       Workspace
       ========================================================= */

    QFrame#ApplicationWorkspace {{
        background-color: {colors.BACKGROUND};
        border: none;
    }}

    /* =========================================================
       Content container
       ========================================================= */

    QFrame#ContentContainer {{
        background-color: {colors.BACKGROUND};
        border: none;
    }}

    /* =========================================================
       Main page surface
       ========================================================= */

    QFrame#PageSurface {{
        background-color: {colors.PANEL};

        border: 1px solid {colors.BORDER};

        border-radius: {metrics.RADIUS_LARGE}px;
    }}
    """
"""
Application color palette.

Contains all colors used by the desktop interface.

UI widgets and views should not define their own color values.
All application colors must be taken from this module.
"""

from __future__ import annotations


class AppColors:
    """
    Central application color palette.
    """

    # ==========================================================
    # Backgrounds
    # ==========================================================

    BACKGROUND = "#151b24"
    BACKGROUND_DEEP = "#10151c"

    PANEL = "#1c2430"
    PANEL_SECONDARY = "#181f29"

    SURFACE = "#232d3a"
    SURFACE_HOVER = "#2a3645"
    SURFACE_PRESSED = "#202936"

    INPUT_BACKGROUND = "#121821"

    # ==========================================================
    # Borders
    # ==========================================================

    BORDER = "#303b49"
    BORDER_LIGHT = "#3b4858"
    BORDER_HOVER = "#536579"
    BORDER_FOCUS = "#4da3ff"

    # ==========================================================
    # Accent colors
    # ==========================================================

    ACCENT = "#347fc4"
    ACCENT_HOVER = "#3d8bd2"
    ACCENT_LIGHT = "#4da3ff"
    ACCENT_BORDER = "#4795dc"

    # ==========================================================
    # Semantic colors
    # ==========================================================

    SUCCESS = "#22c55e"
    SUCCESS_BACKGROUND = "#183525"

    WARNING = "#f59e0b"
    WARNING_BACKGROUND = "#3a2c13"

    DANGER = "#ef4444"
    DANGER_HOVER = "#dc3636"
    DANGER_BACKGROUND = "#3b1c20"

    INFO = "#38bdf8"
    INFO_BACKGROUND = "#163343"

    # ==========================================================
    # Text
    # ==========================================================

    TEXT_PRIMARY = "#f3f6fa"
    TEXT_SECONDARY = "#b8c4d1"
    TEXT_MUTED = "#7f91a5"
    TEXT_DISABLED = "#697687"

    TEXT_ON_ACCENT = "#ffffff"

    # ==========================================================
    # Selection
    # ==========================================================

    SELECTION = "#347fc4"
    SELECTION_INACTIVE = "#36475a"

    # ==========================================================
    # Scrollbars
    # ==========================================================

    SCROLLBAR_BACKGROUND = "#151b24"
    SCROLLBAR_HANDLE = "#3b4858"
    SCROLLBAR_HANDLE_HOVER = "#536579"

    # ==========================================================
    # Graph
    # ==========================================================

    GRAPH_BACKGROUND = BACKGROUND
    GRAPH_PANEL = PANEL
    GRAPH_GRID = "#202a36"
    GRAPH_EDGE = "#58697c"
    GRAPH_EDGE_SELECTED = ACCENT_LIGHT
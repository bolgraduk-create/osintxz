"""
Central desktop interface metrics.

Contains shared values for:

- typography
- spacing
- control sizes
- corner radii
- page layout
- navigation
- headers
- cards
- badges
- dialogs

The compatibility aliases at the bottom preserve support for
older desktop stylesheets and widgets.
"""

from __future__ import annotations


class AppMetrics:
    """
    Shared desktop application metrics.
    """

    # ==========================================================
    # Font family
    # ==========================================================

    FONT_FAMILY = "Segoe UI"

    # ==========================================================
    # Font sizes
    # ==========================================================

    FONT_SIZE_CAPTION = 10
    FONT_SIZE_SMALL = 11
    FONT_SIZE_NORMAL = 12
    FONT_SIZE_BODY = 12
    FONT_SIZE_MEDIUM = 13
    FONT_SIZE_LARGE = 15
    FONT_SIZE_TITLE = 20
    FONT_SIZE_PAGE_TITLE = 24

    # ==========================================================
    # Font weights
    # ==========================================================

    FONT_WEIGHT_NORMAL = 400
    FONT_WEIGHT_MEDIUM = 500
    FONT_WEIGHT_SEMIBOLD = 600
    FONT_WEIGHT_BOLD = 700

    # ==========================================================
    # Spacing
    # ==========================================================

    SPACE_XXS = 2
    SPACE_XS = 4
    SPACE_SMALL = 8
    SPACE_MEDIUM = 12
    SPACE_LARGE = 16
    SPACE_XL = 20
    SPACE_XXL = 24
    SPACE_XXXL = 32

    # ==========================================================
    # Corner radii
    # ==========================================================

    RADIUS_NONE = 0
    RADIUS_XSMALL = 3
    RADIUS_SMALL = 6
    RADIUS_MEDIUM = 10
    RADIUS_LARGE = 14
    RADIUS_XLARGE = 18
    RADIUS_ROUND = 999

    # Generic legacy radius used by the existing stylesheet.
    RADIUS = RADIUS_SMALL

    # Card-specific radius.
    RADIUS_CARD = RADIUS_MEDIUM

    # ==========================================================
    # Controls
    # ==========================================================

    CONTROL_HEIGHT_SMALL = 28
    CONTROL_HEIGHT = 34
    CONTROL_HEIGHT_MEDIUM = 36
    CONTROL_HEIGHT_LARGE = 42

    BUTTON_HEIGHT_SMALL = 28
    BUTTON_HEIGHT_MEDIUM = 34
    BUTTON_HEIGHT_LARGE = 40

    INPUT_HEIGHT_SMALL = 30
    INPUT_HEIGHT_MEDIUM = 38
    INPUT_HEIGHT_LARGE = 44

    ICON_SIZE_SMALL = 14
    ICON_SIZE_MEDIUM = 18
    ICON_SIZE_LARGE = 22

    ICON_BUTTON_SIZE = 34

    # ==========================================================
    # General layout
    # ==========================================================

    PAGE_MARGIN = 24
    PAGE_SPACING = 20

    CONTENT_MARGIN = 24
    CONTENT_SPACING = 16

    SECTION_SPACING = 16
    SECTION_HEADER_SPACING = 6

    # ==========================================================
    # Navigation
    # ==========================================================

    NAVIGATION_WIDTH = 248
    NAVIGATION_COLLAPSED_WIDTH = 72

    NAVIGATION_ITEM_HEIGHT = 42
    NAVIGATION_ITEM_RADIUS = RADIUS_MEDIUM

    # ==========================================================
    # Header
    # ==========================================================

    HEADER_HEIGHT = 72
    HEADER_HORIZONTAL_PADDING = 24
    HEADER_VERTICAL_PADDING = 14

    # ==========================================================
    # Cards
    # ==========================================================

    CARD_RADIUS = RADIUS_MEDIUM
    CARD_PADDING = 16
    CARD_SPACING = 12
    CARD_MIN_HEIGHT = 96

    # ==========================================================
    # Badges
    # ==========================================================

    BADGE_RADIUS = RADIUS_ROUND

    BADGE_HEIGHT_SMALL = 20
    BADGE_HEIGHT_MEDIUM = 24
    BADGE_HEIGHT_LARGE = 30

    BADGE_HORIZONTAL_PADDING_SMALL = 7
    BADGE_HORIZONTAL_PADDING_MEDIUM = 9
    BADGE_HORIZONTAL_PADDING_LARGE = 12

    # ==========================================================
    # Search
    # ==========================================================

    SEARCH_BOX_HEIGHT = 38
    SEARCH_BOX_MIN_WIDTH = 240
    SEARCH_BOX_RADIUS = RADIUS_MEDIUM

    # ==========================================================
    # Toolbar
    # ==========================================================

    TOOLBAR_HEIGHT = 44
    TOOLBAR_COMPACT_HEIGHT = 36
    TOOLBAR_RADIUS = RADIUS_MEDIUM

    # ==========================================================
    # Dialogs
    # ==========================================================

    DIALOG_MIN_WIDTH = 420
    DIALOG_RADIUS = RADIUS_LARGE
    DIALOG_PADDING = 24

    # ==========================================================
    # Miscellaneous
    # ==========================================================

    SEPARATOR_SIZE = 1
    SCROLLBAR_SIZE = 10

    ANIMATION_FAST = 120
    ANIMATION_NORMAL = 200
    ANIMATION_SLOW = 320

    # ==========================================================
    # Compatibility aliases
    # ==========================================================

    BORDER_RADIUS_SMALL = RADIUS_SMALL
    BORDER_RADIUS_MEDIUM = RADIUS_MEDIUM
    BORDER_RADIUS_LARGE = RADIUS_LARGE

    SPACING_XSMALL = SPACE_XS
    SPACING_SMALL = SPACE_SMALL
    SPACING_MEDIUM = SPACE_MEDIUM
    SPACING_LARGE = SPACE_LARGE
    SPACING_XLARGE = SPACE_XL
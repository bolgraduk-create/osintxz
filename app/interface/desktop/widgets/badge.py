"""
Reusable desktop badge component.

Responsible for:

- displaying compact status labels
- displaying entity and evidence types
- displaying semantic states
- supporting multiple sizes and variants
- supporting filled and outlined appearances

Does NOT:

- execute business logic
- determine statuses
- access controllers
- access services
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QWidget,
)


class Badge(QLabel):
    """
    Reusable application badge.

    Supported variants:

    - default
    - primary
    - success
    - warning
    - danger
    - info
    - neutral

    Supported sizes:

    - small
    - medium
    - large
    """

    SUPPORTED_VARIANTS = {
        "default",
        "primary",
        "success",
        "warning",
        "danger",
        "info",
        "neutral",
    }

    SUPPORTED_SIZES = {
        "small",
        "medium",
        "large",
    }

    def __init__(
        self,
        text: str = "",
        variant: str = "default",
        size: str = "medium",
        outlined: bool = False,
        rounded: bool = True,
        transparent: bool = False,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            text,
            parent,
        )

        self._badge_text = (
            text or ""
        )

        self._variant = "default"
        self._size = "medium"
        self._outlined = bool(
            outlined
        )
        self._rounded = bool(
            rounded
        )
        self._transparent = bool(
            transparent
        )

        self.setObjectName(
            "Badge"
        )

        self.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        self.setWordWrap(
            False
        )

        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )

        self.set_variant(
            variant
        )

        self.set_badge_size(
            size
        )

        self.set_outlined(
            outlined
        )

        self.set_rounded(
            rounded
        )

        self.set_transparent(
            transparent
        )

        self._update_visibility()

    # ==========================================================
    # Text API
    # ==========================================================

    def set_text(
        self,
        text: str | None,
    ) -> None:
        """
        Update badge text.
        """

        self._badge_text = (
            text or ""
        )

        self.setText(
            self._badge_text
        )

        self._update_visibility()

    def text_value(
        self,
    ) -> str:
        """
        Return current badge text.
        """

        return self._badge_text

    # ==========================================================
    # Variant API
    # ==========================================================

    def set_variant(
        self,
        variant: str,
    ) -> None:
        """
        Set semantic badge variant.
        """

        normalized_variant = self._normalize_value(
            variant,
            self.SUPPORTED_VARIANTS,
            "default",
        )

        self._variant = (
            normalized_variant
        )

        self.setProperty(
            "variant",
            self._variant,
        )

        self._refresh_style()

    def variant(
        self,
    ) -> str:
        """
        Return current badge variant.
        """

        return self._variant

    # ==========================================================
    # Size API
    # ==========================================================

    def set_badge_size(
        self,
        size: str,
    ) -> None:
        """
        Set badge size.

        The method is named set_badge_size instead of set_size
        to avoid ambiguity with QWidget geometry methods.
        """

        normalized_size = self._normalize_value(
            size,
            self.SUPPORTED_SIZES,
            "medium",
        )

        self._size = (
            normalized_size
        )

        self.setProperty(
            "badgeSize",
            self._size,
        )

        self._apply_size_constraints()
        self._refresh_style()

    def badge_size(
        self,
    ) -> str:
        """
        Return current badge size.
        """

        return self._size

    # ==========================================================
    # Appearance API
    # ==========================================================

    def set_outlined(
        self,
        outlined: bool,
    ) -> None:
        """
        Enable or disable outlined appearance.
        """

        self._outlined = bool(
            outlined
        )

        self.setProperty(
            "outlined",
            self._outlined,
        )

        self._refresh_style()

    def is_outlined(
        self,
    ) -> bool:
        """
        Return whether outlined appearance is enabled.
        """

        return self._outlined

    def set_rounded(
        self,
        rounded: bool,
    ) -> None:
        """
        Enable or disable pill-shaped corners.
        """

        self._rounded = bool(
            rounded
        )

        self.setProperty(
            "rounded",
            self._rounded,
        )

        self._refresh_style()

    def is_rounded(
        self,
    ) -> bool:
        """
        Return whether rounded appearance is enabled.
        """

        return self._rounded

    def set_transparent(
        self,
        transparent: bool,
    ) -> None:
        """
        Enable or disable transparent background.
        """

        self._transparent = bool(
            transparent
        )

        self.setProperty(
            "transparent",
            self._transparent,
        )

        self._refresh_style()

    def is_transparent(
        self,
    ) -> bool:
        """
        Return whether transparent background is enabled.
        """

        return self._transparent

    # ==========================================================
    # Convenience API
    # ==========================================================

    def configure(
        self,
        *,
        text: str | None = None,
        variant: str | None = None,
        size: str | None = None,
        outlined: bool | None = None,
        rounded: bool | None = None,
        transparent: bool | None = None,
    ) -> None:
        """
        Update multiple badge properties at once.
        """

        if text is not None:

            self.set_text(
                text
            )

        if variant is not None:

            self.set_variant(
                variant
            )

        if size is not None:

            self.set_badge_size(
                size
            )

        if outlined is not None:

            self.set_outlined(
                outlined
            )

        if rounded is not None:

            self.set_rounded(
                rounded
            )

        if transparent is not None:

            self.set_transparent(
                transparent
            )

    # ==========================================================
    # Qt overrides
    # ==========================================================

    def setText(
        self,
        text: str,
    ) -> None:
        """
        Keep internal badge text synchronized with QLabel.
        """

        self._badge_text = (
            text or ""
        )

        super().setText(
            self._badge_text
        )

        if hasattr(
            self,
            "_variant",
        ):

            self._update_visibility()

    # ==========================================================
    # Internal helpers
    # ==========================================================

    def _apply_size_constraints(
        self,
    ) -> None:
        """
        Apply height and horizontal padding through margins.
        """

        if self._size == "small":

            self.setMinimumHeight(
                22
            )

            self.setContentsMargins(
                8,
                2,
                8,
                2,
            )

            return

        if self._size == "large":

            self.setMinimumHeight(
                32
            )

            self.setContentsMargins(
                14,
                4,
                14,
                4,
            )

            return

        self.setMinimumHeight(
            26
        )

        self.setContentsMargins(
            10,
            3,
            10,
            3,
        )

    def _update_visibility(
        self,
    ) -> None:
        """
        Hide badge when its text is empty.
        """

        has_text = bool(
            self._badge_text.strip()
        )

        self.setVisible(
            has_text
        )

    def _refresh_style(
        self,
    ) -> None:
        """
        Reapply QSS after dynamic property changes.
        """

        style = self.style()

        if style is None:

            return

        style.unpolish(
            self
        )

        style.polish(
            self
        )

        self.updateGeometry()
        self.update()

    @staticmethod
    def _normalize_value(
        value: str | None,
        supported_values: set[str],
        fallback: str,
    ) -> str:
        """
        Normalize and validate a string property.
        """

        normalized_value = (
            value or fallback
        ).strip().casefold()

        if normalized_value not in supported_values:

            return fallback

        return normalized_value
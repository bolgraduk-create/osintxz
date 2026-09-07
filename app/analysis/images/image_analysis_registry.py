"""
Image analysis registry.

Stores available analyzers and provides
lookup functionality.

Responsibilities:

- register analyzers
- register default analyzers
- unregister analyzers
- retrieve analyzers
- list analyzers
- report analyzer availability

Does NOT:

- execute analyzers
- access the database
- modify evidence
- commit transactions
"""

from __future__ import annotations

from collections.abc import (
    Iterable,
)

from typing import Any

from app.analysis.images.base_image_analyzer import (
    BaseImageAnalyzer,
)

from app.analysis.images.image_hash_analyzer import (
    ImageHashAnalyzer,
)

from app.analysis.images.image_face_analyzer import (
    ImageFaceAnalyzer,
)

from app.analysis.images.face_embedding_analyzer import (
    FaceEmbeddingAnalyzer,
)

from app.analysis.images.image_embedding_analyzer import (
    ImageEmbeddingAnalyzer,
)

from app.analysis.images.image_ocr_analyzer import (
    ImageOCRAnalyzer,
)


class ImageAnalysisRegistry:
    """
    Registry of image analyzers.
    """

    def __init__(
        self,
        *,
        register_defaults: bool = True,
    ) -> None:
        """
        Initialize the registry.

        Args:
            register_defaults:
                Register built-in analyzers automatically.
        """

        self._analyzers: dict[
            str,
            BaseImageAnalyzer,
        ] = {}

        if register_defaults:

            self.register_default_analyzers()

        # ==================================================
        # General semantic image embeddings
        # ==================================================

        if register_defaults:
            self.register(
                ImageEmbeddingAnalyzer()
            )

        if register_defaults:
            self.register(
                ImageOCRAnalyzer()
            )

    # ==========================================================
    # Default analyzers
    # ==========================================================

    def register_default_analyzers(
        self,
    ) -> None:
        """
        Register every built-in image analyzer.

        This method is safe to call repeatedly because analyzers
        are stored by normalized unique name.
        """

        default_analyzers: list[
            BaseImageAnalyzer
        ] = [
            ImageHashAnalyzer(),
            ImageFaceAnalyzer(),
            FaceEmbeddingAnalyzer(),
        ]

        for analyzer in default_analyzers:

            self.register(
                analyzer,
                replace=True,
            )

    # ==========================================================
    # Registration
    # ==========================================================

    def register(
        self,
        analyzer: BaseImageAnalyzer,
        *,
        replace: bool = False,
    ) -> None:
        """
        Register one analyzer.

        Args:
            analyzer:
                Analyzer instance.

            replace:
                Replace an already registered analyzer with
                the same normalized name.
        """

        if not isinstance(
            analyzer,
            BaseImageAnalyzer,
        ):

            raise TypeError(
                "Analyzer must inherit BaseImageAnalyzer."
            )

        name = self._normalize_name(
            analyzer.name
        )

        if (
            name in self._analyzers
            and not replace
        ):

            raise ValueError(
                "Image analyzer is already registered: "
                f"{name}"
            )

        self._analyzers[name] = analyzer

    def register_many(
        self,
        analyzers: Iterable[
            BaseImageAnalyzer
        ],
        *,
        replace: bool = False,
    ) -> None:
        """
        Register multiple analyzers.
        """

        for analyzer in analyzers:

            self.register(
                analyzer,
                replace=replace,
            )

    def unregister(
        self,
        name: str,
    ) -> BaseImageAnalyzer | None:
        """
        Remove and return one analyzer.
        """

        normalized_name = (
            self._normalize_name(
                name
            )
        )

        return self._analyzers.pop(
            normalized_name,
            None,
        )

    def clear(
        self,
    ) -> None:
        """
        Remove every analyzer.
        """

        self._analyzers.clear()

    # ==========================================================
    # Lookup
    # ==========================================================

    def get(
        self,
        name: str,
    ) -> BaseImageAnalyzer:
        """
        Return one analyzer.

        Raises:
            KeyError:
                When the analyzer is not registered.
        """

        normalized_name = (
            self._normalize_name(
                name
            )
        )

        analyzer = self._analyzers.get(
            normalized_name
        )

        if analyzer is None:

            registered_names = (
                ", ".join(
                    self.names()
                )
                or "none"
            )

            raise KeyError(
                "Unknown image analyzer: "
                f"{normalized_name}. "
                "Registered analyzers: "
                f"{registered_names}."
            )

        return analyzer

    def get_optional(
        self,
        name: str,
    ) -> BaseImageAnalyzer | None:
        """
        Return an analyzer or None.
        """

        normalized_name = (
            self._normalize_name(
                name
            )
        )

        return self._analyzers.get(
            normalized_name
        )

    def exists(
        self,
        name: str,
    ) -> bool:
        """
        Return whether an analyzer is registered.
        """

        normalized_name = (
            self._normalize_name(
                name
            )
        )

        return (
            normalized_name
            in self._analyzers
        )

    # ==========================================================
    # Collections
    # ==========================================================

    def names(
        self,
    ) -> list[str]:
        """
        Return sorted analyzer names.
        """

        return sorted(
            self._analyzers.keys()
        )

    def analyzers(
        self,
    ) -> list[BaseImageAnalyzer]:
        """
        Return registered analyzers in registration order.
        """

        return list(
            self._analyzers.values()
        )

    def available(
        self,
    ) -> list[BaseImageAnalyzer]:
        """
        Return analyzers whose dependencies are available.
        """

        return [
            analyzer
            for analyzer
            in self._analyzers.values()
            if analyzer.is_available()
        ]

    def unavailable(
        self,
    ) -> list[BaseImageAnalyzer]:
        """
        Return analyzers with missing dependencies.
        """

        return [
            analyzer
            for analyzer
            in self._analyzers.values()
            if not analyzer.is_available()
        ]

    def availability_map(
        self,
    ) -> dict[str, bool]:
        """
        Return analyzer availability by name.
        """

        return {
            name: analyzer.is_available()
            for name, analyzer
            in self._analyzers.items()
        }

    # ==========================================================
    # Protocol
    # ==========================================================

    def __contains__(
        self,
        name: object,
    ) -> bool:

        if not isinstance(
            name,
            str,
        ):

            return False

        return self.exists(
            name
        )

    def __len__(
        self,
    ) -> int:

        return len(
            self._analyzers
        )

    def __iter__(
        self,
    ) -> Iterable[
        BaseImageAnalyzer
    ]:

        return iter(
            self._analyzers.values()
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:
        """
        Normalize and validate an analyzer name.
        """

        if not isinstance(
            name,
            str,
        ):

            raise TypeError(
                "Analyzer name must be a string."
            )

        normalized_name = (
            name.strip().lower()
        )

        if not normalized_name:

            raise ValueError(
                "Analyzer name cannot be empty."
            )

        return normalized_name

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return registry information.
        """

        available_analyzers = (
            self.available()
        )

        unavailable_analyzers = (
            self.unavailable()
        )

        return {
            "registered": len(
                self._analyzers
            ),
            "available": len(
                available_analyzers
            ),
            "unavailable": len(
                unavailable_analyzers
            ),
            "names": self.names(),
            "availability": (
                self.availability_map()
            ),
            "analyzers": [
                analyzer.metadata()
                for analyzer
                in self.analyzers()
            ],
        }
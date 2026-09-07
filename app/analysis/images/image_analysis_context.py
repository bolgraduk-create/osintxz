"""
Image analysis context.

Represents immutable input data passed
to every image analyzer.

The context contains:

- evidence identifier
- case identifier
- original image path
- compatible preview path
- MIME type
- existing processing metadata
- analyzer options

Does NOT:

- access the database
- modify evidence
- execute analyzers
- store analysis results
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from pathlib import Path
from typing import Any
from uuid import UUID


@dataclass(
    frozen=True,
    slots=True,
)
class ImageAnalysisContext:
    """
    Immutable input context for image analysis.
    """

    image_path: Path

    evidence_id: UUID | None = None

    case_id: UUID | None = None

    preview_path: Path | None = None

    mime_type: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    options: dict[str, Any] = field(
        default_factory=dict
    )

    # ==========================================================
    # Construction
    # ==========================================================

    @classmethod
    def create(
        cls,
        *,
        image_path: str | Path,
        evidence_id: str | UUID | None = None,
        case_id: str | UUID | None = None,
        preview_path: str | Path | None = None,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> "ImageAnalysisContext":
        """
        Validate input and create an analysis context.
        """

        normalized_image_path = (
            cls._validate_required_file(
                image_path,
                field_name="image_path",
            )
        )

        normalized_preview_path = (
            cls._validate_optional_file(
                preview_path,
                field_name="preview_path",
            )
        )

        normalized_evidence_id = (
            cls._normalize_uuid(
                evidence_id,
                field_name="evidence_id",
            )
        )

        normalized_case_id = (
            cls._normalize_uuid(
                case_id,
                field_name="case_id",
            )
        )

        normalized_mime_type = (
            str(
                mime_type
            ).strip()
            if mime_type
            else None
        )

        return cls(
            image_path=normalized_image_path,
            evidence_id=normalized_evidence_id,
            case_id=normalized_case_id,
            preview_path=normalized_preview_path,
            mime_type=normalized_mime_type,
            metadata=dict(
                metadata
                or {}
            ),
            options=dict(
                options
                or {}
            ),
        )

    # ==========================================================
    # Paths
    # ==========================================================

    @property
    def analysis_path(
        self,
    ) -> Path:
        """
        Return the best path for pixel-based analyzers.

        A generated preview is preferred when available because
        Qt-compatible previews also normalize HEIC and HEIF files.
        """

        if (
            self.preview_path is not None
            and self.preview_path.is_file()
        ):

            return self.preview_path

        return self.image_path

    @property
    def original_path(
        self,
    ) -> Path:
        """
        Return the unmodified original evidence path.
        """

        return self.image_path

    # ==========================================================
    # Options
    # ==========================================================

    def get_option(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        """
        Read one analyzer option.
        """

        return self.options.get(
            name,
            default,
        )

    # ==========================================================
    # Serialization
    # ==========================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize context into an application-ready dictionary.
        """

        return {
            "image_path": str(
                self.image_path
            ),
            "analysis_path": str(
                self.analysis_path
            ),
            "preview_path": (
                str(
                    self.preview_path
                )
                if self.preview_path
                else None
            ),
            "evidence_id": (
                str(
                    self.evidence_id
                )
                if self.evidence_id
                else None
            ),
            "case_id": (
                str(
                    self.case_id
                )
                if self.case_id
                else None
            ),
            "mime_type": self.mime_type,
            "metadata": dict(
                self.metadata
            ),
            "options": dict(
                self.options
            ),
        }

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_required_file(
        value: str | Path,
        *,
        field_name: str,
    ) -> Path:
        """
        Validate a required file path.
        """

        path = Path(
            value
        ).expanduser()

        try:

            path = path.resolve(
                strict=True
            )

        except FileNotFoundError as error:

            raise FileNotFoundError(
                f"{field_name} does not exist: {path}"
            ) from error

        if not path.is_file():

            raise ValueError(
                f"{field_name} is not a file: {path}"
            )

        return path

    @staticmethod
    def _validate_optional_file(
        value: str | Path | None,
        *,
        field_name: str,
    ) -> Path | None:
        """
        Validate an optional file path.
        """

        if value is None:

            return None

        path = Path(
            value
        ).expanduser()

        try:

            path = path.resolve(
                strict=True
            )

        except FileNotFoundError:

            return None

        if not path.is_file():

            raise ValueError(
                f"{field_name} is not a file: {path}"
            )

        return path

    @staticmethod
    def _normalize_uuid(
        value: str | UUID | None,
        *,
        field_name: str,
    ) -> UUID | None:
        """
        Normalize an optional UUID value.
        """

        if value is None:

            return None

        if isinstance(
            value,
            UUID,
        ):

            return value

        try:

            return UUID(
                str(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                f"{field_name} must be a valid UUID."
            ) from error
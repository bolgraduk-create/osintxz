"""
Image analysis result.

Provides a unified result contract
for all image analyzers.

Every analyzer returns the same structure:

- analyzer name
- execution status
- result data
- warnings
- errors
- execution time
- analyzer metadata
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from enum import Enum
from typing import Any


class ImageAnalysisStatus(
    str,
    Enum,
):
    """
    Supported image analysis result statuses.
    """

    COMPLETED = "completed"

    COMPLETED_WITH_WARNINGS = (
        "completed_with_warnings"
    )

    SKIPPED = "skipped"

    UNAVAILABLE = "unavailable"

    FAILED = "failed"


@dataclass(
    slots=True,
)
class ImageAnalysisResult:
    """
    Unified result returned by one image analyzer.
    """

    analyzer: str

    status: ImageAnalysisStatus

    data: dict[str, Any] = field(
        default_factory=dict
    )

    warnings: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    execution_time: float = 0.0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    # ==========================================================
    # Factories
    # ==========================================================

    @classmethod
    def completed(
        cls,
        *,
        analyzer: str,
        data: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        execution_time: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> "ImageAnalysisResult":
        """
        Create a successful result.
        """

        normalized_warnings = cls._normalize_messages(
            warnings
            or []
        )

        status = (
            ImageAnalysisStatus
            .COMPLETED_WITH_WARNINGS
            if normalized_warnings
            else ImageAnalysisStatus.COMPLETED
        )

        return cls(
            analyzer=analyzer,
            status=status,
            data=dict(
                data
                or {}
            ),
            warnings=normalized_warnings,
            errors=[],
            execution_time=round(
                max(
                    0.0,
                    float(
                        execution_time
                    ),
                ),
                6,
            ),
            metadata=dict(
                metadata
                or {}
            ),
        )

    @classmethod
    def failed(
        cls,
        *,
        analyzer: str,
        error: str | Exception,
        execution_time: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> "ImageAnalysisResult":
        """
        Create a failed result.
        """

        return cls(
            analyzer=analyzer,
            status=ImageAnalysisStatus.FAILED,
            data={},
            warnings=[],
            errors=[
                str(
                    error
                ).strip()
                or error.__class__.__name__
                if isinstance(
                    error,
                    Exception,
                )
                else str(
                    error
                ).strip()
            ],
            execution_time=round(
                max(
                    0.0,
                    float(
                        execution_time
                    ),
                ),
                6,
            ),
            metadata=dict(
                metadata
                or {}
            ),
        )

    @classmethod
    def unavailable(
        cls,
        *,
        analyzer: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> "ImageAnalysisResult":
        """
        Create an unavailable result.
        """

        return cls(
            analyzer=analyzer,
            status=(
                ImageAnalysisStatus
                .UNAVAILABLE
            ),
            data={},
            warnings=[
                str(
                    reason
                ).strip()
            ],
            errors=[],
            execution_time=0.0,
            metadata=dict(
                metadata
                or {}
            ),
        )

    @classmethod
    def skipped(
        cls,
        *,
        analyzer: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> "ImageAnalysisResult":
        """
        Create a skipped result.
        """

        return cls(
            analyzer=analyzer,
            status=ImageAnalysisStatus.SKIPPED,
            data={},
            warnings=[
                str(
                    reason
                ).strip()
            ],
            errors=[],
            execution_time=0.0,
            metadata=dict(
                metadata
                or {}
            ),
        )

    # ==========================================================
    # State
    # ==========================================================

    @property
    def successful(
        self,
    ) -> bool:
        """
        Return whether the analyzer produced usable output.
        """

        return self.status in {
            ImageAnalysisStatus.COMPLETED,
            (
                ImageAnalysisStatus
                .COMPLETED_WITH_WARNINGS
            ),
        }

    # ==========================================================
    # Serialization
    # ==========================================================

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize result into an application-ready dictionary.
        """

        return {
            "analyzer": self.analyzer,
            "status": self.status.value,
            "successful": self.successful,
            "data": dict(
                self.data
            ),
            "warnings": list(
                self.warnings
            ),
            "errors": list(
                self.errors
            ),
            "execution_time": (
                self.execution_time
            ),
            "metadata": dict(
                self.metadata
            ),
        }

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _normalize_messages(
        messages: list[str],
    ) -> list[str]:
        """
        Remove empty and duplicate messages.
        """

        normalized_messages: list[str] = []

        seen: set[str] = set()

        for message in messages:

            normalized = str(
                message
            ).strip()

            if (
                not normalized
                or normalized in seen
            ):

                continue

            seen.add(
                normalized
            )

            normalized_messages.append(
                normalized
            )

        return normalized_messages
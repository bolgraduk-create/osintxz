"""
Base image analyzer.

All image analysis modules must inherit
from this abstract class.

An analyzer:

- receives ImageAnalysisContext
- executes one isolated analytical function
- returns ImageAnalysisResult
- does not access the database
- does not commit transactions
- does not modify original evidence
"""

from __future__ import annotations

import time

from abc import (
    ABC,
    abstractmethod,
)

from typing import Any

from app.analysis.images.image_analysis_context import (
    ImageAnalysisContext,
)

from app.analysis.images.image_analysis_result import (
    ImageAnalysisResult,
)


class BaseImageAnalyzer(
    ABC,
):
    """
    Abstract contract for image analyzers.
    """

    name: str = "base"

    description: str = (
        "Base image analyzer."
    )

    version: str = "1.0"

    # ==========================================================
    # Availability
    # ==========================================================

    def is_available(
        self,
    ) -> bool:
        """
        Return whether analyzer dependencies are available.

        Analyzers that depend on external tools or optional
        Python packages should override this method.
        """

        return True

    def unavailable_reason(
        self,
    ) -> str:
        """
        Return a human-readable availability explanation.
        """

        return (
            f"Analyzer '{self.name}' "
            "is not available."
        )

    # ==========================================================
    # Execution
    # ==========================================================

    def execute(
        self,
        context: ImageAnalysisContext,
    ) -> ImageAnalysisResult:
        """
        Safely execute this analyzer.

        Exceptions are converted into failed results so one
        analyzer cannot terminate the complete pipeline.
        """

        if not isinstance(
            context,
            ImageAnalysisContext,
        ):

            raise TypeError(
                "Image analyzer context must be "
                "ImageAnalysisContext."
            )

        if not self.is_available():

            return (
                ImageAnalysisResult
                .unavailable(
                    analyzer=self.name,
                    reason=(
                        self.unavailable_reason()
                    ),
                    metadata=(
                        self.metadata()
                    ),
                )
            )

        start_time = time.perf_counter()

        try:

            result = self.analyze(
                context
            )

        except Exception as error:

            return (
                ImageAnalysisResult.failed(
                    analyzer=self.name,
                    error=error,
                    execution_time=(
                        time.perf_counter()
                        - start_time
                    ),
                    metadata=(
                        self.metadata()
                    ),
                )
            )

        execution_time = (
            time.perf_counter()
            - start_time
        )

        if isinstance(
            result,
            ImageAnalysisResult,
        ):

            result.execution_time = round(
                execution_time,
                6,
            )

            if not result.metadata:

                result.metadata = (
                    self.metadata()
                )

            return result

        if isinstance(
            result,
            dict,
        ):

            return (
                ImageAnalysisResult
                .completed(
                    analyzer=self.name,
                    data=result,
                    execution_time=(
                        execution_time
                    ),
                    metadata=(
                        self.metadata()
                    ),
                )
            )

        raise TypeError(
            f"Analyzer '{self.name}' returned "
            "an unsupported result type: "
            f"{type(result).__name__}."
        )

    @abstractmethod
    def analyze(
        self,
        context: ImageAnalysisContext,
    ) -> ImageAnalysisResult | dict[str, Any]:
        """
        Execute analyzer-specific logic.
        """

        raise NotImplementedError

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return analyzer information.
        """

        return {
            "name": self.name,
            "description": (
                self.description
            ),
            "version": self.version,
            "available": (
                self.is_available()
            ),
            "class": (
                self.__class__.__name__
            ),
        }
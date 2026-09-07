"""
Image analysis pipeline.

Coordinates execution of all image analyzers.

Architecture:

Image
    ↓
ImageAnalysisPipeline
    ↓
Registry
    ↓
Analyzers
    ↓
Unified Result
"""

from __future__ import annotations

import time

from typing import Any

from app.analysis.images.base_image_analyzer import (
    BaseImageAnalyzer,
)

from app.analysis.images.image_analysis_context import (
    ImageAnalysisContext,
)

from app.analysis.images.image_analysis_registry import (
    ImageAnalysisRegistry,
)


class ImageAnalysisPipeline:
    """
    Main image analysis orchestrator.
    """

    def __init__(
        self,
        registry: (
            ImageAnalysisRegistry
            | None
        ) = None,
    ) -> None:

        self.registry = (
            registry
            or ImageAnalysisRegistry()
        )

    # ==========================================================
    # Registration
    # ==========================================================

    def register(
        self,
        analyzer: BaseImageAnalyzer,
    ) -> None:
        """
        Register one analyzer.
        """

        self.registry.register(
            analyzer
        )

    # ==========================================================
    # Single execution
    # ==========================================================

    def analyze(
        self,
        analyzer_name: str,
        context: ImageAnalysisContext,
    ) -> dict[str, Any]:
        """
        Execute one analyzer.
        """

        analyzer = (
            self.registry.get(
                analyzer_name
            )
        )

        result = (
            analyzer.execute(
                context
            )
        )

        return result.to_dict()

    # ==========================================================
    # Multiple execution
    # ==========================================================

    def analyze_many(
        self,
        analyzers: list[str],
        context: ImageAnalysisContext,
    ) -> dict[str, Any]:
        """
        Execute selected analyzers.
        """

        start_time = (
            time.perf_counter()
        )

        results: dict[
            str,
            Any,
        ] = {}

        for analyzer_name in analyzers:

            results[
                analyzer_name
            ] = self.analyze(
                analyzer_name,
                context,
            )

        return {

            "results":
                results,

            "metadata":
                self._metadata(
                    start_time,
                    analyzers,
                ),

        }

    # ==========================================================
    # Full execution
    # ==========================================================

    def analyze_all(
        self,
        context: ImageAnalysisContext,
    ) -> dict[str, Any]:
        """
        Execute every registered analyzer.
        """

        start_time = (
            time.perf_counter()
        )

        results: dict[
            str,
            Any,
        ] = {}

        executed: list[str] = []

        for analyzer in self.registry:

            executed.append(
                analyzer.name
            )

            results[
                analyzer.name
            ] = (
                analyzer.execute(
                    context
                ).to_dict()
            )

        return {

            "results":
                results,

            "metadata":
                self._metadata(
                    start_time,
                    executed,
                ),

        }

    # ==========================================================
    # Helpers
    # ==========================================================

    def available(
        self,
    ) -> list[str]:
        """
        Return available analyzers.
        """

        return [

            analyzer.name

            for analyzer

            in self.registry.available()

        ]

    def installed(
        self,
    ) -> dict[str, bool]:
        """
        Availability map.
        """

        return {

            analyzer.name:
                analyzer.is_available()

            for analyzer

            in self.registry

        }

    # ==========================================================
    # Metadata
    # ==========================================================

    def _metadata(
        self,
        start_time: float,
        analyzers: list[str],
    ) -> dict[str, Any]:

        return {

            "execution_time":
                round(
                    time.perf_counter()
                    -
                    start_time,
                    6,
                ),

            "executed":
                analyzers,

            "registered":
                len(
                    self.registry
                ),

            "available":
                len(
                    self.registry.available()
                ),

        }

    # ==========================================================
    # Information
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:

        return {

            "type":
                "image_analysis_pipeline",

            "registry":
                self.registry.metadata(),

        }
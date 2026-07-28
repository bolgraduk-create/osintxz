"""
Analysis pipeline.

Coordinates all analysis modules.

Architecture:

Input Data
    ↓
AnalysisPipeline
    ↓
Analyzers
    ↓
Unified Analysis Result
"""

from __future__ import annotations

import time

from typing import Any


from app.analysis.analyzers.entity_analyzer import (
    EntityAnalyzer,
)

from app.analysis.analyzers.relationship_analyzer import (
    RelationshipAnalyzer,
)

from app.analysis.analyzers.timeline_analyzer import (
    TimelineAnalyzer,
)

from app.analysis.analyzers.sentiment_analyzer import (
    SentimentAnalyzer,
)


class AnalysisPipeline:
    """
    Main analysis orchestrator.

    Coordinates all analytical modules.
    """


    def __init__(
        self,
        entity_analyzer: EntityAnalyzer | None = None,
        relationship_analyzer: RelationshipAnalyzer | None = None,
        timeline_analyzer: TimelineAnalyzer | None = None,
        sentiment_analyzer: SentimentAnalyzer | None = None,
    ):
        """
        Initialize pipeline.
        """

        self.entity_analyzer = (
            entity_analyzer
            or EntityAnalyzer()
        )

        self.relationship_analyzer = (
            relationship_analyzer
            or RelationshipAnalyzer()
        )

        self.timeline_analyzer = (
            timeline_analyzer
            or TimelineAnalyzer()
        )

        self.sentiment_analyzer = (
            sentiment_analyzer
            or SentimentAnalyzer()
        )


    # ==========================================================
    # Main execution
    # ==========================================================

    def analyze(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute full analysis pipeline.
        """


        self.validate_input(
            data
        )


        start_time = time.time()


        result = {

            "entities":
                self.run_entities_analysis(
                    data
                ),

            "relationships":
                self.run_relationship_analysis(
                    data
                ),

            "timeline":
                self.run_timeline_analysis(
                    data
                ),

            "sentiment":
                self.run_sentiment_analysis(
                    data
                ),

        }


        result["metadata"] = (
            self.build_metadata(
                start_time
            )
        )


        return result


    # ==========================================================
    # Analyzer execution
    # ==========================================================

    def run_entities_analysis(
        self,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:

        text = data.get(
            "text",
            "",
        )


        return self.entity_analyzer.analyze(
            text
        )


    def run_relationship_analysis(
        self,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:

        messages = data.get(
            "messages",
            [],
        )


        return (
            self.relationship_analyzer.analyze(
                messages
            )
        )


    def run_timeline_analysis(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:

        events = data.get(
            "events",
            [],
        )


        return (
            self.timeline_analyzer.analyze(
                events
            )
        )


    def run_sentiment_analysis(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:

        text = data.get(
            "text",
            "",
        )


        return (
            self.sentiment_analyzer.analyze(
                text
            )
        )


    # ==========================================================
    # Validation
    # ==========================================================

    def validate_input(
        self,
        data: dict[str, Any],
    ) -> None:

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "Analysis input must be dictionary"
            )


    # ==========================================================
    # Metadata
    # ==========================================================

    def build_metadata(
        self,
        start_time: float,
    ) -> dict[str, Any]:

        return {

            "execution_time":
                round(
                    time.time()
                    -
                    start_time,
                    4,
                ),

            "modules": [

                "entities",

                "relationships",

                "timeline",

                "sentiment",

            ],
        }


    # ==========================================================
    # Export
    # ==========================================================

    def export_result(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:

        return result
"""
AI Context Builder.

Collects and structures investigation
data before sending it to AI models.

Architecture:

Case Data
    ↓
ContextBuilder
    ↓
AI Context
    ↓
AI Provider
"""

from __future__ import annotations

from datetime import datetime

from typing import Any


class ContextBuilder:
    """
    Builds structured context
    for AI analysis.
    """


    def __init__(
        self,
    ):
        """
        Initialize context storage.
        """

        self.context: dict[str, Any] = {}

        self.reset()


    # ==========================================================
    # Core
    # ==========================================================

    def reset(
        self,
    ) -> None:
        """
        Clear current context.
        """

        self.context = {

            "case": {},

            "documents": [],

            "messages": [],

            "entities": [],

            "relationships": [],

            "analysis_results": [],

            "metadata": {},

        }


    def build_case_context(
        self,
        case: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build context from investigation case.
        """

        self.reset()


        self.context["case"] = case


        self.context["metadata"] = {

            "created_at":
                datetime.utcnow(),

        }


        return self.context


    # ==========================================================
    # Data collectors
    # ==========================================================

    def add_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> None:
        """
        Add documents.
        """

        self.context[
            "documents"
        ].extend(
            documents
        )


    def add_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> None:
        """
        Add messages.
        """

        self.context[
            "messages"
        ].extend(
            messages
        )


    def add_entities(
        self,
        entities: list[dict[str, Any]],
    ) -> None:
        """
        Add extracted entities.
        """

        self.context[
            "entities"
        ].extend(
            entities
        )


    def add_relationships(
        self,
        relationships: list[dict[str, Any]],
    ) -> None:
        """
        Add relationships.
        """

        self.context[
            "relationships"
        ].extend(
            relationships
        )


    def add_analysis_results(
        self,
        results: list[dict[str, Any]],
    ) -> None:
        """
        Add analysis outputs.
        """

        self.context[
            "analysis_results"
        ].extend(
            results
        )


    # ==========================================================
    # Output
    # ==========================================================

    def get_context(
        self,
    ) -> dict[str, Any]:
        """
        Return current AI context.
        """

        return self.context


    def summarize_context(
        self,
    ) -> dict[str, Any]:
        """
        Return context statistics.
        """

        return {

            "documents":
                len(
                    self.context["documents"]
                ),

            "messages":
                len(
                    self.context["messages"]
                ),

            "entities":
                len(
                    self.context["entities"]
                ),

            "relationships":
                len(
                    self.context["relationships"]
                ),

            "analysis_results":
                len(
                    self.context["analysis_results"]
                ),

        }


    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Context metadata.
        """

        return {

            "type":
                "investigation_context",

            "sections":
                list(
                    self.context.keys()
                ),

        }
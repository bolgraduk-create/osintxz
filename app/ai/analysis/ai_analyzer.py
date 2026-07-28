"""
AI Analyzer.

Execution layer for AI-powered
investigation analysis.

Responsible for:

- preparing AI requests
- using RAG context
- executing AI generation
- returning structured results

Does NOT:

- store data
- access database
- replace analysis pipeline
"""

from __future__ import annotations

from typing import Any


from app.ai.rag.rag_engine import (
    RAGEngine,
)


class AIAnalyzer:
    """
    Main AI analysis executor.
    """


    def __init__(
        self,
        rag_engine: RAGEngine,
    ):
        """
        Initialize analyzer.
        """

        self.rag_engine = (
            rag_engine
        )


    # ==========================================================
    # Generic analysis
    # ==========================================================

    def analyze(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute generic AI analysis.
        """


        analysis_type = (
            data.get(
                "type",
                "general",
            )
        )


        content = (
            data.get(
                "content",
                "",
            )
        )


        question = (

            f"Perform {analysis_type} "
            "investigation analysis.\n\n"

            f"Data:\n{content}"

        )


        return self.rag_engine.query(
            question
        )


    # ==========================================================
    # Case analysis
    # ==========================================================

    def analyze_case(
        self,
        case: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Analyze investigation case.
        """


        return self.analyze(
            {
                "type":
                    "case",

                "content":
                    str(case),
            }
        )


    # ==========================================================
    # Document analysis
    # ==========================================================

    def analyze_document(
        self,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Analyze document.
        """


        return self.analyze(
            {
                "type":
                    "document",

                "content":
                    document.get(
                        "content",
                        "",
                    ),
            }
        )


    # ==========================================================
    # Message analysis
    # ==========================================================

    def analyze_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze message collection.
        """


        content = "\n".join(

            message.get(
                "text",
                "",
            )

            for message in messages

        )


        return self.analyze(
            {
                "type":
                    "messages",

                "content":
                    content,
            }
        )


    # ==========================================================
    # Questions
    # ==========================================================

    def ask(
        self,
        question: str,
    ) -> dict[str, Any]:
        """
        Ask investigation question.
        """


        return self.rag_engine.query(
            question
        )


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

            "type":
                "ai_analyzer",

            "rag_engine":
                self.rag_engine.metadata(),

        }
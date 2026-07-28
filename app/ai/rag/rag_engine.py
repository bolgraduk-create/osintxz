"""
RAG Engine.

Connects knowledge retrieval,
context preparation and AI generation.

Architecture:

User Query

    ↓

RAGEngine

    ↓

Retriever

    ↓

ContextBuilder

    ↓

AI Provider

    ↓

Response
"""

from __future__ import annotations

from typing import Any


from app.ai.rag.knowledge_store import (
    KnowledgeStore,
)

from app.ai.rag.retriever import (
    Retriever,
)

from app.ai.context.context_builder import (
    ContextBuilder,
)

from app.ai.base_ai import (
    BaseAI,
)


class RAGEngine:
    """
    Main RAG orchestration layer.

    Responsible for combining:
    - knowledge retrieval
    - context building
    - AI generation
    """


    def __init__(
        self,
        ai: BaseAI,
        knowledge_store: KnowledgeStore | None = None,
    ):
        """
        Initialize RAG engine.
        """


        self.ai = ai


        self.knowledge_store = (
            knowledge_store
            or KnowledgeStore()
        )


        self.retriever = Retriever(
            self.knowledge_store
        )


        self.context_builder = (
            ContextBuilder()
        )


    # ==========================================================
    # Knowledge
    # ==========================================================

    def add_knowledge(
        self,
        key: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add information to knowledge store.
        """


        self.knowledge_store.add(
            key=key,
            content=content,
            metadata=metadata,
        )


    # ==========================================================
    # Retrieval
    # ==========================================================

    def retrieve_context(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant knowledge.
        """


        return self.retriever.retrieve(
            query=query,
            limit=limit,
        )


    # ==========================================================
    # Prompt preparation
    # ==========================================================

    def build_prompt(
        self,
        query: str,
        context: list[dict[str, Any]],
    ) -> str:
        """
        Build AI prompt with context.
        """


        context_text = "\n\n".join(

            item["content"]

            for item in context

        )


        return (

            "Use the following investigation "
            "context to answer the question.\n\n"

            "Context:\n"

            f"{context_text}\n\n"

            "Question:\n"

            f"{query}"

        )


    # ==========================================================
    # Query
    # ==========================================================

    def query(
        self,
        question: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """
        Execute complete RAG flow.
        """


        context = (
            self.retrieve_context(
                question,
                limit,
            )
        )


        prompt = (
            self.build_prompt(
                question,
                context,
            )
        )


        response = (
            self.ai.generate(
                prompt
            )
        )


        return {

            "question":
                question,

            "context":
                context,

            "response":
                response,

        }


    # ==========================================================
    # Metadata
    #==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return engine metadata.
        """

        return {

            "type":
                "rag_engine",

            "knowledge":
                self.knowledge_store.metadata(),

            "retriever":
                self.retriever.metadata(),

        }
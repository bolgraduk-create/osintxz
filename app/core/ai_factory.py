"""
AI Factory.

Creates fully configured AI stack.

Architecture:

AIFactory

    ↓

Provider

    ↓

KnowledgeStore

    ↓

RAGEngine

    ↓

AIAnalyzer

This is the single place where
AI objects are created.
"""

from __future__ import annotations

import os

from app.ai.analysis.ai_analyzer import (
    AIAnalyzer,
)

from app.ai.rag.knowledge_store import (
    KnowledgeStore,
)

from app.ai.rag.rag_engine import (
    RAGEngine,
)

from app.ai.providers.ollama_provider import (
    OllamaProvider,
)

from app.ai.providers.openai_provider import (
    OpenAIProvider,
)


def create_ai_analyzer() -> AIAnalyzer:
    """
    Create fully configured AI analyzer.

    Provider selection:

    - OPENAI_API_KEY -> OpenAI
    - otherwise -> Ollama
    """

    api_key = os.getenv("OPENAI_API_KEY")

    if api_key:

        provider = OpenAIProvider(
            api_key=api_key,
        )

    else:

        provider = OllamaProvider()

    provider.initialize()

    connected = provider.connect()

    if not connected:

        raise RuntimeError(
            "Unable to connect AI provider."
        )

    knowledge_store = KnowledgeStore()

    rag_engine = RAGEngine(
        ai=provider,
        knowledge_store=knowledge_store,
    )

    analyzer = AIAnalyzer(
        rag_engine=rag_engine,
    )

    return analyzer
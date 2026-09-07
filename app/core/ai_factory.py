"""
AI Factory.

Creates the complete AI stack used by the application.

Composition:

AIManager
    ↓
ManagedAI
    ↓
KnowledgeStore
    ↓
RAGEngine
    ↓
AIAnalyzer

Provider selection is explicit and deterministic.

The provider is NOT connected during startup.
Connection happens lazily when the first AI request is executed.
"""

from __future__ import annotations

import os

from app.ai.ai_manager import (
    AIManager,
)

from app.ai.managed_ai import (
    ManagedAI,
)

from app.ai.analysis.ai_analyzer import (
    AIAnalyzer,
)

from app.ai.rag.knowledge_store import (
    KnowledgeStore,
)

from app.ai.rag.rag_engine import (
    RAGEngine,
)


DEFAULT_AI_PROVIDER = "ollama"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"

SUPPORTED_AI_PROVIDERS = frozenset(
    {
        "ollama",
        "openai",
    }
)


def _env_value(
    name: str,
) -> str | None:
    """
    Return a stripped non-empty environment value.
    """

    value = os.getenv(
        name
    )

    if value is None:
        return None

    normalized = str(
        value
    ).strip()

    return (
        normalized
        or None
    )


def resolve_ai_configuration() -> tuple[
    str,
    str,
]:
    """
    Resolve the configured AI provider and model.

    Contract:

    - AI_PROVIDER controls provider selection.
    - provider selection never depends on whether an API key exists.
    - OLLAMA_MODEL controls the Ollama model.
    - OPENAI_MODEL controls the OpenAI model.
    - legacy AI_MODEL is accepted only as an Ollama fallback.
    - legacy DEFAULT_MODEL is accepted only as a final Ollama fallback.

    This prevents a local model name such as ``qwen3:8b`` from
    accidentally being passed to an OpenAI provider merely because
    OPENAI_API_KEY is present in the environment.
    """

    provider_name = (
        _env_value(
            "AI_PROVIDER"
        )
        or DEFAULT_AI_PROVIDER
    ).lower()

    if (
        provider_name
        not in SUPPORTED_AI_PROVIDERS
    ):

        supported = ", ".join(
            sorted(
                SUPPORTED_AI_PROVIDERS
            )
        )

        raise ValueError(
            "Unsupported AI provider "
            f"'{provider_name}'. "
            f"Supported providers: {supported}."
        )

    if (
        provider_name
        == "ollama"
    ):

        model_name = (
            _env_value(
                "OLLAMA_MODEL"
            )
            or _env_value(
                "AI_MODEL"
            )
            or _env_value(
                "DEFAULT_MODEL"
            )
            or DEFAULT_OLLAMA_MODEL
        )

    else:

        model_name = (
            _env_value(
                "OPENAI_MODEL"
            )
            or DEFAULT_OPENAI_MODEL
        )

    return (
        provider_name,
        model_name,
    )


def create_ai_stack() -> tuple[
    AIManager,
    AIAnalyzer,
]:
    """
    Create the complete AI stack.

    Returns:

        (
            AIManager,
            AIAnalyzer,
        )

    The provider is neither initialized nor connected here.
    """

    (
        provider_name,
        model_name,
    ) = resolve_ai_configuration()

    manager = AIManager(
        provider_name=provider_name,
        model_name=model_name,
    )

    managed_ai = ManagedAI(
        manager
    )

    knowledge_store = (
        KnowledgeStore()
    )

    rag_engine = RAGEngine(
        ai=managed_ai,
        knowledge_store=knowledge_store,
    )

    analyzer = AIAnalyzer(
        rag_engine=rag_engine,
    )

    return (
        manager,
        analyzer,
    )


def create_ai_analyzer() -> AIAnalyzer:
    """
    Backward-compatible helper.

    Existing code may still call this function.
    """

    _, analyzer = create_ai_stack()

    return analyzer

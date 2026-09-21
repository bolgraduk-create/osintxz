"""AI stack composition for OSINTXZ.

The application has one generation/reasoning provider selected through the
central Settings object.  Provider initialization and network use remain lazy,
so a missing cloud/local backend never prevents the desktop from starting.

R13.28a makes OpenAI the default analysis provider while preserving Ollama as a
supported fallback.  Embedding services are configured separately and are not
changed by this module.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from app.ai.ai_manager import AIManager
from app.ai.analysis.ai_analyzer import AIAnalyzer
from app.ai.managed_ai import ManagedAI
from app.ai.rag.knowledge_store import KnowledgeStore
from app.ai.rag.rag_engine import RAGEngine
from app.core.config import Settings, settings


DEFAULT_AI_PROVIDER = "ollama"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
DEFAULT_OPENAI_MODEL = "gpt-5.6"

SUPPORTED_AI_PROVIDERS = frozenset({"ollama", "openai"})


def resolve_ai_configuration(
    config: Settings = settings,
) -> tuple[str, str]:
    """Resolve provider/model only from the central application settings."""

    provider_name = str(
        getattr(config, "ai_provider", None) or DEFAULT_AI_PROVIDER
    ).strip().casefold()

    if provider_name not in SUPPORTED_AI_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_AI_PROVIDERS))
        raise ValueError(
            f"Unsupported AI provider '{provider_name}'. "
            f"Supported providers: {supported}."
        )

    if provider_name == "openai":
        model_name = str(
            getattr(config, "openai_model", None) or DEFAULT_OPENAI_MODEL
        ).strip()
    else:
        model_name = str(
            getattr(config, "ollama_model", None)
            or getattr(config, "ai_model", None)
            or getattr(config, "default_model", None)
            or DEFAULT_OLLAMA_MODEL
        ).strip()

    if not model_name:
        raise ValueError("Configured AI model name cannot be empty.")

    return provider_name, model_name


def _provider_config(
    *,
    config: Settings,
    provider_name: str,
) -> dict[str, object]:
    """Return provider-specific runtime config without exposing secrets."""

    if provider_name == "openai":
        secret = getattr(config, "openai_api_key", None)
        api_key = (
            secret.get_secret_value().strip()
            if secret is not None
            else ""
        )
        return {
            "api_key": api_key or None,
            "reasoning_effort": str(
                getattr(config, "openai_reasoning_effort", "medium")
                or "medium"
            ).strip().casefold(),
            "timeout_seconds": float(
                getattr(config, "openai_timeout_seconds", 120.0) or 120.0
            ),
            "store_responses": bool(
                getattr(config, "openai_store_responses", False)
            ),
        }

    # Preserve the existing Ollama provider contract while sourcing the host
    # from Settings instead of reading the environment directly.
    raw = str(getattr(config, "ollama_url", "") or "").strip()
    parsed = urlsplit(raw if "://" in raw else f"http://{raw}")
    host = parsed.hostname or "localhost"
    port = int(parsed.port or 11434)
    return {
        "host": host,
        "port": port,
    }


def create_ai_stack(
    config: Settings = settings,
    *,
    provider_name: str | None = None,
    model_name: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[AIManager, AIAnalyzer]:
    """Create the complete lazy AI stack.

    Optional runtime overrides are used by the desktop Analysis workspace.
    They do not mutate global Settings and therefore let one analysis run use
    OpenAI while another uses Ollama in the same application session.
    """

    configured_provider, configured_model = resolve_ai_configuration(config)
    selected_provider = str(
        provider_name or configured_provider
    ).strip().casefold()

    if selected_provider not in SUPPORTED_AI_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_AI_PROVIDERS))
        raise ValueError(
            f"Unsupported AI provider '{selected_provider}'. "
            f"Supported providers: {supported}."
        )

    if str(model_name or "").strip():
        selected_model = str(model_name).strip()
    elif selected_provider == configured_provider:
        selected_model = configured_model
    elif selected_provider == "openai":
        selected_model = str(
            getattr(config, "openai_model", None) or DEFAULT_OPENAI_MODEL
        ).strip()
    else:
        selected_model = str(
            getattr(config, "ollama_model", None)
            or getattr(config, "ai_model", None)
            or getattr(config, "default_model", None)
            or DEFAULT_OLLAMA_MODEL
        ).strip()

    if not selected_model:
        raise ValueError("Configured AI model name cannot be empty.")

    provider_config = _provider_config(
        config=config,
        provider_name=selected_provider,
    )
    if (
        selected_provider == "openai"
        and reasoning_effort is not None
        and str(reasoning_effort).strip()
    ):
        provider_config["reasoning_effort"] = (
            str(reasoning_effort).strip().casefold()
        )

    manager = AIManager(
        provider_name=selected_provider,
        model_name=selected_model,
        **provider_config,
    )

    managed_ai = ManagedAI(manager)
    knowledge_store = KnowledgeStore()
    rag_engine = RAGEngine(
        ai=managed_ai,
        knowledge_store=knowledge_store,
    )
    analyzer = AIAnalyzer(
        rag_engine=rag_engine,
    )

    return manager, analyzer


def create_ai_analyzer(
    config: Settings = settings,
) -> AIAnalyzer:
    """Backward-compatible helper."""

    _, analyzer = create_ai_stack(config)
    return analyzer

"""
Managed AI adapter.

Bridges AIManager with the high-level BaseAI contract.

Responsible for:

- exposing the BaseAI interface
- lazily initializing the configured provider
- lazily connecting to the AI backend
- delegating generation to AIManager

Does NOT:

- build prompts
- access the database
- store analysis results
- contain UI logic
"""

from __future__ import annotations

from typing import Any

from app.ai.ai_manager import (
    AIManager,
)

from app.ai.base_ai import (
    BaseAI,
)


class ManagedAI(
    BaseAI,
):
    """
    High-level AI adapter backed by AIManager.

    The provider is initialized and connected only when generation
    is requested. This allows the desktop application to start even
    when Ollama or another configured backend is offline.
    """

    def __init__(
        self,
        manager: AIManager,
    ) -> None:

        if not isinstance(
            manager,
            AIManager,
        ):

            raise TypeError(
                "manager must be an AIManager instance."
            )

        model_name = str(
            manager.model_name
            or "unknown-model"
        ).strip()

        super().__init__(
            model_name=model_name,
        )

        self.manager = manager

    # ==========================================================
    # Generation
    # ==========================================================

    def generate(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """
        Generate an AI response through the managed provider.
        """

        normalized_prompt = str(
            prompt
            or ""
        ).strip()

        if not normalized_prompt:

            raise ValueError(
                "AI prompt cannot be empty."
            )

        self.ensure_ready()

        response = self.manager.generate(
            normalized_prompt,
            **kwargs,
        )

        normalized_response = str(
            response
            or ""
        ).strip()

        if not normalized_response:

            raise ValueError(
                "The AI provider returned an empty response."
            )

        return normalized_response

    # ==========================================================
    # Provider state
    # ==========================================================

    def ensure_ready(
        self,
    ) -> None:
        """
        Initialize and connect the configured provider when needed.
        """

        if self.manager.provider is None:

            self.manager.initialize()

        if self.manager.health_check():

            return

        connected = self.manager.connect()

        if not connected:

            raise RuntimeError(
                "The configured AI provider is unavailable."
            )

    def health_check(
        self,
    ) -> bool:
        """
        Return whether the configured provider is currently ready.
        """

        return self.manager.health_check()

    def close(
        self,
    ) -> None:
        """
        Close the current provider resources.
        """

        provider = self.manager.provider

        if provider is not None:

            provider.close()

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return managed AI metadata.
        """

        return {
            "type": "managed_ai",
            "model": self.manager.model_name,
            "provider_name": (
                self.manager.provider_name
            ),
            "ready": self.manager.health_check(),
            "provider": self.manager.metadata(),
        }
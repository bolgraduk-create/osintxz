"""
AI Manager.

Controls AI providers
and AI workflow execution.
"""

from __future__ import annotations

from typing import Any


from app.ai.providers.ollama_provider import (
    OllamaProvider,
)

from app.ai.providers.openai_provider import (
    OpenAIProvider,
)

from app.ai.providers.mock_provider import (
    MockProvider,
)



class AIManager:
    """
    Central AI provider manager.
    """



    def __init__(
        self,
        provider_name: str = "ollama",
        model_name: str | None = None,
        **config: Any,
    ):
        """
        Initialize AI manager.
        """

        self.provider_name = provider_name

        self.model_name = model_name

        self.config = config

        self.provider = None



    # ==========================================================
    # Initialization
    # ==========================================================


    def initialize(
        self,
    ) -> None:
        """
        Create selected provider.
        """


        if self.provider_name == "ollama":

            self.provider = OllamaProvider(

                model_name=
                    self.model_name
                    or "llama3",

                **self.config,
            )



        elif self.provider_name == "openai":

            self.provider = OpenAIProvider(

                model_name=
                    self.model_name
                    or "gpt-5.6",

                **self.config,
            )



        elif self.provider_name == "mock":

            self.provider = MockProvider(

                model_name=
                    self.model_name
                    or "mock-model",

                **self.config,
            )



        else:

            raise ValueError(
                f"Unknown AI provider: {self.provider_name}"
            )



        self.provider.initialize()



    # ==========================================================
    # Connection
    # ==========================================================


    def connect(
        self,
    ) -> bool:
        """
        Connect provider.
        """

        if self.provider is None:

            raise RuntimeError(
                "AI provider is not initialized"
            )


        return self.provider.connect()



    # ==========================================================
    # Generation
    # ==========================================================


    def generate(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """
        Generate AI response.
        """

        if self.provider is None:

            raise RuntimeError(
                "AI provider is not initialized"
            )


        return self.provider.generate(
            prompt,
            **kwargs,
        )



    # ==========================================================
    # Usage telemetry
    # ==========================================================

    def usage_snapshot(
        self,
    ) -> dict[str, Any]:
        """Return provider-reported usage without triggering a request."""

        if self.provider is None:
            return {
                "provider": self.provider_name,
                "requests": 0,
                "inputTokens": 0,
                "cachedInputTokens": 0,
                "outputTokens": 0,
                "reasoningTokens": 0,
                "totalTokens": 0,
                "events": [],
            }

        method = getattr(
            self.provider,
            "usage_snapshot",
            None,
        )
        if not callable(method):
            return {
                "provider": self.provider_name,
                "requests": 0,
                "inputTokens": 0,
                "cachedInputTokens": 0,
                "outputTokens": 0,
                "reasoningTokens": 0,
                "totalTokens": 0,
                "events": [],
            }

        result = method()
        return dict(result) if isinstance(result, dict) else {}

    # ==========================================================
    # Information
    # ==========================================================


    def info(
        self,
    ) -> dict[str, Any]:
        """
        Return AI information.
        """

        if self.provider is None:

            return {}


        return self.provider.get_model_info()



    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return provider metadata.
        """

        if self.provider is None:

            return {}


        return self.provider.metadata()



    def health_check(
        self,
    ) -> bool:
        """
        Check AI availability.
        """

        if self.provider is None:

            return False


        return self.provider.health_check()
"""
OpenAI AI Provider.

Connects application AI layer
with OpenAI compatible models.

Architecture:

BaseProvider
      ↓
OpenAIProvider
      ↓
OpenAI API
      ↓
Cloud LLM
"""

from __future__ import annotations

from typing import Any

from app.ai.providers.base_provider import (
    BaseProvider,
)


class OpenAIProvider(
    BaseProvider,
):
    """
    OpenAI implementation
    of AI provider.

    The provider does not store
    API keys internally.
    Configuration is injected.
    """


    def __init__(
        self,
        model_name: str = "gpt-4.1-mini",
        api_key: str | None = None,
        **config: Any,
    ):
        """
        Initialize OpenAI provider.
        """

        super().__init__(
            model_name,
            **config,
        )


        self.api_key = api_key

        self.client = None


    # ==========================================================
    # Lifecycle
    # ==========================================================

    def initialize(
        self,
    ) -> None:
        """
        Initialize OpenAI client.
        """


        if not self.api_key:

            self.connected = False

            return


        try:

            from openai import (
                OpenAI,
            )


            self.client = OpenAI(
                api_key=self.api_key
            )


        except ImportError:

            self.client = None



    def connect(
        self,
    ) -> bool:
        """
        Verify OpenAI availability.
        """


        if (
            self.client is None
        ):

            self.connected = False

            return False


        try:

            self.client.models.list()

            self.connected = True


        except Exception:

            self.connected = False


        return self.connected


    # ==========================================================
    # Generation
    # ==========================================================

    def generate(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """
        Generate response
        using OpenAI model.
        """


        if not self.connected:

            raise RuntimeError(
                "OpenAI provider is not connected"
            )


        response = (
            self.client.chat.completions.create(
                model=self.model_name,

                messages=[
                    {
                        "role":
                            "user",

                        "content":
                            prompt,
                    }
                ],

                **kwargs,
            )
        )


        return (
            response
            .choices[0]
            .message
            .content
            or ""
        )


    # ==========================================================
    # Information
    # ==========================================================

    def get_model_info(
        self,
    ) -> dict[str, Any]:
        """
        Return OpenAI information.
        """

        return {

            "provider":
                "openai",

            "model":
                self.model_name,

            "connected":
                self.connected,

        }


    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Provider metadata.
        """

        return {

            "type":
                "openai",

            "model":
                self.model_name,

            "status":
                (
                    "ready"
                    if self.connected
                    else "offline"
                ),

        }
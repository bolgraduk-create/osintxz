"""
Ollama AI Provider.

Connects application AI layer
with local Ollama models.

Architecture:

BaseProvider
      ↓
OllamaProvider
      ↓
Ollama API
      ↓
Local LLM
"""

from __future__ import annotations

from typing import Any

import json

from urllib.request import (
    Request,
    urlopen,
)

from urllib.error import (
    URLError,
)


from app.ai.providers.base_provider import (
    BaseProvider,
)


class OllamaProvider(
    BaseProvider,
):
    """
    Ollama implementation
    of AI provider.
    """


    def __init__(
        self,
        model_name: str = "llama3",
        host: str = "localhost",
        port: int = 11434,
        **config: Any,
    ):
        """
        Initialize Ollama provider.
        """

        super().__init__(
            model_name,
            **config,
        )


        self.host = host

        self.port = port


        self.base_url = (
            f"http://{host}:{port}"
        )


    # ==========================================================
    # Lifecycle
    # ==========================================================

    def initialize(
        self,
    ) -> None:
        """
        Initialize provider.

        Connection is established
        separately.
        """

        self.connected = False


    def connect(
        self,
    ) -> bool:
        """
        Check Ollama availability.
        """

        try:

            request = Request(
                self.base_url,
                method="GET",
            )


            with urlopen(
                request,
                timeout=3,
            ):

                self.connected = True


        except (
            URLError,
            TimeoutError,
        ):

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
        Generate response using Ollama.
        """


        if not self.connected:

            raise RuntimeError(
                "Ollama provider is not connected"
            )


        payload = {

            "model":
                self.model_name,

            "prompt":
                prompt,

            "stream":
                False,

        }


        payload.update(
            kwargs
        )


        request = Request(

            f"{self.base_url}/api/generate",

            data=json.dumps(
                payload
            ).encode(
                "utf-8"
            ),

            headers={
                "Content-Type":
                    "application/json",
            },

            method="POST",
        )


        with urlopen(
            request,
            timeout=120,
        ) as response:

            data = json.loads(
                response.read()
                .decode(
                    "utf-8"
                )
            )


        return data.get(
            "response",
            "",
        )


    # ==========================================================
    # Information
    # ==========================================================

    def get_model_info(
        self,
    ) -> dict[str, Any]:
        """
        Return Ollama information.
        """

        return {

            "provider":
                "ollama",

            "model":
                self.model_name,

            "host":
                self.host,

            "port":
                self.port,

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
                "ollama",

            "model":
                self.model_name,

            "status":
                (
                    "ready"
                    if self.connected
                    else "offline"
                ),

        }
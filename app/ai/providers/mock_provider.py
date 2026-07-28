"""
Mock AI Provider.

Used for testing AI workflows
without external AI services.

Implements the same interface
as real providers.
"""

from __future__ import annotations

from typing import Any

from app.ai.providers.base_provider import (
    BaseProvider,
)


class MockProvider(
    BaseProvider,
):
    """
    Fake AI provider for tests.
    """

    def __init__(
        self,
        model_name: str = "mock-model",
        **config: Any,
    ):
        """
        Initialize mock provider.
        """

        super().__init__(
            model_name,
            **config,
        )


    # ==========================================================
    # Lifecycle
    # ==========================================================

    def initialize(
        self,
    ) -> None:
        """
        Initialize provider.
        """

        self.connected = False



    def connect(
        self,
    ) -> bool:
        """
        Simulate connection.
        """

        self.connected = True

        return True



    def close(
        self,
    ) -> None:
        """
        Close provider.
        """

        self.connected = False



    # ==========================================================
    # Generation
    # ==========================================================

    def generate(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """
        Return deterministic test response.
        """

        return """
Mock AI analysis result.

Detected entities:

- Person A
- Organization B


Detected relationships:

- Person A connected with Organization B


Conclusion:

Investigation data analyzed successfully.
"""


    # ==========================================================
    # Information
    # ==========================================================

    def get_model_info(
        self,
    ) -> dict[str, Any]:
        """
        Return model information.
        """

        return {

            "provider":
                "mock",

            "model":
                self.model_name,

            "connected":
                self.connected,

        }



    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return metadata.
        """

        return {

            "type":
                "mock",

            "model":
                self.model_name,

            "status":
                (
                    "ready"
                    if self.connected
                    else "offline"
                ),

        }



    def health_check(
        self,
    ) -> bool:
        """
        Check provider state.
        """

        return self.connected
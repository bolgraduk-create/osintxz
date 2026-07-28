"""
Base AI Provider.

Defines common provider lifecycle
and communication interface.

Architecture:

BaseAI
    ↓
BaseProvider
    ↓
Concrete Providers
    ↓
AI Models
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from typing import Any


class BaseProvider(ABC):
    """
    Abstract AI provider.

    Every provider implementation
    must inherit from this class.
    """


    def __init__(
        self,
        model_name: str,
        **config: Any,
    ):
        """
        Initialize provider.
        """

        self.model_name = model_name

        self.config = config

        self.connected = False


    # ==========================================================
    # Lifecycle
    # ==========================================================

    @abstractmethod
    def initialize(
        self,
    ) -> None:
        """
        Prepare provider resources.
        """

        pass


    @abstractmethod
    def connect(
        self,
    ) -> bool:
        """
        Establish connection
        with AI backend.
        """

        pass


    def close(
        self,
    ) -> None:
        """
        Close provider resources.
        """

        self.connected = False


    # ==========================================================
    # Generation
    # ==========================================================

    @abstractmethod
    def generate(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """
        Generate AI response.
        """

        pass


    # ==========================================================
    # Health
    # ==========================================================

    def health_check(
        self,
    ) -> bool:
        """
        Check provider availability.
        """

        return self.connected


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
            "model": self.model_name,
            "provider": (
                self.__class__.__name__
            ),
            "connected": self.connected,
        }


    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Provider metadata.
        """

        return {
            "provider": (
                self.__class__.__name__
            ),
            "model": self.model_name,
            "status": (
                "connected"
                if self.connected
                else "disconnected"
            ),
        }
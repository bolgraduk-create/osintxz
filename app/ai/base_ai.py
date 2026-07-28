"""
Base AI interface.

Defines common contract for all AI engines.

All AI providers must implement
this interface.

Architecture:

AI Service
    ↓
BaseAI
    ↓
Providers
    ↓
Models
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from typing import Any


class BaseAI(ABC):
    """
    Abstract AI engine.

    Every AI provider must inherit
    from this class.
    """


    def __init__(
        self,
        model_name: str,
    ):
        self.model_name = model_name


    # ==========================================================
    # Core generation
    # ==========================================================

    @abstractmethod
    def generate(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """
        Generate AI response.

        Must be implemented
        by every provider.
        """

        pass


    # ==========================================================
    # Analysis operations
    # ==========================================================

    def analyze(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform structured analysis.
        """


        prompt = self.build_analysis_prompt(
            text,
            context,
        )


        response = self.generate(
            prompt
        )


        return {
            "result": response,
            "model": self.model_name,
        }


    def summarize(
        self,
        text: str,
    ) -> str:
        """
        Summarize text.
        """


        prompt = (
            "Summarize the following text:\n\n"
            f"{text}"
        )


        return self.generate(
            prompt
        )


    def extract(
        self,
        text: str,
    ) -> dict[str, Any]:
        """
        Extract information.
        """


        prompt = (
            "Extract important information "
            "from the text:\n\n"
            f"{text}"
        )


        response = self.generate(
            prompt
        )


        return {
            "extracted": response,
        }


    # ==========================================================
    # Prompt helpers
    # ==========================================================

    def build_analysis_prompt(
        self,
        text: str,
        context: dict[str, Any] | None,
    ) -> str:
        """
        Build default analysis prompt.
        """


        prompt = (
            "Analyze the following information:\n\n"
            f"{text}"
        )


        if context:

            prompt += (
                "\n\nAdditional context:\n"
                f"{context}"
            )


        return prompt


    # ==========================================================
    # Validation
    # ==========================================================

    def validate_response(
        self,
        response: str,
    ) -> bool:
        """
        Validate AI output.
        """


        if not response:
            return False


        return True


    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return AI engine metadata.
        """


        return {
            "model": self.model_name,
            "type": self.__class__.__name__,
        }
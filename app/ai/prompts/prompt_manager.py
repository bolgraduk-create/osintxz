"""
Prompt Manager.

Responsible for storing, managing
and rendering AI prompts.

Architecture:

AI Analysis Service
        ↓
PromptManager
        ↓
Prompt Template
        ↓
AI Provider
"""

from __future__ import annotations

from datetime import datetime

from typing import Any


class PromptManager:
    """
    Manages AI prompt templates.
    """


    def __init__(
        self,
    ):
        """
        Initialize prompt storage.
        """


        self.prompts: dict[str, dict[str, Any]] = {}


        self._load_default_prompts()


    # ==========================================================
    # Registration
    # ==========================================================

    def register_prompt(
        self,
        name: str,
        template: str,
        description: str = "",
        version: str = "1.0",
    ) -> None:
        """
        Register new prompt template.
        """


        self.prompts[name] = {

            "template":
                template,

            "description":
                description,

            "version":
                version,

            "created_at":
                datetime.utcnow(),

        }


    # ==========================================================
    # Retrieval
    # ==========================================================

    def get_prompt(
        self,
        name: str,
    ) -> dict[str, Any] | None:
        """
        Return prompt information.
        """

        return self.prompts.get(
            name
        )


    # ==========================================================
    # Rendering
    # ==========================================================

    def render_prompt(
        self,
        name: str,
        variables: dict[str, Any],
    ) -> str:
        """
        Render prompt template.
        """


        prompt = self.get_prompt(
            name
        )


        if prompt is None:

            raise KeyError(
                f"Prompt '{name}' not found"
            )


        template = prompt[
            "template"
        ]


        return template.format(
            **variables
        )


    # ==========================================================
    # Management
    # ==========================================================

    def list_prompts(
        self,
    ) -> list[str]:
        """
        Return available prompts.
        """


        return list(
            self.prompts.keys()
        )


    def remove_prompt(
        self,
        name: str,
    ) -> bool:
        """
        Remove prompt template.
        """


        if name not in self.prompts:

            return False


        del self.prompts[name]


        return True


    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return manager information.
        """


        return {

            "total_prompts":
                len(
                    self.prompts
                ),

            "prompts":
                self.list_prompts(),

        }


    # ==========================================================
    # Default prompts
    # ==========================================================

    def _load_default_prompts(
        self,
    ) -> None:
        """
        Load system prompts.
        """


        self.register_prompt(

            name="entity_analysis",

            template=(
                "Analyze entities in the following "
                "investigation text:\n\n"
                "{text}"
            ),

            description=(
                "Extract persons, organizations "
                "and locations."
            ),

        )


        self.register_prompt(

            name="relationship_analysis",

            template=(
                "Analyze relationships between "
                "entities:\n\n"
                "{text}"
            ),

            description=(
                "Find connections and interactions."
            ),

        )


        self.register_prompt(

            name="summary",

            template=(
                "Create an investigation summary "
                "from this information:\n\n"
                "{text}"
            ),

            description=(
                "Generate structured summary."
            ),

        )
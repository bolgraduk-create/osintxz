"""
Investigation RAG prompt service.

Connects the new investigation RAG context contract to the
existing central PromptManager.

Architecture:

InvestigationRAGContext
        ↓
InvestigationRAGPromptService
        ↓
existing PromptManager
        ↓
render_prompt(...)
        ↓
InvestigationRAGPrompt
        ↓
future AI execution layer

Responsibilities:

- register the RAG investigation prompt in the existing
  PromptManager when necessary
- transform InvestigationRAGContext into prompt variables
- render the prompt through PromptManager
- preserve R1 / R2 / R3 source references
- expose stable prompt metadata
- keep user question separate from retrieved source material
- make epistemic boundaries explicit to the model

Does NOT:

- create another PromptManager implementation
- perform retrieval
- build RAG context
- call Ollama or AIManager
- generate an AI response
- validate model-generated citations
- create evidence
- change evidence confidence
- perform Entity Resolution
- write to the database

Important boundaries:

retrieval score != evidence confidence
M024 evidence confidence != general source truth
retrieved source != verified fact
model statement != investigation fact
source reference != validated grounded citation

Grounded citation validation is implemented later in Block 9.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from uuid import UUID

from app.ai.prompts.prompt_manager import (
    PromptManager,
)
from app.security.sensitive_content import (
    sanitize_sensitive_text,
)

from app.services.investigation_rag_context_builder import (
    InvestigationRAGContext,
)


# ==========================================================
# Constants
# ==========================================================

RAG_INVESTIGATION_PROMPT_NAME = (
    "rag_investigation_question"
)

RAG_INVESTIGATION_PROMPT_VERSION = (
    "1.0"
)

RAG_INVESTIGATION_PROMPT_CATEGORY = (
    "investigation"
)


# ==========================================================
# Rendered prompt contract
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGPrompt:
    """
    One fully rendered RAG investigation prompt.

    This object contains a prompt ready for the existing
    AI execution layer.

    It does NOT contain an AI response.
    """

    name: str

    version: str

    category: str

    question: str

    case_id: UUID

    text: str

    source_references: tuple[
        str,
        ...,
    ]

    included_source_count: int

    context_characters: int

    prompt_characters: int

    context_warnings: tuple[
        str,
        ...,
    ] = ()

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    # ======================================================
    # Helpers
    # ======================================================

    @property
    def has_sources(
        self,
    ) -> bool:
        """
        Whether at least one investigation source is present.
        """

        return bool(
            self.source_references
        )

    @property
    def is_empty(
        self,
    ) -> bool:
        """
        Whether rendered prompt text is empty.
        """

        return not bool(
            self.text.strip()
        )


# ==========================================================
# Service
# ==========================================================


class InvestigationRAGPromptService:
    """
    RAG-specific adapter over the existing PromptManager.

    The PromptManager remains the single template registry
    and rendering mechanism.
    """

    def __init__(
        self,
        *,
        prompt_manager: PromptManager,
    ) -> None:

        if not isinstance(
            prompt_manager,
            PromptManager,
        ):

            raise TypeError(
                "prompt_manager must be PromptManager."
            )

        self.prompt_manager = (
            prompt_manager
        )

        self._ensure_prompt()

    # ======================================================
    # Public API
    # ======================================================

    def build(
        self,
        context: InvestigationRAGContext,
    ) -> InvestigationRAGPrompt:
        """
        Render one investigation RAG prompt.

        Source ordering and source references come directly
        from InvestigationRAGContext and are never changed.
        """

        if not isinstance(
            context,
            InvestigationRAGContext,
        ):

            raise TypeError(
                "context must be InvestigationRAGContext."
            )

        question = self._normalize_question(
            context.question
        )
        safe_question = sanitize_sensitive_text(
            question
        )

        source_references = tuple(
            source.reference_id
            for source in (
                context.included_sources
            )
        )

        context_text = (
            context.text.strip()
        )
        safe_context = sanitize_sensitive_text(
            context_text
        )
        context_text = safe_context.text

        if not context_text:

            context_text = (
                "[NO RETRIEVED INVESTIGATION CONTEXT]\n"
                "No investigation source was available "
                "for this question."
            )

        rendered = (
            self.prompt_manager
            .render_prompt(
                RAG_INVESTIGATION_PROMPT_NAME,
                {
                    "question": safe_question.text,
                    "context": context_text,
                },
            )
        )

        rendered = str(
            rendered
            or ""
        ).strip()

        if not rendered:

            raise ValueError(
                "PromptManager returned an empty "
                "RAG prompt."
            )

        prompt_metadata = (
            self.prompt_manager
            .get_prompt(
                RAG_INVESTIGATION_PROMPT_NAME
            )
            or {}
        )

        return InvestigationRAGPrompt(
            name=(
                RAG_INVESTIGATION_PROMPT_NAME
            ),

            version=str(
                prompt_metadata.get(
                    "version",
                    RAG_INVESTIGATION_PROMPT_VERSION,
                )
            ),

            category=str(
                prompt_metadata.get(
                    "category",
                    RAG_INVESTIGATION_PROMPT_CATEGORY,
                )
            ),

            question=question,

            case_id=(
                context.case_id
            ),

            text=rendered,

            source_references=(
                source_references
            ),

            included_source_count=(
                context.included_source_count
            ),

            context_characters=(
                context.used_chars
            ),

            prompt_characters=len(
                rendered
            ),

            context_warnings=(
                context.warnings
            ),

            metadata={
                "prompt_manager": (
                    self.prompt_manager
                    .__class__
                    .__name__
                ),
                "context_source_count": (
                    context.available_source_count
                ),
                "included_source_count": (
                    context.included_source_count
                ),
                "truncated_source_count": (
                    context.truncated_source_count
                ),
                "skipped_source_count": (
                    context.skipped_source_count
                ),
                "has_context": (
                    context.has_context
                ),
                "sensitive_redaction_count": (
                    safe_question.redaction_count
                    + safe_context.redaction_count
                ),
                "sensitive_material_redacted": bool(
                    safe_question.redacted
                    or safe_context.redacted
                ),
            },
        )

    # ======================================================
    # Prompt registration
    # ======================================================

    def _ensure_prompt(
        self,
    ) -> None:
        """
        Ensure RAG prompt exists inside the existing
        PromptManager registry.

        Existing registration is preserved instead of being
        silently overwritten.
        """

        if not self.prompt_manager.has_prompt(
            RAG_INVESTIGATION_PROMPT_NAME
        ):

            self.prompt_manager.register_prompt(
                name=(
                    RAG_INVESTIGATION_PROMPT_NAME
                ),

                category=(
                    RAG_INVESTIGATION_PROMPT_CATEGORY
                ),

                version=(
                    RAG_INVESTIGATION_PROMPT_VERSION
                ),

                description=(
                    "Answer an investigation question using "
                    "only bounded RAG investigation context."
                ),

                required_variables=(
                    "question",
                    "context",
                ),

                template=(
                    "You are an investigation analysis assistant.\n\n"

                    "Answer the investigation question using ONLY "
                    "the investigation context supplied below.\n\n"

                    "QUESTION:\n"
                    "{question}\n\n"

                    "INVESTIGATION CONTEXT:\n"
                    "{context}\n\n"

                    "IMPORTANT RULES:\n"
                    "- Treat retrieved material as source material, "
                    "not automatically as verified fact.\n"
                    "- Do not invent facts, identities, events, "
                    "relationships, motives, dates or evidence.\n"
                    "- Distinguish direct source content from "
                    "analytical inference.\n"
                    "- If sources conflict, describe the conflict "
                    "instead of choosing one without support.\n"
                    "- If the supplied context is insufficient, "
                    "state that clearly.\n"
                    "- retrieval_score represents search relevance, "
                    "not evidence confidence.\n"
                    "- When evidence_confidence is present, it is the "
                    "canonical M024 confidence for a specific proposition, "
                    "not a general truth score for the whole source.\n"
                    "- evidence_confidence_coverage describes how much of "
                    "the reliability/independence assessment was observable; "
                    "low coverage must be stated as uncertainty.\n"
                    "- Never invent, estimate or extrapolate confidence "
                    "numbers that are not supplied in the context.\n"
                    "- Do not treat two similar identities as the "
                    "same person or entity unless the supplied "
                    "context establishes that conclusion.\n"
                    "- Preserve source references such as R1, R2 "
                    "and R3 when discussing source-specific "
                    "information.\n"
                    "- Do not claim that a source reference is a "
                    "validated citation; citation validation occurs "
                    "in a separate investigation layer.\n\n"

                    "RESPONSE STRUCTURE:\n"
                    "1. Answer\n"
                    "2. Supporting source references\n"
                    "3. Contradictions or uncertainties\n"
                    "4. Missing information or limitations\n\n"

                    "Be precise and evidence-oriented."
                ),
            )

        self._validate_registered_prompt()

    def _validate_registered_prompt(
        self,
    ) -> None:
        """
        Ensure an existing prompt with the same name remains
        compatible with this RAG adapter.
        """

        required = set(
            self.prompt_manager
            .get_required_variables(
                RAG_INVESTIGATION_PROMPT_NAME
            )
        )

        expected = {
            "question",
            "context",
        }

        if required != expected:

            raise RuntimeError(
                "Registered RAG prompt has incompatible "
                "required variables. Expected exactly: "
                "question, context."
            )

    # ======================================================
    # Validation
    # ======================================================

    @staticmethod
    def _normalize_question(
        question: str,
    ) -> str:
        """
        Normalize investigation question.
        """

        if not isinstance(
            question,
            str,
        ):

            raise TypeError(
                "Investigation question must be a string."
            )

        normalized = (
            question.strip()
        )

        if not normalized:

            raise ValueError(
                "Investigation question cannot be empty."
            )

        return normalized

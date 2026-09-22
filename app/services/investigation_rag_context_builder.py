"""
Investigation RAG context builder.

Transforms already-retrieved investigation sources into
a bounded, deterministic context package suitable for the
future Prompt Layer.

Architecture:

InvestigationRAGRetrievalResult
        ↓
InvestigationRAGContextBuilder
        ↓
bounded structured context
        ↓
future Prompt Layer
        ↓
future Ollama execution

Responsibilities:

- preserve R1 / R2 / R3 source references
- preserve Unified Search ordering
- preserve investigation object identity
- extract textual source content safely
- fall back to search snippets when full content is unavailable
- enforce per-source text limits
- enforce global context limits
- report full / truncated / skipped source state
- keep provenance available for later citation processing

Does NOT:

- perform retrieval
- call UnifiedSearchService
- calculate embeddings
- rerank sources
- call Ollama
- build final prompts
- generate conclusions
- create grounded citations
- modify evidence confidence
- perform Entity Resolution
- write to the database

Important boundaries:

retrieval score != evidence confidence
retrieved text != verified fact
context inclusion != factual validation
R1 / R2 / R3 != final grounded citation format

The final grounded citation layer is implemented later
in Block 9.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from uuid import UUID

from app.services.investigation_rag_retrieval_service import (
    InvestigationRAGRetrievalResult,
    InvestigationRAGSource,
)


# ==========================================================
# Defaults
# ==========================================================

DEFAULT_MAX_CONTEXT_CHARS = 12_000

DEFAULT_MAX_SOURCE_CHARS = 3_000

DEFAULT_MAX_TITLE_CHARS = 300


# ==========================================================
# Source state
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGContextSource:
    """
    Context-building state for one retrieved source.

    status values:

    full
        Entire available source text was included.

    truncated
        Source text was shortened because of either the
        per-source or global context budget.

    skipped_empty
        No usable text could be extracted.

    skipped_budget
        Source could not fit into the remaining global
        context budget.

    `final_score` remains a retrieval relevance score only.
    """

    reference_id: str

    object_id: UUID

    object_type: str

    case_id: UUID | None

    title: str

    status: str

    included: bool

    text: str

    original_length: int

    included_length: int

    final_score: float

    matched_methods: tuple[
        str,
        ...,
    ]

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    @property
    def truncated(
        self,
    ) -> bool:
        """
        Whether the source entered context only partially.
        """

        return (
            self.status
            ==
            "truncated"
        )

    @property
    def skipped(
        self,
    ) -> bool:
        """
        Whether the source was not included.
        """

        return not self.included


# ==========================================================
# Context contract
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGContext:
    """
    Structured context produced for the future Prompt Layer.

    `text` contains only source blocks.

    The investigation question remains separate so the
    Prompt Layer can decide how to place user instructions
    relative to evidence context.
    """

    question: str

    case_id: UUID

    text: str

    sources: tuple[
        InvestigationRAGContextSource,
        ...,
    ]

    max_context_chars: int

    max_source_chars: int

    available_source_count: int

    included_source_count: int

    truncated_source_count: int

    skipped_source_count: int

    used_chars: int

    warnings: tuple[
        str,
        ...,
    ] = ()

    # ======================================================
    # Helpers
    # ======================================================

    @property
    def has_context(
        self,
    ) -> bool:
        """
        Whether at least one source entered the context.
        """

        return bool(
            self.text.strip()
        )

    @property
    def remaining_chars(
        self,
    ) -> int:
        """
        Unused global context character budget.
        """

        return max(
            0,
            (
                self.max_context_chars
                -
                self.used_chars
            ),
        )

    @property
    def included_sources(
        self,
    ) -> tuple[
        InvestigationRAGContextSource,
        ...,
    ]:
        """
        Sources actually present in context text.
        """

        return tuple(
            source
            for source in self.sources
            if source.included
        )

    @property
    def skipped_sources(
        self,
    ) -> tuple[
        InvestigationRAGContextSource,
        ...,
    ]:
        """
        Sources omitted from context.
        """

        return tuple(
            source
            for source in self.sources
            if source.skipped
        )


# ==========================================================
# Builder
# ==========================================================


class InvestigationRAGContextBuilder:
    """
    Deterministic bounded RAG context builder.

    Source ordering is never changed.

    The input ordering is assumed to already be the final
    ordering produced by UnifiedSearchService and preserved
    by InvestigationRAGRetrievalService.
    """

    # ======================================================
    # Public API
    # ======================================================

    def build(
        self,
        retrieval: InvestigationRAGRetrievalResult,
        *,
        max_context_chars: int = (
            DEFAULT_MAX_CONTEXT_CHARS
        ),
        max_source_chars: int = (
            DEFAULT_MAX_SOURCE_CHARS
        ),
    ) -> InvestigationRAGContext:
        """
        Build bounded structured context from RAG retrieval.

        Character budgets are deliberately enforced here
        instead of inside retrieval so retrieval remains
        independent from LLM context-window concerns.
        """

        if not isinstance(
            retrieval,
            InvestigationRAGRetrievalResult,
        ):

            raise TypeError(
                "retrieval must be "
                "InvestigationRAGRetrievalResult."
            )

        self._validate_budget(
            max_context_chars,
            field_name=(
                "max_context_chars"
            ),
        )

        self._validate_budget(
            max_source_chars,
            field_name=(
                "max_source_chars"
            ),
        )

        context_blocks: list[
            str
        ] = []

        context_sources: list[
            InvestigationRAGContextSource
        ] = []

        warnings: list[
            str
        ] = []

        used_chars = 0

        # --------------------------------------------------
        # Preserve input order exactly.
        # --------------------------------------------------

        for source in retrieval.sources:

            (
                context_source,
                block,
            ) = self._prepare_source(
                source=source,
                current_used_chars=(
                    used_chars
                ),
                has_previous_blocks=(
                    bool(
                        context_blocks
                    )
                ),
                max_context_chars=(
                    max_context_chars
                ),
                max_source_chars=(
                    max_source_chars
                ),
            )

            context_sources.append(
                context_source
            )

            if block is None:

                if (
                    context_source.status
                    ==
                    "skipped_budget"
                ):

                    warnings.append(
                        "Context budget excluded "
                        f"{source.reference_id}."
                    )

                elif (
                    context_source.status
                    ==
                    "skipped_empty"
                ):

                    warnings.append(
                        "No usable text was available for "
                        f"{source.reference_id}."
                    )

                continue

            separator = (
                "\n\n"
                if context_blocks
                else ""
            )

            context_blocks.append(
                block
            )

            used_chars += (
                len(
                    separator
                )
                +
                len(
                    block
                )
            )

        text = "\n\n".join(
            context_blocks
        )

        # Defensive invariant.
        if len(
            text
        ) > max_context_chars:

            raise RuntimeError(
                "Context builder exceeded "
                "max_context_chars."
            )

        if len(
            text
        ) != used_chars:

            used_chars = len(
                text
            )

        included_count = sum(
            1
            for source in context_sources
            if source.included
        )

        truncated_count = sum(
            1
            for source in context_sources
            if source.truncated
        )

        skipped_count = sum(
            1
            for source in context_sources
            if source.skipped
        )

        return InvestigationRAGContext(
            question=(
                retrieval.question
            ),

            case_id=(
                retrieval.case_id
            ),

            text=text,

            sources=tuple(
                context_sources
            ),

            max_context_chars=(
                max_context_chars
            ),

            max_source_chars=(
                max_source_chars
            ),

            available_source_count=len(
                retrieval.sources
            ),

            included_source_count=(
                included_count
            ),

            truncated_source_count=(
                truncated_count
            ),

            skipped_source_count=(
                skipped_count
            ),

            used_chars=(
                used_chars
            ),

            warnings=tuple(
                warnings
            ),
        )

    # ======================================================
    # Source preparation
    # ======================================================

    def _prepare_source(
        self,
        *,
        source: InvestigationRAGSource,
        current_used_chars: int,
        has_previous_blocks: bool,
        max_context_chars: int,
        max_source_chars: int,
    ) -> tuple[
        InvestigationRAGContextSource,
        str | None,
    ]:
        """
        Prepare one source without changing source order.
        """

        if not isinstance(
            source,
            InvestigationRAGSource,
        ):

            raise TypeError(
                "Context source must be "
                "InvestigationRAGSource."
            )

        raw_text = (
            self._extract_source_text(
                source
            )
        )

        original_length = len(
            raw_text
        )

        if not raw_text:

            return (
                self._build_context_source(
                    source=source,
                    status="skipped_empty",
                    included=False,
                    text="",
                    original_length=0,
                    included_length=0,
                ),
                None,
            )

        # --------------------------------------------------
        # Per-source budget
        # --------------------------------------------------

        source_text = raw_text[
            :max_source_chars
        ]

        per_source_truncated = (
            len(
                source_text
            )
            <
            original_length
        )

        header = (
            self._build_source_header(
                source
            )
        )

        separator_length = (
            2
            if has_previous_blocks
            else 0
        )

        remaining = (
            max_context_chars
            -
            current_used_chars
            -
            separator_length
        )

        # Require at least the header plus one character
        # of source content.
        if remaining <= len(
            header
        ):

            return (
                self._build_context_source(
                    source=source,
                    status="skipped_budget",
                    included=False,
                    text="",
                    original_length=(
                        original_length
                    ),
                    included_length=0,
                ),
                None,
            )

        body_budget = (
            remaining
            -
            len(
                header
            )
        )

        included_text = source_text[
            :body_budget
        ]

        global_truncated = (
            len(
                included_text
            )
            <
            len(
                source_text
            )
        )

        if not included_text:

            return (
                self._build_context_source(
                    source=source,
                    status="skipped_budget",
                    included=False,
                    text="",
                    original_length=(
                        original_length
                    ),
                    included_length=0,
                ),
                None,
            )

        truncated = (
            per_source_truncated
            or global_truncated
        )

        status = (
            "truncated"
            if truncated
            else "full"
        )

        block = (
            header
            +
            included_text
        )

        return (
            self._build_context_source(
                source=source,
                status=status,
                included=True,
                text=included_text,
                original_length=(
                    original_length
                ),
                included_length=len(
                    included_text
                ),
            ),
            block,
        )

    # ======================================================
    # Context source contract
    # ======================================================

    @staticmethod
    def _build_context_source(
        *,
        source: InvestigationRAGSource,
        status: str,
        included: bool,
        text: str,
        original_length: int,
        included_length: int,
    ) -> InvestigationRAGContextSource:
        """
        Build immutable source-state representation.
        """

        return InvestigationRAGContextSource(
            reference_id=(
                source.reference_id
            ),

            object_id=(
                source.object_id
            ),

            object_type=(
                source.object_type
            ),

            case_id=(
                source.case_id
            ),

            title=(
                source.title
            ),

            status=status,

            included=included,

            text=text,

            original_length=(
                original_length
            ),

            included_length=(
                included_length
            ),

            final_score=(
                source.final_score
            ),

            matched_methods=(
                source.matched_methods
            ),

            metadata=dict(
                source.metadata
            ),
        )

    # ======================================================
    # Text extraction
    # ======================================================

    def _extract_source_text(
        self,
        source: InvestigationRAGSource,
    ) -> str:
        """
        Extract text without blindly serializing arbitrary
        domain / ORM objects.

        Extraction order:

        1. direct string source
        2. bytes source
        3. known textual Mapping fields
        4. known textual values already loaded in __dict__
        5. search snippet
        6. title

        Using __dict__ rather than arbitrary getattr calls
        avoids intentionally triggering lazy ORM loading.
        """

        raw_source = (
            source.source
        )

        # --------------------------------------------------
        # String
        # --------------------------------------------------

        if isinstance(
            raw_source,
            str,
        ):

            normalized = (
                self._normalize_text(
                    raw_source
                )
            )

            if normalized:

                return normalized

        # --------------------------------------------------
        # Bytes
        # --------------------------------------------------

        if isinstance(
            raw_source,
            (
                bytes,
                bytearray,
            ),
        ):

            try:

                decoded = bytes(
                    raw_source
                ).decode(
                    "utf-8",
                    errors="replace",
                )

            except Exception:

                decoded = ""

            normalized = (
                self._normalize_text(
                    decoded
                )
            )

            if normalized:

                return normalized

        # --------------------------------------------------
        # Mapping
        # --------------------------------------------------

        if isinstance(
            raw_source,
            Mapping,
        ):

            mapping_text = (
                self._extract_mapping_text(
                    raw_source
                )
            )

            if mapping_text:

                return mapping_text

        # --------------------------------------------------
        # Already-loaded object dictionary only.
        # --------------------------------------------------

        if raw_source is not None:

            object_dict = getattr(
                raw_source,
                "__dict__",
                None,
            )

            if isinstance(
                object_dict,
                dict,
            ):

                object_text = (
                    self._extract_mapping_text(
                        object_dict
                    )
                )

                if object_text:

                    return object_text

        # --------------------------------------------------
        # Stable retrieval fallback
        # --------------------------------------------------

        snippet = (
            self._normalize_text(
                source.snippet
            )
        )

        if snippet:

            return snippet

        return self._normalize_text(
            source.title
        )

    def _extract_mapping_text(
        self,
        mapping: Mapping,
    ) -> str:
        """
        Extract only known textual fields from a mapping.

        This intentionally avoids dumping arbitrary metadata
        into the LLM context.
        """

        preferred_fields = (
            "content",
            "text",
            "body",
            "message",
            "description",
            "summary",
            "caption",
            "value",
            "transcript",
            "transcript_text",
        )

        values: list[
            str
        ] = []

        seen: set[
            str
        ] = set()

        for field_name in preferred_fields:

            try:

                value = mapping.get(
                    field_name
                )

            except Exception:

                continue

            if not isinstance(
                value,
                str,
            ):

                continue

            normalized = (
                self._normalize_text(
                    value
                )
            )

            if (
                not normalized
                or normalized in seen
            ):

                continue

            seen.add(
                normalized
            )

            values.append(
                normalized
            )

        return "\n\n".join(
            values
        )

    # ======================================================
    # Source block formatting
    # ======================================================

    @staticmethod
    def _format_optional_score(
        value: Any,
    ) -> str | None:
        if value is None or isinstance(
            value,
            bool,
        ):
            return None

        try:
            numeric = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        if not (
            0.0
            <= numeric
            <= 1.0
        ):
            return None

        return f"{numeric:.6f}"

    def _build_source_header(
        self,
        source: InvestigationRAGSource,
    ) -> str:
        """
        Build deterministic provenance header.

        `retrieval_score` is explicitly named to prevent
        accidental interpretation as evidence confidence.
        """

        title = (
            self._normalize_text(
                source.title
            )
        )

        if len(
            title
        ) > DEFAULT_MAX_TITLE_CHARS:

            title = (
                title[
                    :DEFAULT_MAX_TITLE_CHARS
                ]
                .rstrip()
                +
                "..."
            )

        methods = ", ".join(
            source.matched_methods
        )

        lines = [
            (
                "[SOURCE "
                f"{source.reference_id}]"
            ),
            (
                "object_type: "
                f"{source.object_type}"
            ),
            (
                "object_id: "
                f"{source.object_id}"
            ),
        ]

        if title:

            lines.append(
                "title: "
                f"{title}"
            )

        lines.append(
            "retrieval_score: "
            f"{source.final_score:.6f}"
        )

        confidence_metadata = (
            source.metadata.get(
                "canonical_evidence_confidence"
            )
            if isinstance(
                source.metadata,
                dict,
            )
            else None
        )

        if isinstance(
            confidence_metadata,
            dict,
        ):

            strongest_confidence = (
                self._format_optional_score(
                    confidence_metadata.get(
                        "strongest_confidence"
                    )
                )
            )
            strongest_coverage = (
                self._format_optional_score(
                    confidence_metadata.get(
                        "strongest_assessment_coverage"
                    )
                )
            )

            lines.append(
                "evidence_confidence_scope: "
                "proposition_support"
            )

            if strongest_confidence is not None:
                lines.append(
                    "evidence_confidence: "
                    f"{strongest_confidence}"
                )

            if strongest_coverage is not None:
                lines.append(
                    "evidence_confidence_coverage: "
                    f"{strongest_coverage}"
                )

            propositions = (
                confidence_metadata.get(
                    "propositions"
                )
                or ()
            )

            if isinstance(
                propositions,
                list,
            ):

                for proposition in propositions[:3]:

                    if not isinstance(
                        proposition,
                        dict,
                    ):
                        continue

                    proposition_key = (
                        self._normalize_text(
                            proposition.get(
                                "proposition_key"
                            )
                        )
                    )

                    confidence_score = (
                        self._format_optional_score(
                            proposition.get(
                                "confidence_score"
                            )
                        )
                    )
                    assessment_coverage = (
                        self._format_optional_score(
                            proposition.get(
                                "assessment_coverage"
                            )
                        )
                    )
                    intrinsic_strength = (
                        self._format_optional_score(
                            proposition.get(
                                "intrinsic_strength"
                            )
                        )
                    )
                    source_reliability = (
                        self._format_optional_score(
                            proposition.get(
                                "source_reliability_score"
                            )
                        )
                    )
                    source_reliability_coverage = (
                        self._format_optional_score(
                            proposition.get(
                                "source_reliability_coverage"
                            )
                        )
                    )
                    effective_corroboration = (
                        self._format_optional_score(
                            proposition.get(
                                "effective_corroboration_score"
                            )
                        )
                    )
                    independence_score = (
                        self._format_optional_score(
                            proposition.get(
                                "independence_score"
                            )
                        )
                    )
                    independence_coverage = (
                        self._format_optional_score(
                            proposition.get(
                                "independence_coverage"
                            )
                        )
                    )
                    contradiction_strength = (
                        self._format_optional_score(
                            proposition.get(
                                "contradiction_strength"
                            )
                        )
                    )

                    if not proposition_key:
                        continue

                    summary_parts = [
                        proposition_key,
                    ]

                    if confidence_score is not None:
                        summary_parts.append(
                            "confidence="
                            f"{confidence_score}"
                        )

                    if assessment_coverage is not None:
                        summary_parts.append(
                            "coverage="
                            f"{assessment_coverage}"
                        )

                    if intrinsic_strength is not None:
                        summary_parts.append(
                            "intrinsic="
                            f"{intrinsic_strength}"
                        )

                    if source_reliability is not None:
                        summary_parts.append(
                            "source_reliability="
                            f"{source_reliability}"
                        )

                    if source_reliability_coverage is not None:
                        summary_parts.append(
                            "source_reliability_coverage="
                            f"{source_reliability_coverage}"
                        )

                    if effective_corroboration is not None:
                        summary_parts.append(
                            "corroboration="
                            f"{effective_corroboration}"
                        )

                    if independence_score is not None:
                        summary_parts.append(
                            "independence="
                            f"{independence_score}"
                        )

                    if independence_coverage is not None:
                        summary_parts.append(
                            "independence_coverage="
                            f"{independence_coverage}"
                        )

                    if contradiction_strength is not None:
                        summary_parts.append(
                            "contradiction="
                            f"{contradiction_strength}"
                        )

                    if proposition.get(
                        "hard_conflict"
                    ):
                        summary_parts.append(
                            "hard_conflict=true"
                        )

                    lines.append(
                        "evidence_proposition: "
                        + "; ".join(
                            summary_parts
                        )
                    )

        if methods:

            lines.append(
                "matched_methods: "
                f"{methods}"
            )

        lines.append(
            "content:"
        )

        return (
            "\n".join(
                lines
            )
            +
            "\n"
        )

    # ======================================================
    # Normalization
    # ======================================================

    @staticmethod
    def _normalize_text(
        value: Any,
    ) -> str:
        """
        Normalize text while preserving useful paragraphs.
        """

        if value is None:

            return ""

        if not isinstance(
            value,
            str,
        ):

            return ""

        value = (
            value
            .replace(
                "\r\n",
                "\n",
            )
            .replace(
                "\r",
                "\n",
            )
        )

        lines = [
            line.strip()
            for line in value.split(
                "\n"
            )
        ]

        normalized_lines: list[
            str
        ] = []

        previous_blank = False

        for line in lines:

            if not line:

                if (
                    normalized_lines
                    and not previous_blank
                ):

                    normalized_lines.append(
                        ""
                    )

                previous_blank = True

                continue

            normalized_lines.append(
                line
            )

            previous_blank = False

        return "\n".join(
            normalized_lines
        ).strip()

    @staticmethod
    def _validate_budget(
        value: int,
        *,
        field_name: str,
    ) -> None:
        """
        Validate context character budgets.
        """

        if not isinstance(
            value,
            int,
        ):

            raise TypeError(
                f"{field_name} must be an integer."
            )

        if value < 1:

            raise ValueError(
                f"{field_name} must be at least 1."
            )

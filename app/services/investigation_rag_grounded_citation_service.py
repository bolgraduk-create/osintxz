"""
Grounded citation validation for investigation RAG outputs.

Architecture:

AI-generated text
        ↓
citation extraction
        ↓
[R1] / [R2] / ...
        ↓
InvestigationRAGGroundedCitationService
        ↓
bounded InvestigationRAGContext
        +
InvestigationRAGRetrievalResult
        ↓
exact RAG object provenance
        ↓
Evidence / Source provenance when already available

Responsibilities:

- extract R-style source references from AI output
- validate references against sources actually included
  in the bounded RAG context
- resolve every valid reference to the exact RAG object
- preserve object_id / object_type / case_id
- recover evidence_id when available
- recover source_id when available
- report invalid references
- report incomplete Evidence/Source provenance
- validate RAG summary output
- validate RAG conclusions output

Does NOT:

- decide whether a factual statement is true
- decide whether evidence proves a claim
- calculate evidence confidence
- calculate identity confidence
- create Evidence
- create Source objects
- create EvidenceEntity links
- modify the database
- run another search
- call AI
- infer missing provenance through guesses
- perform claim-level citation coverage analysis

Important boundaries:

citation valid != statement true
citation valid != evidence proves claim
citation valid != evidence confidence
citation valid != identity confidence

A valid citation only establishes that the model referenced
material that was actually available in its bounded RAG
context.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
import re
from typing import Any
from uuid import UUID

from app.services.investigation_rag_context_builder import (
    InvestigationRAGContext,
    InvestigationRAGContextSource,
)

from app.services.investigation_rag_retrieval_service import (
    InvestigationRAGRetrievalResult,
    InvestigationRAGSource,
)

from app.services.investigation_rag_summary_service import (
    InvestigationRAGSummaryResult,
)

from app.services.investigation_rag_conclusions_service import (
    InvestigationRAGConclusionKind,
    InvestigationRAGConclusionsResult,
)


# ==========================================================
# Citation syntax
# ==========================================================

_CITATION_GROUP_PATTERN = re.compile(
    r"\["
    r"(?P<body>"
    r"[Rr]\d+"
    r"(?:\s*[,;/]\s*[Rr]\d+)*"
    r")"
    r"\]"
)

_CITATION_TOKEN_PATTERN = re.compile(
    r"[Rr]\d+"
)


# ==========================================================
# Status
# ==========================================================


class InvestigationRAGCitationStatus(
    str,
    Enum,
):
    """
    Grounded citation validation status.
    """

    VALID = (
        "valid"
    )

    INVALID_REFERENCE = (
        "invalid_reference"
    )

    UNRESOLVED_PROVENANCE = (
        "unresolved_provenance"
    )


class InvestigationRAGProvenanceLevel(
    str,
    Enum,
):
    """
    Deepest provenance level recovered without performing
    any additional database lookup.
    """

    RAG_OBJECT = (
        "rag_object"
    )

    EVIDENCE = (
        "evidence"
    )

    SOURCE = (
        "source"
    )

    EVIDENCE_SOURCE = (
        "evidence_source"
    )


# ==========================================================
# Citation occurrence
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGCitationOccurrence:
    """
    One textual citation occurrence.
    """

    reference_id: str

    raw_group: str

    start: int

    end: int


# ==========================================================
# Validated citation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGGroundedCitation:
    """
    One unique R-style reference after validation.
    """

    reference_id: str

    status: InvestigationRAGCitationStatus

    reference_valid: bool

    occurrences: tuple[
        InvestigationRAGCitationOccurrence,
        ...,
    ]

    object_id: UUID | None

    object_type: str | None

    case_id: UUID | None

    title: str

    retrieval_score: float | None

    matched_methods: tuple[
        str,
        ...,
    ]

    evidence_id: UUID | None

    source_id: UUID | None

    provenance_level: (
        InvestigationRAGProvenanceLevel
    )

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
    def occurrence_count(
        self,
    ) -> int:
        """
        Number of times this reference appears in the text.
        """

        return len(
            self.occurrences
        )

    @property
    def provenance_resolved(
        self,
    ) -> bool:
        """
        Whether the citation can be traced to a Source.

        Source is the terminal provenance object for the
        existing Evidence Layer.
        """

        return (
            self.source_id
            is not None
        )

    @property
    def has_evidence(
        self,
    ) -> bool:
        """
        Whether explicit Evidence identity is available.
        """

        return (
            self.evidence_id
            is not None
        )


# ==========================================================
# Validation report
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGCitationValidation:
    """
    Citation validation report for one generated text.

    `unused_context_reference_ids` does NOT mean those sources
    should have been cited.

    It only reports that they were available in the bounded
    context but were not referenced by this model response.
    """

    case_id: UUID

    text: str

    citations: tuple[
        InvestigationRAGGroundedCitation,
        ...,
    ]

    available_reference_ids: tuple[
        str,
        ...,
    ]

    cited_reference_ids: tuple[
        str,
        ...,
    ]

    unused_context_reference_ids: tuple[
        str,
        ...,
    ]

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
    def has_citations(
        self,
    ) -> bool:
        """
        Whether the generated text contains R-style citations.
        """

        return bool(
            self.citations
        )

    @property
    def valid_citations(
        self,
    ) -> tuple[
        InvestigationRAGGroundedCitation,
        ...,
    ]:
        """
        References that really existed in model context.

        Includes UNRESOLVED_PROVENANCE because the reference
        itself is valid even when deeper Source provenance
        could not be reconstructed.
        """

        return tuple(
            citation
            for citation in self.citations
            if citation.reference_valid
        )

    @property
    def invalid_citations(
        self,
    ) -> tuple[
        InvestigationRAGGroundedCitation,
        ...,
    ]:
        """
        References that were not supplied to the model.
        """

        return tuple(
            citation
            for citation in self.citations
            if not citation.reference_valid
        )

    @property
    def unresolved_citations(
        self,
    ) -> tuple[
        InvestigationRAGGroundedCitation,
        ...,
    ]:
        """
        Valid RAG references whose deeper provenance could not
        be resolved to Source.
        """

        return tuple(
            citation
            for citation in self.citations
            if (
                citation.status
                ==
                InvestigationRAGCitationStatus
                .UNRESOLVED_PROVENANCE
            )
        )

    @property
    def valid_count(
        self,
    ) -> int:
        return len(
            self.valid_citations
        )

    @property
    def invalid_count(
        self,
    ) -> int:
        return len(
            self.invalid_citations
        )

    @property
    def unresolved_count(
        self,
    ) -> int:
        return len(
            self.unresolved_citations
        )

    @property
    def all_references_valid(
        self,
    ) -> bool:
        """
        True only when at least one citation exists and every
        cited reference actually appeared in bounded context.
        """

        return (
            bool(
                self.citations
            )
            and all(
                citation.reference_valid
                for citation in self.citations
            )
        )

    @property
    def all_provenance_resolved(
        self,
    ) -> bool:
        """
        True only when every cited reference can also be traced
        to a Source.
        """

        return (
            bool(
                self.citations
            )
            and all(
                citation.provenance_resolved
                for citation in self.citations
                if citation.reference_valid
            )
            and not self.invalid_citations
        )


# ==========================================================
# Conclusions validation contracts
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGConclusionCitationValidation:
    """
    Citation validation for one AI conclusion workflow.
    """

    kind: InvestigationRAGConclusionKind

    workflow_name: str

    validation: InvestigationRAGCitationValidation


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationRAGConclusionsCitationValidation:
    """
    Citation validation for all generated conclusion workflows.
    """

    case_id: UUID

    items: tuple[
        InvestigationRAGConclusionCitationValidation,
        ...,
    ]

    @property
    def all_references_valid(
        self,
    ) -> bool:
        """
        Whether every conclusion that contains references uses
        only valid references.

        Conclusion responses without citations remain visible
        as separate reports and are not silently interpreted
        as validated.
        """

        return (
            bool(
                self.items
            )
            and all(
                (
                    item.validation
                    .all_references_valid
                )
                for item in self.items
            )
        )

    @property
    def has_invalid_references(
        self,
    ) -> bool:
        """
        Whether at least one workflow contains an invalid R ref.
        """

        return any(
            bool(
                item.validation
                .invalid_citations
            )
            for item in self.items
        )


# ==========================================================
# Service
# ==========================================================


class InvestigationRAGGroundedCitationService:
    """
    Read-only deterministic RAG citation validator.
    """

    # ======================================================
    # Public API
    # ======================================================

    def validate_text(
        self,
        *,
        text: str,
        retrieval: InvestigationRAGRetrievalResult,
        context: InvestigationRAGContext,
    ) -> InvestigationRAGCitationValidation:
        """
        Validate citations in arbitrary AI-generated text.

        Only references included in `context.included_sources`
        are considered available to the model.
        """

        if not isinstance(
            text,
            str,
        ):

            raise TypeError(
                "text must be a string."
            )

        if not isinstance(
            retrieval,
            InvestigationRAGRetrievalResult,
        ):

            raise TypeError(
                "retrieval must be "
                "InvestigationRAGRetrievalResult."
            )

        if not isinstance(
            context,
            InvestigationRAGContext,
        ):

            raise TypeError(
                "context must be InvestigationRAGContext."
            )

        self._validate_case_contract(
            retrieval=retrieval,
            context=context,
        )

        included_sources = tuple(
            context.included_sources
        )

        context_by_reference = (
            self._context_reference_map(
                included_sources
            )
        )

        retrieval_by_reference = (
            self._retrieval_reference_map(
                retrieval.sources
            )
        )

        occurrences = (
            self._extract_occurrences(
                text
            )
        )

        grouped = (
            self._group_occurrences(
                occurrences
            )
        )

        citations: list[
            InvestigationRAGGroundedCitation
        ] = []

        for (
            reference_id,
            reference_occurrences,
        ) in grouped:

            context_source = (
                context_by_reference.get(
                    reference_id
                )
            )

            # ----------------------------------------------
            # Model referenced something it never received.
            # ----------------------------------------------

            if context_source is None:

                citations.append(
                    self._invalid_citation(
                        reference_id=reference_id,
                        occurrences=(
                            reference_occurrences
                        ),
                    )
                )

                continue

            retrieval_source = (
                retrieval_by_reference.get(
                    reference_id
                )
            )

            if retrieval_source is not None:

                self._validate_source_contract(
                    context_source=(
                        context_source
                    ),
                    retrieval_source=(
                        retrieval_source
                    ),
                )

            citations.append(
                self._valid_or_unresolved_citation(
                    reference_id=reference_id,
                    occurrences=(
                        reference_occurrences
                    ),
                    context_source=(
                        context_source
                    ),
                    retrieval_source=(
                        retrieval_source
                    ),
                )
            )

        available_reference_ids = tuple(
            source.reference_id
            for source in included_sources
        )

        cited_reference_ids = tuple(
            reference_id
            for (
                reference_id,
                _,
            ) in grouped
        )

        cited_set = set(
            cited_reference_ids
        )

        unused_context_reference_ids = tuple(
            reference_id
            for reference_id
            in available_reference_ids
            if reference_id
            not in cited_set
        )

        return InvestigationRAGCitationValidation(
            case_id=(
                context.case_id
            ),

            text=text,

            citations=tuple(
                citations
            ),

            available_reference_ids=(
                available_reference_ids
            ),

            cited_reference_ids=(
                cited_reference_ids
            ),

            unused_context_reference_ids=(
                unused_context_reference_ids
            ),

            metadata={
                "validator": (
                    self.__class__.__name__
                ),

                "available_reference_count": len(
                    available_reference_ids
                ),

                "cited_reference_count": len(
                    cited_reference_ids
                ),

                "claim_level_coverage_evaluated": False,

                "database_lookup_performed": False,

                "database_write_performed": False,
            },
        )

    def validate_summary(
        self,
        summary: InvestigationRAGSummaryResult,
    ) -> InvestigationRAGCitationValidation:
        """
        Validate citations in one RAG investigation summary.
        """

        if not isinstance(
            summary,
            InvestigationRAGSummaryResult,
        ):

            raise TypeError(
                "summary must be "
                "InvestigationRAGSummaryResult."
            )

        return self.validate_text(
            text=(
                summary.summary
            ),
            retrieval=(
                summary.retrieval
            ),
            context=(
                summary.context
            ),
        )

    def validate_conclusions(
        self,
        conclusions: InvestigationRAGConclusionsResult,
    ) -> InvestigationRAGConclusionsCitationValidation:
        """
        Validate every AI conclusion workflow independently.
        """

        if not isinstance(
            conclusions,
            InvestigationRAGConclusionsResult,
        ):

            raise TypeError(
                "conclusions must be "
                "InvestigationRAGConclusionsResult."
            )

        items: list[
            InvestigationRAGConclusionCitationValidation
        ] = []

        for conclusion in (
            conclusions.conclusions
        ):

            validation = self.validate_text(
                text=(
                    conclusion.text
                ),
                retrieval=(
                    conclusions.retrieval
                ),
                context=(
                    conclusions.context
                ),
            )

            items.append(
                InvestigationRAGConclusionCitationValidation(
                    kind=(
                        conclusion.kind
                    ),

                    workflow_name=(
                        conclusion.workflow_name
                    ),

                    validation=(
                        validation
                    ),
                )
            )

        return (
            InvestigationRAGConclusionsCitationValidation(
                case_id=(
                    conclusions.case_id
                ),

                items=tuple(
                    items
                ),
            )
        )

    # ======================================================
    # Citation extraction
    # ======================================================

    @staticmethod
    def _extract_occurrences(
        text: str,
    ) -> tuple[
        InvestigationRAGCitationOccurrence,
        ...,
    ]:
        """
        Extract references such as:

            [R1]
            [r2]
            [R1, R2]
            [R1; R3]
            [R1/R4]

        References are normalized only by case.
        R01 remains R01 and therefore does not silently become R1.
        """

        occurrences: list[
            InvestigationRAGCitationOccurrence
        ] = []

        for group_match in (
            _CITATION_GROUP_PATTERN
            .finditer(
                text
            )
        ):

            body = (
                group_match.group(
                    "body"
                )
            )

            raw_group = (
                group_match.group(
                    0
                )
            )

            for token_match in (
                _CITATION_TOKEN_PATTERN
                .finditer(
                    body
                )
            ):

                reference_id = (
                    token_match.group(
                        0
                    ).upper()
                )

                occurrences.append(
                    InvestigationRAGCitationOccurrence(
                        reference_id=(
                            reference_id
                        ),

                        raw_group=(
                            raw_group
                        ),

                        start=(
                            group_match.start()
                        ),

                        end=(
                            group_match.end()
                        ),
                    )
                )

        return tuple(
            occurrences
        )

    @staticmethod
    def _group_occurrences(
        occurrences: tuple[
            InvestigationRAGCitationOccurrence,
            ...,
        ],
    ) -> tuple[
        tuple[
            str,
            tuple[
                InvestigationRAGCitationOccurrence,
                ...,
            ],
        ],
        ...,
    ]:
        """
        Group duplicate references while preserving order of
        first appearance.
        """

        order: list[
            str
        ] = []

        grouped: dict[
            str,
            list[
                InvestigationRAGCitationOccurrence
            ],
        ] = {}

        for occurrence in occurrences:

            reference_id = (
                occurrence.reference_id
            )

            if reference_id not in grouped:

                grouped[
                    reference_id
                ] = []

                order.append(
                    reference_id
                )

            grouped[
                reference_id
            ].append(
                occurrence
            )

        return tuple(
            (
                reference_id,
                tuple(
                    grouped[
                        reference_id
                    ]
                ),
            )
            for reference_id in order
        )

    # ======================================================
    # Reference maps
    # ======================================================

    @staticmethod
    def _context_reference_map(
        sources: tuple[
            InvestigationRAGContextSource,
            ...,
        ],
    ) -> dict[
        str,
        InvestigationRAGContextSource,
    ]:
        """
        Build unique reference map for sources actually included
        in model context.
        """

        result: dict[
            str,
            InvestigationRAGContextSource,
        ] = {}

        for source in sources:

            reference_id = (
                source.reference_id
            )

            if reference_id in result:

                raise RuntimeError(
                    "Duplicate RAG context reference: "
                    f"{reference_id}"
                )

            result[
                reference_id
            ] = source

        return result

    @staticmethod
    def _retrieval_reference_map(
        sources: tuple[
            InvestigationRAGSource,
            ...,
        ],
    ) -> dict[
        str,
        InvestigationRAGSource,
    ]:
        """
        Build exact retrieval provenance map.
        """

        result: dict[
            str,
            InvestigationRAGSource,
        ] = {}

        for source in sources:

            reference_id = (
                source.reference_id
            )

            if reference_id in result:

                raise RuntimeError(
                    "Duplicate RAG retrieval reference: "
                    f"{reference_id}"
                )

            result[
                reference_id
            ] = source

        return result

    # ======================================================
    # Citation construction
    # ======================================================

    @staticmethod
    def _invalid_citation(
        *,
        reference_id: str,
        occurrences: tuple[
            InvestigationRAGCitationOccurrence,
            ...,
        ],
    ) -> InvestigationRAGGroundedCitation:
        """
        Build citation for an R ref that never existed in the
        bounded context supplied to the model.
        """

        return InvestigationRAGGroundedCitation(
            reference_id=reference_id,

            status=(
                InvestigationRAGCitationStatus
                .INVALID_REFERENCE
            ),

            reference_valid=False,

            occurrences=occurrences,

            object_id=None,

            object_type=None,

            case_id=None,

            title="",

            retrieval_score=None,

            matched_methods=(),

            evidence_id=None,

            source_id=None,

            provenance_level=(
                InvestigationRAGProvenanceLevel
                .RAG_OBJECT
            ),

            metadata={
                "reason": (
                    "Reference was not present in "
                    "bounded RAG context."
                ),
            },
        )

    def _valid_or_unresolved_citation(
        self,
        *,
        reference_id: str,
        occurrences: tuple[
            InvestigationRAGCitationOccurrence,
            ...,
        ],
        context_source: InvestigationRAGContextSource,
        retrieval_source: InvestigationRAGSource | None,
    ) -> InvestigationRAGGroundedCitation:
        """
        Build a grounded citation and recover deeper provenance
        when the retrieval object still exposes it.
        """

        evidence_id: UUID | None = None
        source_id: UUID | None = None

        matched_methods = tuple(
            context_source.matched_methods
        )

        retrieval_score = (
            float(
                context_source.final_score
            )
        )

        metadata = dict(
            context_source.metadata
        )

        if retrieval_source is not None:

            (
                evidence_id,
                source_id,
            ) = (
                self._resolve_provenance(
                    retrieval_source
                )
            )

            matched_methods = tuple(
                retrieval_source
                .matched_methods
            )

            retrieval_score = float(
                retrieval_source
                .final_score
            )

            metadata.update(
                {
                    "retrieval_metadata": dict(
                        retrieval_source
                        .metadata
                    ),
                }
            )

        provenance_level = (
            self._provenance_level(
                evidence_id=(
                    evidence_id
                ),
                source_id=(
                    source_id
                ),
            )
        )

        # Exact RAG reference is valid because it existed in
        # the bounded context. Deeper Source provenance may
        # still be unavailable.
        if source_id is not None:

            status = (
                InvestigationRAGCitationStatus
                .VALID
            )

        else:

            status = (
                InvestigationRAGCitationStatus
                .UNRESOLVED_PROVENANCE
            )

        return InvestigationRAGGroundedCitation(
            reference_id=reference_id,

            status=status,

            reference_valid=True,

            occurrences=occurrences,

            object_id=(
                context_source.object_id
            ),

            object_type=(
                context_source.object_type
            ),

            case_id=(
                context_source.case_id
            ),

            title=(
                context_source.title
            ),

            retrieval_score=(
                retrieval_score
            ),

            matched_methods=(
                matched_methods
            ),

            evidence_id=(
                evidence_id
            ),

            source_id=(
                source_id
            ),

            provenance_level=(
                provenance_level
            ),

            metadata=metadata,
        )

    # ======================================================
    # Provenance resolution
    # ======================================================

    def _resolve_provenance(
        self,
        source: InvestigationRAGSource,
    ) -> tuple[
        UUID | None,
        UUID | None,
    ]:
        """
        Recover evidence_id and source_id only from information
        already preserved by the RAG retrieval layer.

        No database query is made.

        This deliberately avoids inventing provenance for entity,
        relationship or analytical objects whose original Source
        cannot be established from the retrieval contract itself.
        """

        object_type = str(
            source.object_type
            or ""
        ).strip().lower()

        metadata = (
            source.metadata
            if isinstance(
                source.metadata,
                Mapping,
            )
            else {}
        )

        raw_mapping = (
            self._safe_object_mapping(
                source.source
            )
        )

        evidence_candidates: list[
            Any
        ] = []

        source_candidates: list[
            Any
        ] = []

        # --------------------------------------------------
        # Exact object identity
        # --------------------------------------------------

        if object_type == "evidence":

            evidence_candidates.append(
                source.object_id
            )

        if object_type == "source":

            source_candidates.append(
                source.object_id
            )

        # --------------------------------------------------
        # Direct metadata
        # --------------------------------------------------

        evidence_candidates.extend(
            [
                metadata.get(
                    "evidence_id"
                ),
                raw_mapping.get(
                    "evidence_id"
                ),
            ]
        )

        source_candidates.extend(
            [
                metadata.get(
                    "source_id"
                ),
                raw_mapping.get(
                    "source_id"
                ),
            ]
        )

        # --------------------------------------------------
        # Nested metadata provenance
        # --------------------------------------------------

        metadata_evidence = (
            metadata.get(
                "evidence"
            )
        )

        if isinstance(
            metadata_evidence,
            Mapping,
        ):

            evidence_candidates.extend(
                [
                    metadata_evidence.get(
                        "id"
                    ),
                    metadata_evidence.get(
                        "evidence_id"
                    ),
                ]
            )

            source_candidates.append(
                metadata_evidence.get(
                    "source_id"
                )
            )

        metadata_source = (
            metadata.get(
                "source"
            )
        )

        if isinstance(
            metadata_source,
            Mapping,
        ):

            source_candidates.extend(
                [
                    metadata_source.get(
                        "id"
                    ),
                    metadata_source.get(
                        "source_id"
                    ),
                ]
            )

        raw_evidence = (
            raw_mapping.get(
                "evidence"
            )
        )

        if isinstance(
            raw_evidence,
            Mapping,
        ):

            evidence_candidates.extend(
                [
                    raw_evidence.get(
                        "id"
                    ),
                    raw_evidence.get(
                        "evidence_id"
                    ),
                ]
            )

            source_candidates.append(
                raw_evidence.get(
                    "source_id"
                )
            )

        raw_source = (
            raw_mapping.get(
                "source"
            )
        )

        if isinstance(
            raw_source,
            Mapping,
        ):

            source_candidates.extend(
                [
                    raw_source.get(
                        "id"
                    ),
                    raw_source.get(
                        "source_id"
                    ),
                ]
            )

        evidence_id = (
            self._first_uuid(
                evidence_candidates
            )
        )

        source_id = (
            self._first_uuid(
                source_candidates
            )
        )

        return (
            evidence_id,
            source_id,
        )

    @staticmethod
    def _safe_object_mapping(
        value: Any,
    ) -> Mapping[
        str,
        Any,
    ]:
        """
        Read already-loaded raw source fields without traversing
        SQLAlchemy relationships or triggering intentional lazy
        loads.
        """

        if isinstance(
            value,
            Mapping,
        ):

            return value

        object_dict = getattr(
            value,
            "__dict__",
            None,
        )

        if isinstance(
            object_dict,
            Mapping,
        ):

            return object_dict

        return {}

    @staticmethod
    def _first_uuid(
        candidates: list[
            Any
        ],
    ) -> UUID | None:
        """
        Return first safely parseable UUID.
        """

        for candidate in candidates:

            if candidate is None:

                continue

            if isinstance(
                candidate,
                UUID,
            ):

                return candidate

            try:

                return UUID(
                    str(
                        candidate
                    )
                )

            except (
                ValueError,
                TypeError,
                AttributeError,
            ):

                continue

        return None

    @staticmethod
    def _provenance_level(
        *,
        evidence_id: UUID | None,
        source_id: UUID | None,
    ) -> InvestigationRAGProvenanceLevel:
        """
        Classify recovered provenance depth.
        """

        if (
            evidence_id is not None
            and source_id is not None
        ):

            return (
                InvestigationRAGProvenanceLevel
                .EVIDENCE_SOURCE
            )

        if source_id is not None:

            return (
                InvestigationRAGProvenanceLevel
                .SOURCE
            )

        if evidence_id is not None:

            return (
                InvestigationRAGProvenanceLevel
                .EVIDENCE
            )

        return (
            InvestigationRAGProvenanceLevel
            .RAG_OBJECT
        )

    # ======================================================
    # Contract validation
    # ======================================================

    @staticmethod
    def _validate_case_contract(
        *,
        retrieval: InvestigationRAGRetrievalResult,
        context: InvestigationRAGContext,
    ) -> None:
        """
        Ensure validation cannot accidentally combine context
        and retrieval data from different cases.
        """

        if (
            retrieval.case_id
            !=
            context.case_id
        ):

            raise ValueError(
                "RAG retrieval and context belong "
                "to different cases."
            )

    @staticmethod
    def _validate_source_contract(
        *,
        context_source: InvestigationRAGContextSource,
        retrieval_source: InvestigationRAGSource,
    ) -> None:
        """
        Same R reference must identify the same investigation
        object across retrieval and bounded context layers.
        """

        if (
            context_source.reference_id
            !=
            retrieval_source.reference_id
        ):

            raise RuntimeError(
                "RAG reference identity mismatch."
            )

        if (
            context_source.object_id
            !=
            retrieval_source.object_id
        ):

            raise RuntimeError(
                "RAG citation object_id mismatch for "
                f"{context_source.reference_id}."
            )

        if (
            str(
                context_source.object_type
            ).strip().lower()
            !=
            str(
                retrieval_source.object_type
            ).strip().lower()
        ):

            raise RuntimeError(
                "RAG citation object_type mismatch for "
                f"{context_source.reference_id}."
            )

        if (
            context_source.case_id
            !=
            retrieval_source.case_id
        ):

            raise RuntimeError(
                "RAG citation case_id mismatch for "
                f"{context_source.reference_id}."
            )

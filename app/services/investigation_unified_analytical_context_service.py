"""
Unified analytical context for investigations.

This module is the final aggregation layer of Block 9.

It combines already-computed investigation analysis results
without re-running the underlying mathematical, search or AI
pipelines.

Architecture:

existing analytical results
        ↓
InvestigationUnifiedAnalyticalContextService
        ↓
InvestigationUnifiedAnalyticalContext
        ↓
AI / UI / reporting / future Pivot Engine

Responsibilities:

- preserve typed analytical result objects
- combine completed analytical layers
- preserve RAG retrieval/context/output/citation contracts
- validate case boundaries where case_id is available
- expose section availability
- expose one immutable investigation-level context

Does NOT:

- execute Unified Search
- execute RAG retrieval
- call AI
- calculate graph metrics
- calculate temporal metrics
- run anomaly detection
- run clustering
- perform Entity Resolution
- calculate Evidence confidence
- run multimodal analysis
- persist anything
- replace legacy AI workspace context

Important boundaries:

Unified Analytical Context != new analysis engine
Unified Analytical Context != Evidence
Unified Analytical Context != AI conclusion
Unified Analytical Context != verified fact

It is an aggregation contract over results produced elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from types import MappingProxyType
from typing import TYPE_CHECKING
from typing import Any
from typing import Mapping
from uuid import UUID


if TYPE_CHECKING:

    from app.application.investigation_graph_analysis_service import (
        InvestigationGraphAnalysisResult,
    )

    from app.application.investigation_temporal_analysis_service import (
        InvestigationTemporalAnalysisResult,
    )

    from app.application.investigation_anomaly_analysis_service import (
        InvestigationAnomalyAnalysisResult,
    )

    from app.application.investigation_entity_clustering_service import (
        InvestigationEntityClusteringResult,
    )

    from app.services.investigation_rag_retrieval_service import (
        InvestigationRAGRetrievalResult,
    )

    from app.services.investigation_rag_context_builder import (
        InvestigationRAGContext,
    )

    from app.services.investigation_rag_summary_service import (
        InvestigationRAGSummaryResult,
    )

    from app.services.investigation_rag_conclusions_service import (
        InvestigationRAGConclusionsResult,
    )

    from app.services.investigation_rag_grounded_citation_service import (
        InvestigationRAGCitationValidation,
        InvestigationRAGConclusionsCitationValidation,
    )


# ==========================================================
# Empty immutable metadata
# ==========================================================


def _empty_metadata(
) -> Mapping[
    str,
    Any,
]:

    return MappingProxyType(
        {}
    )


# ==========================================================
# RAG aggregate
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationUnifiedRAGContext:
    """
    Aggregated Block 9 RAG state.

    Every field contains an existing production result object.
    Nothing is recomputed here.
    """

    retrieval: (
        InvestigationRAGRetrievalResult
        | None
    ) = None

    context: (
        InvestigationRAGContext
        | None
    ) = None

    summary: (
        InvestigationRAGSummaryResult
        | None
    ) = None

    conclusions: (
        InvestigationRAGConclusionsResult
        | None
    ) = None

    summary_citations: (
        InvestigationRAGCitationValidation
        | None
    ) = None

    conclusions_citations: (
        InvestigationRAGConclusionsCitationValidation
        | None
    ) = None

    # ======================================================
    # Helpers
    # ======================================================

    @property
    def has_any(
        self,
    ) -> bool:
        """
        Whether at least one RAG component is present.
        """

        return any(
            value is not None
            for value in (
                self.retrieval,
                self.context,
                self.summary,
                self.conclusions,
                self.summary_citations,
                self.conclusions_citations,
            )
        )

    @property
    def available_components(
        self,
    ) -> tuple[
        str,
        ...,
    ]:
        """
        RAG components currently present.
        """

        components: list[
            str
        ] = []

        if self.retrieval is not None:

            components.append(
                "retrieval"
            )

        if self.context is not None:

            components.append(
                "context"
            )

        if self.summary is not None:

            components.append(
                "summary"
            )

        if self.conclusions is not None:

            components.append(
                "conclusions"
            )

        if self.summary_citations is not None:

            components.append(
                "summary_citations"
            )

        if (
            self.conclusions_citations
            is not None
        ):

            components.append(
                "conclusions_citations"
            )

        return tuple(
            components
        )

    @property
    def component_count(
        self,
    ) -> int:
        """
        Number of available RAG components.
        """

        return len(
            self.available_components
        )


# ==========================================================
# Unified investigation context
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationUnifiedAnalyticalContext:
    """
    Immutable investigation-level analytical context.

    Known case-level mathematical layers retain their existing
    typed result contracts.

    Entity Resolution, Evidence and Multimodal layers currently
    have no single case-level result contract, so already-created
    analytical results are preserved as opaque objects instead of
    being converted into a second artificial representation.
    """

    case_id: UUID

    generated_at: datetime

    # ------------------------------------------------------
    # Earlier mathematical layers without one canonical
    # case-level result contract.
    # ------------------------------------------------------

    entity_resolution_results: tuple[
        object,
        ...,
    ] = ()

    evidence_results: tuple[
        object,
        ...,
    ] = ()

    multimodal_results: tuple[
        object,
        ...,
    ] = ()

    # ------------------------------------------------------
    # Stable case-level typed mathematical results.
    # ------------------------------------------------------

    graph: (
        InvestigationGraphAnalysisResult
        | None
    ) = None

    temporal: (
        InvestigationTemporalAnalysisResult
        | None
    ) = None

    anomaly: (
        InvestigationAnomalyAnalysisResult
        | None
    ) = None

    clustering: (
        InvestigationEntityClusteringResult
        | None
    ) = None

    # ------------------------------------------------------
    # Block 9 RAG / AI layer.
    # ------------------------------------------------------

    rag: InvestigationUnifiedRAGContext = field(
        default_factory=(
            InvestigationUnifiedRAGContext
        )
    )

    warnings: tuple[
        str,
        ...,
    ] = ()

    metadata: Mapping[
        str,
        Any,
    ] = field(
        default_factory=(
            _empty_metadata
        )
    )

    # ======================================================
    # Availability
    # ======================================================

    @property
    def available_sections(
        self,
    ) -> tuple[
        str,
        ...,
    ]:
        """
        Top-level analytical sections currently present.
        """

        sections: list[
            str
        ] = []

        if self.entity_resolution_results:

            sections.append(
                "entity_resolution"
            )

        if self.evidence_results:

            sections.append(
                "evidence"
            )

        if self.graph is not None:

            sections.append(
                "graph"
            )

        if self.temporal is not None:

            sections.append(
                "temporal"
            )

        if self.anomaly is not None:

            sections.append(
                "anomaly"
            )

        if self.clustering is not None:

            sections.append(
                "clustering"
            )

        if self.multimodal_results:

            sections.append(
                "multimodal"
            )

        if self.rag.has_any:

            sections.append(
                "rag"
            )

        return tuple(
            sections
        )

    @property
    def section_count(
        self,
    ) -> int:
        """
        Number of available top-level analytical sections.
        """

        return len(
            self.available_sections
        )

    @property
    def has_analysis(
        self,
    ) -> bool:
        """
        Whether at least one analytical section is available.
        """

        return bool(
            self.available_sections
        )

    # ======================================================
    # Convenient checks
    # ======================================================

    @property
    def has_graph(
        self,
    ) -> bool:

        return (
            self.graph
            is not None
        )

    @property
    def has_temporal(
        self,
    ) -> bool:

        return (
            self.temporal
            is not None
        )

    @property
    def has_anomaly(
        self,
    ) -> bool:

        return (
            self.anomaly
            is not None
        )

    @property
    def has_clustering(
        self,
    ) -> bool:

        return (
            self.clustering
            is not None
        )

    @property
    def has_rag(
        self,
    ) -> bool:

        return (
            self.rag.has_any
        )


# ==========================================================
# Aggregation service
# ==========================================================


class InvestigationUnifiedAnalyticalContextService:
    """
    Pure aggregation service.

    This service intentionally has no repositories, database
    session, search engine, AI provider or mathematical analysis
    services.

    Callers explicitly provide results they want to aggregate.
    """

    # ======================================================
    # Public API
    # ======================================================

    def assemble(
        self,
        *,
        case_id: UUID,

        entity_resolution_results: tuple[
            object,
            ...,
        ] = (),

        evidence_results: tuple[
            object,
            ...,
        ] = (),

        graph: (
            InvestigationGraphAnalysisResult
            | None
        ) = None,

        temporal: (
            InvestigationTemporalAnalysisResult
            | None
        ) = None,

        anomaly: (
            InvestigationAnomalyAnalysisResult
            | None
        ) = None,

        clustering: (
            InvestigationEntityClusteringResult
            | None
        ) = None,

        multimodal_results: tuple[
            object,
            ...,
        ] = (),

        rag_retrieval: (
            InvestigationRAGRetrievalResult
            | None
        ) = None,

        rag_context: (
            InvestigationRAGContext
            | None
        ) = None,

        rag_summary: (
            InvestigationRAGSummaryResult
            | None
        ) = None,

        rag_conclusions: (
            InvestigationRAGConclusionsResult
            | None
        ) = None,

        summary_citations: (
            InvestigationRAGCitationValidation
            | None
        ) = None,

        conclusions_citations: (
            InvestigationRAGConclusionsCitationValidation
            | None
        ) = None,

        warnings: tuple[
            str,
            ...,
        ] = (),

        metadata: Mapping[
            str,
            Any,
        ] | None = None,

    ) -> InvestigationUnifiedAnalyticalContext:
        """
        Assemble already-computed analytical results.

        Nothing is calculated or persisted here.
        """

        normalized_case_id = (
            self._normalize_case_id(
                case_id
            )
        )

        normalized_entity_resolution = (
            self._normalize_object_tuple(
                entity_resolution_results,
                name=(
                    "entity_resolution_results"
                ),
            )
        )

        normalized_evidence = (
            self._normalize_object_tuple(
                evidence_results,
                name=(
                    "evidence_results"
                ),
            )
        )

        normalized_multimodal = (
            self._normalize_object_tuple(
                multimodal_results,
                name=(
                    "multimodal_results"
                ),
            )
        )

        normalized_warnings = (
            self._normalize_warnings(
                warnings
            )
        )

        # --------------------------------------------------
        # RAG package
        # --------------------------------------------------

        rag = InvestigationUnifiedRAGContext(
            retrieval=(
                rag_retrieval
            ),

            context=(
                rag_context
            ),

            summary=(
                rag_summary
            ),

            conclusions=(
                rag_conclusions
            ),

            summary_citations=(
                summary_citations
            ),

            conclusions_citations=(
                conclusions_citations
            ),
        )

        # --------------------------------------------------
        # Case-boundary validation
        # --------------------------------------------------

        self._validate_case_alignment(
            case_id=(
                normalized_case_id
            ),

            values=(
                graph,
                temporal,
                anomaly,
                clustering,
                rag_retrieval,
                rag_context,
                rag_summary,
                rag_conclusions,
                summary_citations,
                conclusions_citations,
                *normalized_entity_resolution,
                *normalized_evidence,
                *normalized_multimodal,
            ),
        )

        normalized_metadata = (
            self._build_metadata(
                metadata
            )
        )

        return (
            InvestigationUnifiedAnalyticalContext(
                case_id=(
                    normalized_case_id
                ),

                generated_at=(
                    datetime.now(
                        timezone.utc
                    )
                ),

                entity_resolution_results=(
                    normalized_entity_resolution
                ),

                evidence_results=(
                    normalized_evidence
                ),

                graph=graph,

                temporal=temporal,

                anomaly=anomaly,

                clustering=clustering,

                multimodal_results=(
                    normalized_multimodal
                ),

                rag=rag,

                warnings=(
                    normalized_warnings
                ),

                metadata=(
                    normalized_metadata
                ),
            )
        )

    # ======================================================
    # Validation
    # ======================================================

    @staticmethod
    def _normalize_case_id(
        case_id: UUID,
    ) -> UUID:
        """
        Require canonical UUID case identity.
        """

        if not isinstance(
            case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        return case_id

    @staticmethod
    def _normalize_object_tuple(
        values: tuple[
            object,
            ...,
        ],
        *,
        name: str,
    ) -> tuple[
        object,
        ...,
    ]:
        """
        Preserve existing result objects without converting them.
        """

        if not isinstance(
            values,
            tuple,
        ):

            raise TypeError(
                f"{name} must be a tuple."
            )

        if any(
            value is None
            for value in values
        ):

            raise ValueError(
                f"{name} cannot contain None."
            )

        return values

    @staticmethod
    def _normalize_warnings(
        warnings: tuple[
            str,
            ...,
        ],
    ) -> tuple[
        str,
        ...,
    ]:
        """
        Normalize aggregation warnings.
        """

        if not isinstance(
            warnings,
            tuple,
        ):

            raise TypeError(
                "warnings must be a tuple."
            )

        normalized: list[
            str
        ] = []

        seen: set[
            str
        ] = set()

        for warning in warnings:

            value = str(
                warning
                or ""
            ).strip()

            if not value:

                continue

            if value in seen:

                continue

            seen.add(
                value
            )

            normalized.append(
                value
            )

        return tuple(
            normalized
        )

    @classmethod
    def _validate_case_alignment(
        cls,
        *,
        case_id: UUID,
        values: tuple[
            object | None,
            ...,
        ],
    ) -> None:
        """
        Reject aggregation of results belonging to another case.

        Some analytical result types do not expose case_id.
        Those are preserved without guessing their provenance.
        """

        for value in values:

            if value is None:

                continue

            value_case_id = (
                cls._extract_case_id(
                    value
                )
            )

            if value_case_id is None:

                continue

            if (
                value_case_id
                !=
                case_id
            ):

                raise ValueError(
                    "Analytical result belongs "
                    "to another case."
                )

    @staticmethod
    def _extract_case_id(
        value: object,
    ) -> UUID | None:
        """
        Read explicit case_id only.

        No repository lookup or inferred provenance is used.
        """

        raw_case_id = getattr(
            value,
            "case_id",
            None,
        )

        if raw_case_id is None:

            return None

        if isinstance(
            raw_case_id,
            UUID,
        ):

            return raw_case_id

        try:

            return UUID(
                str(
                    raw_case_id
                )
            )

        except (
            ValueError,
            TypeError,
            AttributeError,
        ):

            raise ValueError(
                "Analytical result exposes "
                "an invalid case_id."
            )

    # ======================================================
    # Metadata
    # ======================================================

    @staticmethod
    def _build_metadata(
        metadata: Mapping[
            str,
            Any,
        ] | None,
    ) -> Mapping[
        str,
        Any,
    ]:
        """
        Produce shallow immutable metadata.
        """

        result: dict[
            str,
            Any,
        ] = dict(
            metadata
            or {}
        )

        # These boundaries are part of the contract and cannot
        # be silently overridden by caller metadata.
        result.update(
            {
                "layer": (
                    "unified_analytical_context"
                ),

                "analysis_recomputed": False,

                "search_executed": False,

                "ai_executed": False,

                "database_write_performed": False,

                "legacy_workspace_replaced": False,
            }
        )

        return MappingProxyType(
            result
        )

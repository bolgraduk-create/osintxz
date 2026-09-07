"""
Investigation graph-analysis application service.

Connects the investigation EntityGraph to the completed
Phase 3 graph-analysis pipeline.

Pipeline:

case_id
    ↓
EntityGraphService
    ↓
EntityGraph
    ↓
UnifiedGraphAnalysisService
    ↓
UnifiedGraphAnalysisResult
    ↓
GraphExplainabilityService
    ↓
GraphExplainabilityResult
    ↓
InvestigationGraphAnalysisResult

Responsibilities:

- provide one application-level graph-analysis entry point
- build the EntityGraph for one investigation case
- execute unified graph analysis
- build graph explainability
- preserve analytical results without mutation
- expose Entity and pair explanations
- keep graph analysis separate from persistence

Does NOT:

- create Relationships
- modify Relationships
- create or merge Entities
- modify Evidence
- convert graph signals into Entity Resolution signals
- convert link predictions into Relationships
- persist analysis results
- modify InvestigationWorkflow
"""

from __future__ import annotations

from dataclasses import dataclass

from uuid import UUID

from app.analysis.graph_explainability import (
    GraphEntityExplanation,
    GraphExplainabilityResult,
    GraphExplainabilityService,
    GraphPairExplanation,
)

from app.analysis.unified_graph_analysis import (
    UnifiedGraphAnalysisConfig,
    UnifiedGraphAnalysisResult,
    UnifiedGraphAnalysisService,
)

from app.services.entity_graph_service import (
    EntityGraphService,
)


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationGraphAnalysisResult:
    """
    Complete graph-analysis result for one investigation.

    analysis:
        Complete mathematical graph analysis.

    explainability:
        Graph-level and Entity-level explanations.

    Pair explanations are intentionally generated on
    demand to avoid O(N²) materialization.
    """

    case_id: UUID

    analysis: UnifiedGraphAnalysisResult

    explainability: GraphExplainabilityResult

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.analysis,
            UnifiedGraphAnalysisResult,
        ):

            raise TypeError(
                "analysis must be "
                "UnifiedGraphAnalysisResult."
            )

        if not isinstance(
            self.explainability,
            GraphExplainabilityResult,
        ):

            raise TypeError(
                "explainability must be "
                "GraphExplainabilityResult."
            )

        if (
            len(
                self.explainability
                .entity_explanations
            )
            !=
            self.analysis
            .statistics
            .node_count
        ):

            raise ValueError(
                "Explainability Entity count "
                "does not match graph analysis."
            )

    # ==========================================================
    # Convenience statistics
    # ==========================================================

    @property
    def node_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .node_count
        )

    @property
    def edge_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .normalized_edge_count
        )

    @property
    def source_edge_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .source_edge_count
        )

    @property
    def component_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .component_count
        )

    @property
    def community_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .community_count
        )

    @property
    def prediction_count(
        self,
    ) -> int:

        return (
            self.analysis
            .statistics
            .prediction_count
        )

    # ==========================================================
    # Entity access
    # ==========================================================

    def get_entity_analysis(
        self,
        entity_id: UUID,
    ):

        return (
            self.analysis
            .get_entity(
                entity_id
            )
        )

    def get_entity_explanation(
        self,
        entity_id: UUID,
    ) -> GraphEntityExplanation:

        return (
            self.explainability
            .get_entity(
                entity_id
            )
        )


# ==========================================================
# Application service
# ==========================================================


class InvestigationGraphAnalysisService:
    """
    Application-level orchestration for Phase 3.

    EntityGraphService owns graph construction.

    UnifiedGraphAnalysisService owns graph mathematics.

    GraphExplainabilityService owns graph explanations.

    This service only coordinates those boundaries.
    """

    def __init__(
        self,
        entity_graph_service: EntityGraphService,
        unified_graph_analysis_service: (
            UnifiedGraphAnalysisService
            | None
        ) = None,
        graph_explainability_service: (
            GraphExplainabilityService
            | None
        ) = None,
    ) -> None:

        if not isinstance(
            entity_graph_service,
            EntityGraphService,
        ):

            raise TypeError(
                "entity_graph_service must be "
                "EntityGraphService."
            )

        if (
            unified_graph_analysis_service
            is not None
            and
            not isinstance(
                unified_graph_analysis_service,
                UnifiedGraphAnalysisService,
            )
        ):

            raise TypeError(
                "unified_graph_analysis_service "
                "must be UnifiedGraphAnalysisService."
            )

        if (
            graph_explainability_service
            is not None
            and
            not isinstance(
                graph_explainability_service,
                GraphExplainabilityService,
            )
        ):

            raise TypeError(
                "graph_explainability_service "
                "must be GraphExplainabilityService."
            )

        self.entity_graph_service = (
            entity_graph_service
        )

        self.unified_graph_analysis_service = (
            unified_graph_analysis_service
            or
            UnifiedGraphAnalysisService()
        )

        self.graph_explainability_service = (
            graph_explainability_service
            or
            GraphExplainabilityService()
        )

    # ==========================================================
    # Complete investigation graph analysis
    # ==========================================================

    def analyze_case(
        self,
        case_id: str | UUID,
        config: (
            UnifiedGraphAnalysisConfig
            | None
        ) = None,
    ) -> InvestigationGraphAnalysisResult:
        """
        Execute the complete Phase 3 pipeline for one case.

        Database interaction is limited to the existing
        EntityGraphService graph-building read path.

        No graph-analysis persistence is performed.
        """

        case_uuid = (
            self._normalize_case_id(
                case_id
            )
        )

        graph = (
            self.entity_graph_service
            .get_case_graph(
                case_uuid
            )
        )

        analysis = (
            self.unified_graph_analysis_service
            .analyze(
                graph,
                config,
            )
        )

        explainability = (
            self.graph_explainability_service
            .build(
                analysis
            )
        )

        return (
            InvestigationGraphAnalysisResult(
                case_id=case_uuid,
                analysis=analysis,
                explainability=(
                    explainability
                ),
            )
        )

    # ==========================================================
    # On-demand pair explanation
    # ==========================================================

    def explain_pair(
        self,
        result: InvestigationGraphAnalysisResult,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> GraphPairExplanation:
        """
        Explain one Entity pair from an already completed
        investigation analysis.

        Analysis is NOT repeated.
        """

        if not isinstance(
            result,
            InvestigationGraphAnalysisResult,
        ):

            raise TypeError(
                "result must be "
                "InvestigationGraphAnalysisResult."
            )

        return (
            self.graph_explainability_service
            .explain_pair(
                result.analysis,
                source_entity_id,
                target_entity_id,
            )
        )

    # ==========================================================
    # On-demand Entity explanation
    # ==========================================================

    def explain_entity(
        self,
        result: InvestigationGraphAnalysisResult,
        entity_id: UUID,
    ) -> GraphEntityExplanation:
        """
        Explain one Entity from an already completed
        investigation analysis.

        Analysis is NOT repeated.
        """

        if not isinstance(
            result,
            InvestigationGraphAnalysisResult,
        ):

            raise TypeError(
                "result must be "
                "InvestigationGraphAnalysisResult."
            )

        return (
            self.graph_explainability_service
            .explain_entity(
                result.analysis,
                entity_id,
            )
        )

    # ==========================================================
    # Case identifier
    # ==========================================================

    @staticmethod
    def _normalize_case_id(
        case_id: str | UUID,
    ) -> UUID:

        if isinstance(
            case_id,
            UUID,
        ):

            return case_id

        try:

            return UUID(
                str(
                    case_id
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                "Invalid investigation case ID."
            ) from error
"""
Investigation Entity clustering application service.

Block 7 — Clustering.

This service orchestrates existing investigation-level
Graph + Temporal feature extraction and applies the two
independent numerical clustering algorithms:

- DBSCAN
- HDBSCAN

Architecture:

case_id
    ↓
InvestigationGraphAnalysisService
    +
InvestigationTemporalAnalysisService
    ↓
InvestigationEntityFeatureExtractionService
    ↓
NumericFeatureMatrix
    ├── DBSCANClusteringService
    └── HDBSCANClusteringService
            ↓
InvestigationEntityClusteringResult


Important semantic boundaries:

Entity feature cluster
    != Graph community

Entity feature cluster
    != connected component

Entity feature cluster
    != Entity Resolution MATCH

DBSCAN cluster
    != HDBSCAN cluster

DBSCAN noise
    != anomaly proof

HDBSCAN noise
    != anomaly proof

HDBSCAN membership probability
    != Evidence confidence

HDBSCAN membership probability
    != Entity Resolution confidence


This service performs no:

- database writes
- Entity mutation
- Entity merge
- Relationship creation
- Evidence creation
- Entity Resolution decision
- anomaly score fusion
- artificial combined clustering score
"""

from __future__ import annotations

from app.application.investigation_graph_analysis_service import InvestigationGraphAnalysisResult
from app.application.investigation_temporal_analysis_service import InvestigationTemporalAnalysisResult

from dataclasses import (
    dataclass,
    field,
)

from uuid import (
    UUID,
)

from app.analysis.dbscan_clustering import (
    DBSCANClusteringResult,
    DBSCANClusteringService,
    DBSCANConfig,
    DBSCANObservationResult,
)

from app.analysis.hdbscan_clustering import (
    HDBSCANClusteringResult,
    HDBSCANClusteringService,
    HDBSCANConfig,
    HDBSCANObservationResult,
)

from app.application.investigation_entity_feature_extraction_service import (
    InvestigationEntityFeatureExtractionResult,
    InvestigationEntityFeatureExtractionService,
)

from app.application.investigation_graph_analysis_service import (
    InvestigationGraphAnalysisService,
)

from app.application.investigation_temporal_analysis_service import (
    InvestigationTemporalAnalysisService,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationEntityClusteringConfig:
    """
    Investigation Entity clustering configuration.

    DBSCAN and HDBSCAN remain completely independent.

    Their raw labels, memberships and noise assignments are
    never averaged or converted into one artificial score.
    """

    dbscan: DBSCANConfig = field(
        default_factory=DBSCANConfig
    )

    hdbscan: HDBSCANConfig = field(
        default_factory=HDBSCANConfig
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.dbscan,
            DBSCANConfig,
        ):

            raise TypeError(
                "dbscan must be DBSCANConfig."
            )

        if not isinstance(
            self.hdbscan,
            HDBSCANConfig,
        ):

            raise TypeError(
                "hdbscan must be HDBSCANConfig."
            )


# ==========================================================
# Per-Entity analytical view
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationEntityClusteringObservation:
    """
    Combined read-only clustering view for one Entity.

    This object aligns DBSCAN and HDBSCAN by Entity ID.

    It deliberately does NOT produce a combined clustering
    score or identity conclusion.
    """

    entity_id: UUID

    dbscan: (
        DBSCANObservationResult
        | None
    )

    hdbscan: (
        HDBSCANObservationResult
        | None
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.entity_id,
            UUID,
        ):

            raise TypeError(
                "entity_id must be UUID."
            )

        expected_id = str(
            self.entity_id
        )

        # ======================================================
        # DBSCAN alignment
        # ======================================================

        if (
            self.dbscan
            is not None
        ):

            if not isinstance(
                self.dbscan,
                DBSCANObservationResult,
            ):

                raise TypeError(
                    "dbscan must be "
                    "DBSCANObservationResult or None."
                )

            if (
                self.dbscan.observation_id
                !=
                expected_id
            ):

                raise ValueError(
                    "DBSCAN observation does not match "
                    "Entity ID."
                )

        # ======================================================
        # HDBSCAN alignment
        # ======================================================

        if (
            self.hdbscan
            is not None
        ):

            if not isinstance(
                self.hdbscan,
                HDBSCANObservationResult,
            ):

                raise TypeError(
                    "hdbscan must be "
                    "HDBSCANObservationResult or None."
                )

            if (
                self.hdbscan.observation_id
                !=
                expected_id
            ):

                raise ValueError(
                    "HDBSCAN observation does not match "
                    "Entity ID."
                )

    # ==========================================================
    # DBSCAN convenience
    # ==========================================================

    @property
    def dbscan_cluster_id(
        self,
    ) -> (
        int
        | None
    ):

        if self.dbscan is None:

            return None

        return (
            self.dbscan.cluster_id
        )

    @property
    def dbscan_is_noise(
        self,
    ) -> (
        bool
        | None
    ):

        if self.dbscan is None:

            return None

        return (
            self.dbscan.is_noise
        )

    # ==========================================================
    # HDBSCAN convenience
    # ==========================================================

    @property
    def hdbscan_cluster_id(
        self,
    ) -> (
        int
        | None
    ):

        if self.hdbscan is None:

            return None

        return (
            self.hdbscan.cluster_id
        )

    @property
    def hdbscan_is_noise(
        self,
    ) -> (
        bool
        | None
    ):

        if self.hdbscan is None:

            return None

        return (
            self.hdbscan.is_noise
        )

    @property
    def hdbscan_membership_probability(
        self,
    ) -> (
        float
        | None
    ):

        if self.hdbscan is None:

            return None

        return (
            self.hdbscan
            .membership_probability
        )


# ==========================================================
# Complete investigation result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationEntityClusteringResult:
    """
    Complete Entity feature-space clustering result.

    Both clustering models are preserved separately.

    No artificial combined clustering score is produced.
    """

    case_id: UUID

    feature_extraction: (
        InvestigationEntityFeatureExtractionResult
    )

    dbscan: DBSCANClusteringResult

    hdbscan: HDBSCANClusteringResult

    entities: tuple[
        InvestigationEntityClusteringObservation,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        # ======================================================
        # Base types
        # ======================================================

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.feature_extraction,
            InvestigationEntityFeatureExtractionResult,
        ):

            raise TypeError(
                "feature_extraction must be "
                "InvestigationEntityFeatureExtractionResult."
            )

        if not isinstance(
            self.dbscan,
            DBSCANClusteringResult,
        ):

            raise TypeError(
                "dbscan must be "
                "DBSCANClusteringResult."
            )

        if not isinstance(
            self.hdbscan,
            HDBSCANClusteringResult,
        ):

            raise TypeError(
                "hdbscan must be "
                "HDBSCANClusteringResult."
            )

        if not isinstance(
            self.entities,
            tuple,
        ):

            raise TypeError(
                "entities must be tuple."
            )

        # ======================================================
        # Case alignment
        # ======================================================

        if (
            self.feature_extraction.case_id
            !=
            self.case_id
        ):

            raise ValueError(
                "Feature extraction case does not "
                "match clustering case."
            )

        matrix = (
            self.feature_extraction
            .matrix
        )

        # ======================================================
        # Feature contract alignment
        # ======================================================

        if (
            self.dbscan.feature_names
            !=
            matrix.feature_names
        ):

            raise ValueError(
                "DBSCAN feature names do not match "
                "Entity feature matrix."
            )

        if (
            self.hdbscan.feature_names
            !=
            matrix.feature_names
        ):

            raise ValueError(
                "HDBSCAN feature names do not match "
                "Entity feature matrix."
            )

        # ======================================================
        # Sample diagnostics alignment
        # ======================================================

        if (
            self.dbscan.sample_count
            !=
            matrix.sample_count
        ):

            raise ValueError(
                "DBSCAN sample count does not match "
                "Entity feature matrix."
            )

        if (
            self.hdbscan.sample_count
            !=
            matrix.sample_count
        ):

            raise ValueError(
                "HDBSCAN sample count does not match "
                "Entity feature matrix."
            )

        # ======================================================
        # Entity view validation
        # ======================================================

        if (
            len(
                self.entities
            )
            !=
            matrix.sample_count
        ):

            raise ValueError(
                "Entity clustering view count does "
                "not match feature matrix."
            )

        seen: set[
            UUID
        ] = set()

        entity_ids: list[
            UUID
        ] = []

        for entity in (
            self.entities
        ):

            if not isinstance(
                entity,
                InvestigationEntityClusteringObservation,
            ):

                raise TypeError(
                    "entities must contain "
                    "InvestigationEntityClusteringObservation."
                )

            if (
                entity.entity_id
                in seen
            ):

                raise ValueError(
                    "Duplicate Entity in clustering result."
                )

            seen.add(
                entity.entity_id
            )

            entity_ids.append(
                entity.entity_id
            )

        # Canonical deterministic ordering.
        expected_entity_ids = tuple(
            sorted(
                entity_ids,
                key=str,
            )
        )

        if (
            tuple(
                entity_ids
            )
            !=
            expected_entity_ids
        ):

            raise ValueError(
                "Entity clustering results must be "
                "in canonical Entity-ID order."
            )

        matrix_entity_ids = tuple(
            UUID(
                str(
                    observation.observation_id
                )
            )
            for observation
            in matrix.observations
        )

        if (
            tuple(
                entity_ids
            )
            !=
            matrix_entity_ids
        ):

            raise ValueError(
                "Entity clustering results do not "
                "match feature observations."
            )

    # ==========================================================
    # Statistics
    # ==========================================================

    @property
    def entity_count(
        self,
    ) -> int:

        return len(
            self.entities
        )

    @property
    def feature_count(
        self,
    ) -> int:

        return (
            self.feature_extraction
            .matrix
            .feature_count
        )

    @property
    def dbscan_cluster_count(
        self,
    ) -> int:

        return (
            self.dbscan.cluster_count
        )

    @property
    def dbscan_noise_count(
        self,
    ) -> int:

        return (
            self.dbscan.noise_count
        )

    @property
    def hdbscan_cluster_count(
        self,
    ) -> int:

        return (
            self.hdbscan.cluster_count
        )

    @property
    def hdbscan_noise_count(
        self,
    ) -> int:

        return (
            self.hdbscan.noise_count
        )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get_entity(
        self,
        entity_id: (
            UUID
            | str
        ),
    ) -> InvestigationEntityClusteringObservation:

        normalized_id = (
            entity_id
            if isinstance(
                entity_id,
                UUID,
            )
            else UUID(
                str(
                    entity_id
                )
            )
        )

        for entity in (
            self.entities
        ):

            if (
                entity.entity_id
                ==
                normalized_id
            ):

                return entity

        raise KeyError(
            f"Unknown clustered Entity: {normalized_id}"
        )

    @property
    def entity_map(
        self,
    ) -> dict[
        UUID,
        InvestigationEntityClusteringObservation,
    ]:

        return {
            entity.entity_id: entity
            for entity
            in self.entities
        }


# ==========================================================
# Application service
# ==========================================================


class InvestigationEntityClusteringService:
    """
    Investigation-level Entity feature clustering.

    The service owns no repository and no database session.

    Existing Graph, Temporal and feature-extraction layers
    are reused rather than reimplemented.
    """

    def __init__(
        self,
        investigation_graph_analysis_service: (
            InvestigationGraphAnalysisService
        ),
        investigation_temporal_analysis_service: (
            InvestigationTemporalAnalysisService
        ),
        entity_feature_extraction_service: (
            InvestigationEntityFeatureExtractionService
            | None
        ) = None,
        dbscan_clustering_service: (
            DBSCANClusteringService
            | None
        ) = None,
        hdbscan_clustering_service: (
            HDBSCANClusteringService
            | None
        ) = None,
    ) -> None:

        # ======================================================
        # Graph dependency
        # ======================================================

        if not isinstance(
            investigation_graph_analysis_service,
            InvestigationGraphAnalysisService,
        ):

            raise TypeError(
                "investigation_graph_analysis_service "
                "must be InvestigationGraphAnalysisService."
            )

        # ======================================================
        # Temporal dependency
        # ======================================================

        if not isinstance(
            investigation_temporal_analysis_service,
            InvestigationTemporalAnalysisService,
        ):

            raise TypeError(
                "investigation_temporal_analysis_service "
                "must be InvestigationTemporalAnalysisService."
            )

        # ======================================================
        # Feature extraction dependency
        # ======================================================

        if (
            entity_feature_extraction_service
            is not None
            and
            not isinstance(
                entity_feature_extraction_service,
                InvestigationEntityFeatureExtractionService,
            )
        ):

            raise TypeError(
                "entity_feature_extraction_service "
                "must be "
                "InvestigationEntityFeatureExtractionService."
            )

        # ======================================================
        # DBSCAN dependency
        # ======================================================

        if (
            dbscan_clustering_service
            is not None
            and
            not isinstance(
                dbscan_clustering_service,
                DBSCANClusteringService,
            )
        ):

            raise TypeError(
                "dbscan_clustering_service must be "
                "DBSCANClusteringService."
            )

        # ======================================================
        # HDBSCAN dependency
        # ======================================================

        if (
            hdbscan_clustering_service
            is not None
            and
            not isinstance(
                hdbscan_clustering_service,
                HDBSCANClusteringService,
            )
        ):

            raise TypeError(
                "hdbscan_clustering_service must be "
                "HDBSCANClusteringService."
            )

        self.investigation_graph_analysis_service = (
            investigation_graph_analysis_service
        )

        self.investigation_temporal_analysis_service = (
            investigation_temporal_analysis_service
        )

        self.entity_feature_extraction_service = (
            entity_feature_extraction_service
            or
            InvestigationEntityFeatureExtractionService()
        )

        self.dbscan_clustering_service = (
            dbscan_clustering_service
            or
            DBSCANClusteringService()
        )

        self.hdbscan_clustering_service = (
            hdbscan_clustering_service
            or
            HDBSCANClusteringService()
        )

    # ==========================================================
    # Complete case analysis
    # ==========================================================

    def analyze_case(
        self,
        case_id: (
            str
            | UUID
        ),
        config: (
            InvestigationEntityClusteringConfig
            | None
        ) = None,
    ) -> InvestigationEntityClusteringResult:
        """
        Cluster investigation Entities for one case.

        This compatibility entry point preserves the previous
        behavior: Graph and Temporal analysis are calculated here.

        InvestigationAnalysisOrchestrator should instead call
        analyze_precomputed() so already calculated Graph and
        Temporal results can be reused.
        """

        config = (
            config
            or
            InvestigationEntityClusteringConfig()
        )

        if not isinstance(
            config,
            InvestigationEntityClusteringConfig,
        ):

            raise TypeError(
                "config must be "
                "InvestigationEntityClusteringConfig."
            )

        graph_result = (
            self
            .investigation_graph_analysis_service
            .analyze_case(
                case_id
            )
        )

        temporal_result = (
            self
            .investigation_temporal_analysis_service
            .analyze_case(
                case_id
            )
        )

        return self.analyze_precomputed(
            case_id=case_id,
            graph_result=graph_result,
            temporal_result=temporal_result,
            config=config,
        )

    def analyze_precomputed(
        self,
        *,
        case_id: (
            str
            | UUID
        ),
        graph_result: InvestigationGraphAnalysisResult,
        temporal_result: InvestigationTemporalAnalysisResult,
        feature_extraction: (
            InvestigationEntityFeatureExtractionResult
            | None
        ) = None,
        config: (
            InvestigationEntityClusteringConfig
            | None
        ) = None,
    ) -> InvestigationEntityClusteringResult:
        """
        Cluster Entities from already calculated Graph and Temporal
        analysis results.

        feature_extraction may be supplied when the shared Entity
        feature matrix has already been calculated.

        This method never executes Graph or Temporal analysis.
        """

        del case_id

        config = (
            config
            or
            InvestigationEntityClusteringConfig()
        )

        if not isinstance(
            config,
            InvestigationEntityClusteringConfig,
        ):

            raise TypeError(
                "config must be "
                "InvestigationEntityClusteringConfig."
            )

        if not isinstance(
            graph_result,
            InvestigationGraphAnalysisResult,
        ):

            raise TypeError(
                "graph_result must be "
                "InvestigationGraphAnalysisResult."
            )

        if not isinstance(
            temporal_result,
            InvestigationTemporalAnalysisResult,
        ):

            raise TypeError(
                "temporal_result must be "
                "InvestigationTemporalAnalysisResult."
            )

        if feature_extraction is None:

            feature_extraction = (
                self
                .entity_feature_extraction_service
                .extract(
                    graph_result,
                    temporal_result,
                )
            )

        if not isinstance(
            feature_extraction,
            InvestigationEntityFeatureExtractionResult,
        ):

            raise TypeError(
                "feature_extraction must be "
                "InvestigationEntityFeatureExtractionResult."
            )

        matrix = (
            feature_extraction
            .matrix
        )

        dbscan = (
            self
            .dbscan_clustering_service
            .analyze(
                matrix,
                config.dbscan,
            )
        )

        hdbscan = (
            self
            .hdbscan_clustering_service
            .analyze(
                matrix,
                config.hdbscan,
            )
        )

        dbscan_map = {
            observation.observation_id: observation
            for observation
            in dbscan.observations
        }

        hdbscan_map = {
            observation.observation_id: observation
            for observation
            in hdbscan.observations
        }

        entities: list[
            InvestigationEntityClusteringObservation
        ] = []

        for observation in (
            matrix.observations
        ):

            entity_id = UUID(
                str(
                    observation.observation_id
                )
            )

            observation_id = str(
                entity_id
            )

            entities.append(
                InvestigationEntityClusteringObservation(
                    entity_id=(
                        entity_id
                    ),
                    dbscan=(
                        dbscan_map.get(
                            observation_id
                        )
                    ),
                    hdbscan=(
                        hdbscan_map.get(
                            observation_id
                        )
                    ),
                )
            )

        entities.sort(
            key=lambda entity: str(
                entity.entity_id
            )
        )

        return (
            InvestigationEntityClusteringResult(
                case_id=(
                    feature_extraction
                    .case_id
                ),
                feature_extraction=(
                    feature_extraction
                ),
                dbscan=(
                    dbscan
                ),
                hdbscan=(
                    hdbscan
                ),
                entities=tuple(
                    entities
                ),
            )
        )

"""
Unified investigation search service.

Central orchestration layer for investigation search.

Architecture:

InvestigationSearchQuery
        ↓
UnifiedSearchService
        ↓
QueryExpansionService
        ↓
original + conservative variants
        ↓
Registered SearchRetrievers
        ↓
per-retriever variant merge
        ↓
Independent ranked result lists
        ↓
RankFusionService
        ↓
Reciprocal Rank Fusion (RRF)
        ↓
SearchRankingService
        ↓
Mathematical global ranking
        ↓
SearchResultGroupingService
        ↓
redundancy metadata
        ↓
NeuralCrossEncoderRerankingService
        ↓
optional combined neural reranking
        ↓
SearchResultDiversificationService
        ↓
final diversified ordering
        ↓
InvestigationSearchResponse

Responsibilities:

- register search retrievers
- select compatible retrievers
- expand textual queries conservatively
- execute retrieval
- isolate retriever failures
- merge variant matches by object identity
- collect independent rankings
- apply minimum retrieval thresholds
- fuse rankings through RankFusionService
- apply optional global mathematical ranking
- annotate redundancy groups
- apply optional local neural cross-encoder reranking
- diversify redundant result groups
- preserve safe fallback states between refinement layers
- return one unified ranked response

Does NOT:

- implement BM25
- calculate embeddings
- calculate fuzzy similarity
- implement cross-encoder model inference
- perform graph analysis
- perform temporal analysis
- interact with UI
"""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter

from app.investigation.search_query import (
    InvestigationSearchQuery,
    SearchMethod,
)

from app.investigation.search_result import (
    InvestigationSearchHit,
    InvestigationSearchResponse,
)

from app.services.query_expansion_service import (
    QueryExpansionKind,
    QueryExpansionService,
    QueryExpansionVariant,
)

from app.services.rank_fusion_service import (
    RankFusionService,
)

from app.services.search_ranking_service import (
    SearchRankingService,
)

from app.services.search_result_grouping_service import (
    SearchResultGroupingService,
)

from app.services.neural_cross_encoder_reranking_service import (
    NeuralCrossEncoderRerankingService,
)

from app.services.search_result_diversification_service import (
    SearchResultDiversificationService,
)

from app.services.search_confidence_service import (
    SearchConfidenceService,
)

from app.services.search_explanation_service import (
    SearchExplanationService,
)

from app.services.search_retriever import (
    SearchRetriever,
)


class UnifiedSearchService:
    """
    Central investigation search orchestrator.

    One request may activate several independent
    retrieval mechanisms.

    Each mechanism produces its own ranking.

    RankFusionService then combines those rankings
    into one unified result collection.
    """

    def __init__(
        self,
        retrievers: list[
            SearchRetriever
        ]
        | None = None,
        *,
        query_expansion_service: QueryExpansionService
        | None = None,
        rank_fusion_service: RankFusionService
        | None = None,
        search_ranking_service: SearchRankingService
        | None = None,
        search_result_grouping_service: SearchResultGroupingService
        | None = None,
        neural_cross_encoder_reranking_service: NeuralCrossEncoderRerankingService
        | None = None,
        search_result_diversification_service: SearchResultDiversificationService
        | None = None,
        search_confidence_service: SearchConfidenceService
        | None = None,
        search_explanation_service: SearchExplanationService
        | None = None,
    ) -> None:

        self._retrievers: dict[
            str,
            SearchRetriever,
        ] = {}

        self.query_expansion_service = (
            query_expansion_service
            or QueryExpansionService()
        )

        self.rank_fusion_service = (
            rank_fusion_service
            or RankFusionService()
        )

        self.search_ranking_service = (
            search_ranking_service
            or SearchRankingService()
        )

        self.search_result_grouping_service = (
            search_result_grouping_service
            or SearchResultGroupingService()
        )

        self.neural_cross_encoder_reranking_service = (
            neural_cross_encoder_reranking_service
            or NeuralCrossEncoderRerankingService()
        )

        self.search_result_diversification_service = (
            search_result_diversification_service
            or SearchResultDiversificationService(
                grouping_service=(
                    self.search_result_grouping_service
                ),
            )
        )

        self.search_confidence_service = (
            search_confidence_service
            or SearchConfidenceService()
        )

        self.search_explanation_service = (
            search_explanation_service
            or SearchExplanationService()
        )

        if retrievers:

            for retriever in retrievers:

                self.register(
                    retriever
                )

    # ==========================================================
    # Retriever registry
    # ==========================================================

    def register(
        self,
        retriever: SearchRetriever,
        *,
        replace: bool = False,
    ) -> None:
        """
        Register one retrieval mechanism.

        Retriever names must be unique.

        More than one retriever may use the same
        SearchMethod.
        """

        if not isinstance(
            retriever,
            SearchRetriever,
        ):

            raise TypeError(
                "retriever must implement "
                "SearchRetriever."
            )

        name = retriever.name

        if (
            name in self._retrievers
            and not replace
        ):

            raise ValueError(
                f"Search retriever '{name}' "
                "is already registered."
            )

        self._retrievers[
            name
        ] = retriever

    def unregister(
        self,
        name: str,
    ) -> bool:
        """
        Remove one registered retriever.

        Returns True when a retriever existed.
        """

        normalized_name = (
            name.strip()
        )

        if not normalized_name:

            return False

        if (
            normalized_name
            not in self._retrievers
        ):

            return False

        del self._retrievers[
            normalized_name
        ]

        return True

    def get_retriever(
        self,
        name: str,
    ) -> SearchRetriever | None:
        """
        Return registered retriever by name.
        """

        return self._retrievers.get(
            name.strip()
        )

    def retrievers(
        self,
    ) -> list[
        SearchRetriever
    ]:
        """
        Return all registered retrievers ordered
        by execution priority.

        Lower priority values execute first.
        """

        return sorted(
            self._retrievers.values(),
            key=lambda retriever: (
                retriever.priority,
                retriever.name,
            ),
        )

    def enabled_retrievers(
        self,
    ) -> list[
        SearchRetriever
    ]:
        """
        Return enabled retrievers.
        """

        return [
            retriever
            for retriever
            in self.retrievers()
            if retriever.enabled
        ]

    # ==========================================================
    # Search
    # ==========================================================

    def search(
        self,
        query: InvestigationSearchQuery,
    ) -> InvestigationSearchResponse:
        """
        Execute one unified investigation search.

        Pipeline:

            query
                ↓
            retriever selection
                ↓
            conservative query expansion
                ↓
            independent retrieval
                ↓
            variant merge by identity
                ↓
            independent rankings
                ↓
            RRF
                ↓
            optional mathematical ranking
                ↓
            redundancy grouping
                ↓
            optional neural cross-encoder reranking
                ↓
            diversification
                ↓
            unified response

        A failure in one retriever does not stop
        other retrieval mechanisms.
        """

        if not isinstance(
            query,
            InvestigationSearchQuery,
        ):

            raise TypeError(
                "query must be "
                "InvestigationSearchQuery."
            )

        started_at = perf_counter()

        response = (
            InvestigationSearchResponse(
                query=query,
            )
        )

        # ------------------------------------------------------
        # Empty request
        # ------------------------------------------------------

        if query.is_empty:

            response.add_warning(
                "Search request contains "
                "no usable input."
            )

            response.duration_seconds = (
                perf_counter()
                - started_at
            )

            return response

        # ------------------------------------------------------
        # Retriever selection
        # ------------------------------------------------------

        selected = (
            self._select_retrievers(
                query
            )
        )

        if not selected:

            response.add_warning(
                "No registered search retriever "
                "can handle this request."
            )

            response.duration_seconds = (
                perf_counter()
                - started_at
            )

            return response

        response.metadata[
            "retrievers"
        ] = [
            retriever.name
            for retriever in selected
        ]

        # ------------------------------------------------------
        # Query expansion
        # ------------------------------------------------------

        query_variants = (
            self._build_query_variants(
                query
            )
        )

        response.metadata[
            "query_expansion"
        ] = {
            "enabled": (
                query.enable_query_expansion
                and query.has_text_query
            ),
            "applied": (
                query.has_text_query
                and len(
                    query_variants
                )
                > 1
            ),
            "variant_count": (
                len(
                    query_variants
                )
                if query.has_text_query
                else 0
            ),
            "variants": (
                [
                    self._variant_metadata(
                        variant
                    )
                    for variant
                    in query_variants
                ]
                if query.has_text_query
                else []
            ),
            "semantic_original_only": True,
        }

        # ------------------------------------------------------
        # Independent rankings
        # ------------------------------------------------------

        rankings: dict[
            SearchMethod,
            list[
                InvestigationSearchHit
            ],
        ] = {}

        candidate_count = 0
        raw_candidate_count = 0

        expansion_provenance: dict[
            tuple,
            list[
                dict
            ],
        ] = {}

        for retriever in selected:

            (
                hits,
                retriever_raw_count,
            ) = (
                self._execute_retriever_with_expansion(
                    retriever=retriever,
                    query=query,
                    query_variants=(
                        query_variants
                    ),
                    response=response,
                    expansion_provenance=(
                        expansion_provenance
                    ),
                )
            )

            raw_candidate_count += (
                retriever_raw_count
            )

            if hits is None:

                continue

            candidate_count += len(
                hits
            )

            if not hits:

                continue

            # --------------------------------------------------
            # Multiple retrievers may belong to the same
            # SearchMethod.
            #
            # Variant duplicates were already collapsed inside
            # each retriever. Different retrievers belonging to
            # one SearchMethod retain their original
            # retriever-priority ordering.
            #
            # RankFusionService still protects against duplicate
            # contribution inside the final method ranking.
            # --------------------------------------------------

            method_ranking = (
                rankings.setdefault(
                    retriever.method,
                    [],
                )
            )

            method_ranking.extend(
                hits
            )

        response.candidate_count = (
            candidate_count
        )

        response.metadata[
            "query_expansion"
        ][
            "raw_candidate_count"
        ] = raw_candidate_count

        response.metadata[
            "query_expansion"
        ][
            "merged_candidate_count"
        ] = candidate_count

        # ------------------------------------------------------
        # No candidates
        # ------------------------------------------------------

        if not rankings:

            response.total_matches = 0

            response.duration_seconds = (
                perf_counter()
                - started_at
            )

            return response

        # ------------------------------------------------------
        # Rank fusion
        # ------------------------------------------------------

        fused_hits = (
            self.rank_fusion_service
            .fuse(
                rankings
            )
        )

        self._apply_query_expansion_metadata(
            hits=fused_hits,
            query=query,
            query_variants=(
                query_variants
            ),
            expansion_provenance=(
                expansion_provenance
            ),
        )

        # ------------------------------------------------------
        # Global mathematical ranking
        # ------------------------------------------------------

        ranked_hits = fused_hits

        if query.enable_reranking:

            # SearchRankingService intentionally mutates hit
            # scores in place. Preserve the pre-ranking state
            # so a failure can fall back atomically to pure RRF
            # without leaving a partially reranked collection.
            ranking_state = [
                (
                    hit,
                    hit.scores.rerank,
                    hit.scores.final,
                    hit.metadata.get(
                        "mathematical_ranking"
                    ),
                    (
                        "mathematical_ranking"
                        in hit.metadata
                    ),
                    list(
                        hit.reasons
                    ),
                )
                for hit in fused_hits
            ]

            try:

                ranked_hits = (
                    self.search_ranking_service
                    .rank(
                        query=query,
                        hits=fused_hits,
                    )
                )

                response.metadata[
                    "ranking"
                ] = "mathematical"

                response.metadata[
                    "ranking_service"
                ] = (
                    "SearchRankingService"
                )

            except Exception as error:

                for (
                    hit,
                    previous_rerank,
                    previous_final,
                    previous_ranking_metadata,
                    had_ranking_metadata,
                    previous_reasons,
                ) in ranking_state:

                    hit.scores.rerank = (
                        previous_rerank
                    )

                    hit.scores.final = (
                        previous_final
                    )

                    hit.reasons = (
                        previous_reasons
                    )

                    if had_ranking_metadata:

                        hit.metadata[
                            "mathematical_ranking"
                        ] = (
                            previous_ranking_metadata
                        )

                    else:

                        hit.metadata.pop(
                            "mathematical_ranking",
                            None,
                        )

                # Ranking is an optional refinement layer.
                # A failure must not discard valid retrieval
                # and RRF results.
                ranked_hits = fused_hits

                response.add_warning(
                    "Mathematical search ranking failed; "
                    "using RRF order: "
                    f"{error}"
                )

                response.metadata[
                    "ranking"
                ] = "rrf_fallback"

        else:

            response.metadata[
                "ranking"
            ] = "disabled"

        # ------------------------------------------------------
        # Post-fusion refinement pipeline
        # ------------------------------------------------------

        final_hits = ranked_hits

        if query.enable_reranking:

            final_hits = (
                self._apply_post_fusion_refinements(
                    query=query,
                    hits=ranked_hits,
                    response=response,
                )
            )

        else:

            self._set_disabled_post_fusion_metadata(
                query=query,
                response=response,
            )

        # ------------------------------------------------------
        # Confidence + explainability
        # ------------------------------------------------------

        try:

            final_hits = (
                self.search_confidence_service
                .annotate(
                    final_hits
                )
            )

            response.metadata[
                "confidence_scoring"
            ] = {
                "enabled": True,
                "applied": True,
                "service": "SearchConfidenceService",
                "relevance_is_confidence": False,
            }

        except Exception as error:

            response.add_warning(
                "Search confidence annotation failed; "
                "preserving relevance results: "
                f"{error}"
            )

            response.metadata[
                "confidence_scoring"
            ] = {
                "enabled": True,
                "applied": False,
                "service": "SearchConfidenceService",
                "error": str(error),
            }

        try:

            final_hits = (
                self.search_explanation_service
                .annotate(
                    final_hits
                )
            )

            response.metadata[
                "explainability"
            ] = {
                "enabled": True,
                "applied": True,
                "service": "SearchExplanationService",
            }

        except Exception as error:

            response.add_warning(
                "Search explanation annotation failed; "
                "preserving ranked results: "
                f"{error}"
            )

            response.metadata[
                "explainability"
            ] = {
                "enabled": True,
                "applied": False,
                "service": "SearchExplanationService",
                "error": str(error),
            }

        response.total_matches = len(
            final_hits
        )

        response.hits = (
            final_hits
        )

        # Diversification may intentionally change ordering
        # without changing scores. apply_limit therefore only
        # truncates the final already-ordered collection.

        response.apply_limit()

        # ------------------------------------------------------
        # Runtime metadata
        # ------------------------------------------------------

        response.metadata[
            "fusion"
        ] = "rrf"

        response.metadata[
            "reranking_enabled"
        ] = query.enable_reranking

        response.metadata[
            "neural_reranking_enabled"
        ] = (
            query.enable_reranking
            and query.enable_neural_reranking
        )

        response.metadata[
            "ranking_methods"
        ] = [
            method.value
            for method in rankings
        ]

        response.duration_seconds = (
            perf_counter()
            - started_at
        )

        return response


    # ==========================================================
    # Post-fusion refinement pipeline
    # ==========================================================

    def _apply_post_fusion_refinements(
        self,
        *,
        query: InvestigationSearchQuery,
        hits: list[
            InvestigationSearchHit
        ],
        response: InvestigationSearchResponse,
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Apply optional post-fusion refinement layers.

        Pipeline:

            mathematical ranking
                ↓
            redundancy grouping
                ↓
            optional neural cross-encoder
                ↓
            diversification

        Every layer is isolated. A failure in one optional
        refinement must not discard already valid search
        results from the preceding stages.
        """

        current_hits = list(
            hits
        )

        # ------------------------------------------------------
        # Redundancy grouping
        # ------------------------------------------------------

        grouping_applied = False

        try:

            current_hits = (
                self.search_result_grouping_service
                .group(
                    current_hits
                )
            )

            grouping_applied = True

            response.metadata[
                "grouping"
            ] = {
                "enabled": True,
                "applied": True,
                "service": (
                    "SearchResultGroupingService"
                ),
            }

        except Exception as error:

            # Grouping is metadata-only. Remove any partial
            # annotations before continuing with valid ranking.
            for hit in current_hits:

                hit.metadata.pop(
                    "search_grouping",
                    None,
                )

            response.add_warning(
                "Search result grouping failed; "
                "continuing without redundancy groups: "
                f"{error}"
            )

            response.metadata[
                "grouping"
            ] = {
                "enabled": True,
                "applied": False,
                "service": (
                    "SearchResultGroupingService"
                ),
                "error": str(
                    error
                ),
            }

        # ------------------------------------------------------
        # Optional neural cross-encoder reranking
        # ------------------------------------------------------

        if (
            query.enable_neural_reranking
            and query.has_text_query
        ):

            try:

                current_hits = (
                    self.neural_cross_encoder_reranking_service
                    .rerank(
                        query=query,
                        hits=current_hits,
                    )
                )

                neural_error = (
                    self.neural_cross_encoder_reranking_service
                    .last_error
                )

                neural_metadata = {
                    "enabled": True,
                    "applied": (
                        neural_error is None
                        and (
                            self.neural_cross_encoder_reranking_service
                            .last_reranked_count
                            > 0
                        )
                    ),
                    "service": (
                        "NeuralCrossEncoderRerankingService"
                    ),
                    "model": (
                        self.neural_cross_encoder_reranking_service
                        .config
                        .model_identifier
                    ),
                    "candidate_count": (
                        self.neural_cross_encoder_reranking_service
                        .last_candidate_count
                    ),
                    "reranked_count": (
                        self.neural_cross_encoder_reranking_service
                        .last_reranked_count
                    ),
                    "duration_seconds": (
                        self.neural_cross_encoder_reranking_service
                        .last_duration_seconds
                    ),
                    "batch_count": (
                        self.neural_cross_encoder_reranking_service
                        .last_batch_count
                    ),
                    "batch_shapes": [
                        list(
                            shape
                        )
                        for shape
                        in (
                            self.neural_cross_encoder_reranking_service
                            .last_batch_shapes
                        )
                    ],
                    "error": neural_error,
                }

                response.metadata[
                    "neural_reranking"
                ] = neural_metadata

                if neural_error is not None:

                    response.add_warning(
                        "Neural cross-encoder reranking "
                        "failed; mathematical ranking was "
                        "preserved: "
                        f"{neural_error}"
                    )

            except Exception as error:

                # Neural reranking is optional. The service is
                # itself fail-safe, but orchestration also keeps
                # a defensive boundary around the whole stage.
                response.add_warning(
                    "Neural cross-encoder reranking "
                    "failed; continuing with mathematical "
                    "ranking: "
                    f"{error}"
                )

                response.metadata[
                    "neural_reranking"
                ] = {
                    "enabled": True,
                    "applied": False,
                    "service": (
                        "NeuralCrossEncoderRerankingService"
                    ),
                    "error": str(
                        error
                    ),
                }

        else:

            response.metadata[
                "neural_reranking"
            ] = {
                "enabled": False,
                "applied": False,
                "reason": (
                    "disabled"
                    if not query.enable_neural_reranking
                    else "non_text_query"
                ),
            }

        # ------------------------------------------------------
        # Diversification
        # ------------------------------------------------------

        if grouping_applied:

            try:

                current_hits = (
                    self.search_result_diversification_service
                    .diversify(
                        current_hits
                    )
                )

                response.metadata[
                    "diversification"
                ] = {
                    "enabled": True,
                    "applied": True,
                    "service": (
                        "SearchResultDiversificationService"
                    ),
                }

            except Exception as error:

                # Diversification changes ordering only. Remove
                # partial metadata and preserve neural/math order.
                for hit in current_hits:

                    hit.metadata.pop(
                        "search_diversification",
                        None,
                    )

                response.add_warning(
                    "Search result diversification failed; "
                    "preserving relevance order: "
                    f"{error}"
                )

                response.metadata[
                    "diversification"
                ] = {
                    "enabled": True,
                    "applied": False,
                    "service": (
                        "SearchResultDiversificationService"
                    ),
                    "error": str(
                        error
                    ),
                }

        else:

            response.metadata[
                "diversification"
            ] = {
                "enabled": True,
                "applied": False,
                "reason": (
                    "grouping_unavailable"
                ),
            }

        return current_hits

    @staticmethod
    def _set_disabled_post_fusion_metadata(
        *,
        query: InvestigationSearchQuery,
        response: InvestigationSearchResponse,
    ) -> None:
        """
        Record disabled post-fusion refinement state.
        """

        response.metadata[
            "grouping"
        ] = {
            "enabled": False,
            "applied": False,
            "reason": "reranking_disabled",
        }

        response.metadata[
            "neural_reranking"
        ] = {
            "enabled": False,
            "applied": False,
            "requested": (
                query.enable_neural_reranking
            ),
            "reason": "reranking_disabled",
        }

        response.metadata[
            "diversification"
        ] = {
            "enabled": False,
            "applied": False,
            "reason": "reranking_disabled",
        }


    # ==========================================================
    # Query expansion
    # ==========================================================

    def _build_query_variants(
        self,
        query: InvestigationSearchQuery,
    ) -> list[
        QueryExpansionVariant
    ]:
        """
        Build deterministic execution variants.

        Non-text searches still receive one synthetic original
        variant so image/source-object retrieval keeps the exact
        previous execution path.
        """

        variants = (
            self.query_expansion_service
            .expand(
                query
            )
        )

        if variants:

            return variants

        return [
            QueryExpansionVariant(
                text=query.query,
                kind=(
                    QueryExpansionKind.ORIGINAL
                ),
                weight=1.0,
                reason=(
                    "Original search request."
                ),
                metadata={},
            )
        ]

    def _variants_for_retriever(
        self,
        *,
        retriever: SearchRetriever,
        query_variants: list[
            QueryExpansionVariant
        ],
    ) -> list[
        QueryExpansionVariant
    ]:
        """
        Select variants appropriate for one retriever.

        Semantic retrieval deliberately receives only the
        original query. Semantic embeddings already provide a
        broad matching mechanism, while running every spelling
        or transliteration variant would multiply expensive
        embedding calls.

        IMAGE retrieval also receives only the original request.

        Lexical and fuzzy retrievers may use all conservative
        deterministic variants. Structured retrieval is filter-driven,
        so it executes only once against the original request.
        """

        if not query_variants:

            return []

        if retriever.method in {
            SearchMethod.STRUCTURED,
            SearchMethod.SEMANTIC,
            SearchMethod.IMAGE,
        }:

            return [
                query_variants[0]
            ]

        return list(
            query_variants
        )

    def _execute_retriever_with_expansion(
        self,
        *,
        retriever: SearchRetriever,
        query: InvestigationSearchQuery,
        query_variants: list[
            QueryExpansionVariant
        ],
        response: InvestigationSearchResponse,
        expansion_provenance: dict[
            tuple,
            list[
                dict
            ],
        ],
    ) -> tuple[
        list[
            InvestigationSearchHit
        ]
        | None,
        int,
    ]:
        """
        Execute one retriever across eligible query variants.

        Candidates are merged by InvestigationSearchHit
        identity_key before they enter the method ranking.

        The best variant determines candidate ordering, but raw
        retrieval scores are not overwritten.

        Returns:

            (
                merged hits or None,
                raw number of valid hits before variant merge,
            )
        """

        execution_variants = (
            self._variants_for_retriever(
                retriever=retriever,
                query_variants=(
                    query_variants
                ),
            )
        )

        if not execution_variants:

            return (
                [],
                0,
            )

        aggregated: dict[
            tuple,
            dict,
        ] = {}

        raw_candidate_count = 0
        successful_execution = False

        for variant_index, variant in enumerate(
            execution_variants
        ):

            variant_query = (
                self._query_for_variant(
                    query=query,
                    variant=variant,
                )
            )

            hits = self._execute_retriever(
                retriever,
                variant_query,
                response,
            )

            if hits is None:

                continue

            successful_execution = True

            raw_candidate_count += len(
                hits
            )

            if query.minimum_score > 0.0:

                hits = [
                    hit
                    for hit in hits
                    if self._passes_minimum_score(
                        hit=hit,
                        method=(
                            retriever.method
                        ),
                        minimum_score=(
                            query.minimum_score
                        ),
                    )
                ]

            for hit_rank, hit in enumerate(
                hits,
                start=1,
            ):

                raw_score = (
                    self._get_method_score(
                        hit,
                        retriever.method,
                    )
                )

                selection_score = (
                    self._expansion_selection_score(
                        raw_score=raw_score,
                        rank=hit_rank,
                        variant_weight=(
                            variant.weight
                        ),
                    )
                )

                match_metadata = {
                    "text": variant.text,
                    "kind": (
                        variant.kind.value
                    ),
                    "weight": (
                        variant.weight
                    ),
                    "reason": (
                        variant.reason
                    ),
                    "retriever": (
                        retriever.name
                    ),
                    "method": (
                        retriever.method.value
                    ),
                    "rank": hit_rank,
                    "raw_score": (
                        raw_score
                    ),
                    "selection_score": (
                        selection_score
                    ),
                }

                identity = (
                    hit.identity_key
                )

                expansion_provenance.setdefault(
                    identity,
                    [],
                ).append(
                    dict(
                        match_metadata
                    )
                )

                current = aggregated.get(
                    identity
                )

                candidate_key = (
                    selection_score,
                    -variant_index,
                    -hit_rank,
                )

                if current is None:

                    aggregated[
                        identity
                    ] = {
                        "hit": hit,
                        "key": (
                            candidate_key
                        ),
                    }

                    continue

                if (
                    candidate_key
                    >
                    current[
                        "key"
                    ]
                ):

                    current[
                        "hit"
                    ] = hit

                    current[
                        "key"
                    ] = (
                        candidate_key
                    )

        if not successful_execution:

            return (
                None,
                raw_candidate_count,
            )

        ordered = sorted(
            aggregated.values(),
            key=lambda item: (
                -item[
                    "key"
                ][0],
                -item[
                    "key"
                ][1],
                -item[
                    "key"
                ][2],
                str(
                    item[
                        "hit"
                    ].identity_key
                ),
            ),
        )

        return (
            [
                item[
                    "hit"
                ]
                for item
                in ordered[
                    :query.candidate_limit
                ]
            ],
            raw_candidate_count,
        )

    @staticmethod
    def _query_for_variant(
        *,
        query: InvestigationSearchQuery,
        variant: QueryExpansionVariant,
    ) -> InvestigationSearchQuery:
        """
        Create one execution query without recursively
        re-expanding it.
        """

        if (
            variant.kind
            == QueryExpansionKind.ORIGINAL
            and variant.text
            == query.query
        ):

            return replace(
                query,
                enable_query_expansion=False,
            )

        return replace(
            query,
            query=variant.text,
            enable_query_expansion=False,
        )

    @staticmethod
    def _expansion_selection_score(
        *,
        raw_score: float | None,
        rank: int,
        variant_weight: float,
    ) -> float:
        """
        Calculate temporary ordering priority inside one
        retriever.

        Raw normalized retrieval score is preferred when
        available.

        For rank-only retrievers, reciprocal rank provides a
        deterministic fallback.

        This score is internal query-expansion machinery. It is
        not written into SearchScores.
        """

        safe_weight = min(
            1.0,
            max(
                0.0,
                float(
                    variant_weight
                ),
            ),
        )

        if raw_score is not None:

            safe_score = min(
                1.0,
                max(
                    0.0,
                    float(
                        raw_score
                    ),
                ),
            )

            return (
                safe_score
                * safe_weight
            )

        safe_rank = max(
            1,
            int(
                rank
            ),
        )

        return (
            safe_weight
            /
            safe_rank
        )

    def _apply_query_expansion_metadata(
        self,
        *,
        hits: list[
            InvestigationSearchHit
        ],
        query: InvestigationSearchQuery,
        query_variants: list[
            QueryExpansionVariant
        ],
        expansion_provenance: dict[
            tuple,
            list[
                dict
            ],
        ],
    ) -> None:
        """
        Attach merged query-expansion provenance after RRF.

        Metadata is reconstructed from the external provenance
        map rather than relying on RankFusionService to merge
        arbitrary metadata from duplicate hit instances.
        """

        expansion_applied = (
            query.has_text_query
            and query.enable_query_expansion
            and len(
                query_variants
            )
            > 1
        )

        for hit in hits:

            matches = list(
                expansion_provenance.get(
                    hit.identity_key,
                    [],
                )
            )

            matches.sort(
                key=lambda item: (
                    -float(
                        item.get(
                            "selection_score",
                            0.0,
                        )
                    ),
                    (
                        0
                        if item.get(
                            "kind"
                        )
                        == (
                            QueryExpansionKind
                            .ORIGINAL
                            .value
                        )
                        else 1
                    ),
                    int(
                        item.get(
                            "rank",
                            10**9,
                        )
                    ),
                    str(
                        item.get(
                            "retriever",
                            "",
                        )
                    ),
                )
            )

            best = (
                matches[0]
                if matches
                else None
            )

            unique_variant_keys: set[
                tuple[
                    str,
                    str,
                ]
            ] = set()

            matched_variants: list[
                dict
            ] = []

            for match in matches:

                variant_key = (
                    str(
                        match.get(
                            "kind",
                            "",
                        )
                    ),
                    str(
                        match.get(
                            "text",
                            "",
                        )
                    ),
                )

                if (
                    variant_key
                    in unique_variant_keys
                ):

                    continue

                unique_variant_keys.add(
                    variant_key
                )

                matched_variants.append(
                    {
                        "text": (
                            match.get(
                                "text"
                            )
                        ),
                        "kind": (
                            match.get(
                                "kind"
                            )
                        ),
                        "weight": (
                            match.get(
                                "weight"
                            )
                        ),
                    }
                )

            hit.metadata[
                "query_expansion"
            ] = {
                "enabled": (
                    query.enable_query_expansion
                    and query.has_text_query
                ),
                "applied": (
                    expansion_applied
                ),
                "matched_variants": (
                    matched_variants
                ),
                "match_details": (
                    matches
                ),
                "best_variant": (
                    best.get(
                        "text"
                    )
                    if best
                    else None
                ),
                "best_variant_kind": (
                    best.get(
                        "kind"
                    )
                    if best
                    else None
                ),
                "best_variant_weight": (
                    best.get(
                        "weight"
                    )
                    if best
                    else None
                ),
                "best_variant_raw_score": (
                    best.get(
                        "raw_score"
                    )
                    if best
                    else None
                ),
                "best_variant_selection_score": (
                    best.get(
                        "selection_score"
                    )
                    if best
                    else None
                ),
            }

    @staticmethod
    def _variant_metadata(
        variant: QueryExpansionVariant,
    ) -> dict:
        """
        Serialize one generated expansion variant.
        """

        return {
            "text": variant.text,
            "kind": (
                variant.kind.value
            ),
            "weight": (
                variant.weight
            ),
            "reason": (
                variant.reason
            ),
            "metadata": dict(
                variant.metadata
            ),
        }

    # ==========================================================
    # Retriever execution
    # ==========================================================

    def _execute_retriever(
        self,
        retriever: SearchRetriever,
        query: InvestigationSearchQuery,
        response: InvestigationSearchResponse,
    ) -> list[
        InvestigationSearchHit
    ] | None:
        """
        Execute one retriever safely.

        Invalid output or runtime errors are isolated
        from the rest of the search pipeline.
        """

        try:

            hits = retriever.retrieve(
                query
            )

        except Exception as error:

            response.add_error(
                "Retriever "
                f"'{retriever.name}' failed: "
                f"{error}"
            )

            return None

        # ------------------------------------------------------
        # None result
        # ------------------------------------------------------

        if hits is None:

            response.add_warning(
                "Retriever "
                f"'{retriever.name}' returned "
                "None instead of a result list."
            )

            return None

        # ------------------------------------------------------
        # Invalid collection type
        # ------------------------------------------------------

        if not isinstance(
            hits,
            list,
        ):

            response.add_error(
                "Retriever "
                f"'{retriever.name}' returned "
                "an invalid result type."
            )

            return None

        valid_hits: list[
            InvestigationSearchHit
        ] = []

        # ------------------------------------------------------
        # Validate candidates
        # ------------------------------------------------------

        for hit in hits:

            if not isinstance(
                hit,
                InvestigationSearchHit,
            ):

                response.add_warning(
                    "Retriever "
                    f"'{retriever.name}' returned "
                    "an invalid search hit."
                )

                continue

            # --------------------------------------------------
            # Investigation scope boundary
            # --------------------------------------------------
            #
            # Repository-backed retrievers are expected to scope
            # their own queries by case_id. Unified Search still
            # validates that invariant centrally so a buggy, future
            # or third-party retriever cannot leak a hit from another
            # investigation into fusion/ranking.
            #
            # When a request is case-scoped, every returned hit must
            # carry the same case_id. A missing case_id is also
            # rejected because it cannot be proven to belong to the
            # active investigation.
            # --------------------------------------------------

            if (
                query.case_id is not None
                and hit.case_id != query.case_id
            ):

                response.add_warning(
                    "Retriever "
                    f"'{retriever.name}' returned "
                    "a hit outside the active case scope; "
                    "the hit was discarded."
                )

                continue

            hit.add_method(
                retriever.method
            )

            valid_hits.append(
                hit
            )

        # ------------------------------------------------------
        # Candidate limit is per retriever
        # ------------------------------------------------------

        return valid_hits[
            :query.candidate_limit
        ]

    # ==========================================================
    # Retriever selection
    # ==========================================================

    def _select_retrievers(
        self,
        query: InvestigationSearchQuery,
    ) -> list[
        SearchRetriever
    ]:
        """
        Select retrievers compatible with request.
        """

        selected: list[
            SearchRetriever
        ] = []

        for retriever in self.retrievers():

            try:

                supported = (
                    retriever.supports(
                        query
                    )
                )

            except Exception:

                # Capability checks must not break
                # the whole Unified Search pipeline.
                supported = False

            if supported:

                selected.append(
                    retriever
                )

        return selected

    # ==========================================================
    # Minimum score filtering
    # ==========================================================

    def _passes_minimum_score(
        self,
        *,
        hit: InvestigationSearchHit,
        method: SearchMethod,
        minimum_score: float,
    ) -> bool:
        """
        Apply minimum score before RRF.

        Important:

        minimum_score represents retrieval relevance,
        not the RRF score.

        RRF scores describe agreement between rankings
        and should not be treated as probability or
        absolute relevance.

        If a retriever does not provide a normalized
        score for its method, the candidate is preserved
        because rank position may still carry useful
        information.
        """

        score = (
            self._get_method_score(
                hit,
                method,
            )
        )

        if score is None:

            return True

        return (
            score
            >= minimum_score
        )

    @staticmethod
    def _get_method_score(
        hit: InvestigationSearchHit,
        method: SearchMethod,
    ) -> float | None:
        """
        Return normalized score corresponding to
        one retrieval method.
        """

        mapping = {
            SearchMethod.STRUCTURED:
                hit.scores.structured,

            SearchMethod.LEXICAL:
                hit.scores.lexical,

            SearchMethod.FUZZY:
                hit.scores.fuzzy,

            SearchMethod.SEMANTIC:
                hit.scores.semantic,

            SearchMethod.IMAGE:
                hit.scores.image,
        }

        return mapping.get(
            method
        )
"""
Global mathematical search ranking service.

Refines candidates after rank fusion using deterministic,
explainable and field-aware mathematical signals.

Architecture:

Retrievers
    ↓
RankFusionService
    ↓
fusion score
    ↓
SearchRankingService
    ├── fusion strength
    ├── retrieval quality
    ├── method agreement
    └── field-aware query relevance
    ↓
rerank score
    ↓
final score

Field-aware relevance is important because SearchIndex
content may contain semantically different fields.

Example:

MESSAGE_TEXT:
hello

SENDER:
John

CHAT:
Example

A query matching SENDER must not be treated as though
the query appeared inside MESSAGE_TEXT.

This distinction is also required by future:

- neural reranking
- entity resolution
- evidence scoring
- confidence scoring
- OSINT pivoting

Important:

- retrieval scores are preserved unchanged
- fusion score is preserved unchanged
- no embeddings are calculated here
- no database access is performed here
- no LLM or cross-encoder is used here
- every ranking signal remains explainable
"""

from __future__ import annotations


from dataclasses import dataclass
from math import isfinite
import re


from app.investigation.search_query import (
    InvestigationSearchQuery,
    SearchMethod,
)

from app.investigation.search_result import (
    InvestigationSearchHit,
    SearchMatchReason,
)

from app.services.search_index_field_extractor import (
    SearchIndexFieldExtractor,
    SearchIndexFields,
)


# ==========================================================
# Constants
# ==========================================================


_WORD_PATTERN = re.compile(
    r"\w+",
    flags=re.UNICODE,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SearchRankingConfig:
    """
    Global mathematical ranking configuration.

    Main signal weights:

    fusion:
        RRF consensus.

    retrieval:
        absolute retrieval quality.

    agreement:
        how many retrieval mechanisms found the object.

    text:
        field-aware direct query relevance.

    Field multipliers describe semantic importance inside
    structured objects.

    A field multiplier is NOT evidence confidence.
    It only expresses query relevance.
    """

    # ======================================================
    # Global signal weights
    # ======================================================

    fusion_weight: float = 0.50

    retrieval_weight: float = 0.20

    agreement_weight: float = 0.05

    text_weight: float = 0.25

    # ======================================================
    # Message fields
    # ======================================================

    message_text_multiplier: float = 1.00

    message_external_id_multiplier: float = 0.95

    message_sender_multiplier: float = 0.35

    message_receiver_multiplier: float = 0.30

    message_chat_multiplier: float = 0.20

    message_sent_at_multiplier: float = 0.15

    message_metadata_multiplier: float = 0.10

    # ======================================================
    # Other object fields
    # ======================================================

    entity_content_multiplier: float = 0.65

    generic_content_multiplier: float = 0.90

    def __post_init__(
        self,
    ) -> None:
        """
        Validate all weights and multipliers.
        """

        global_weights = (
            self.fusion_weight,
            self.retrieval_weight,
            self.agreement_weight,
            self.text_weight,
        )

        for weight in global_weights:

            self._validate_non_negative(
                weight,
                "Search ranking weight",
            )

        if sum(
            global_weights
        ) <= 0.0:

            raise ValueError(
                "At least one search ranking "
                "weight must be greater than zero."
            )

        multipliers = (
            self.message_text_multiplier,
            self.message_external_id_multiplier,
            self.message_sender_multiplier,
            self.message_receiver_multiplier,
            self.message_chat_multiplier,
            self.message_sent_at_multiplier,
            self.message_metadata_multiplier,
            self.entity_content_multiplier,
            self.generic_content_multiplier,
        )

        for multiplier in multipliers:

            self._validate_unit_interval(
                multiplier,
                "Search field multiplier",
            )

    @staticmethod
    def _validate_non_negative(
        value: float,
        name: str,
    ) -> None:

        if not isfinite(
            value
        ):

            raise ValueError(
                f"{name} must be finite."
            )

        if value < 0.0:

            raise ValueError(
                f"{name} cannot be negative."
            )

    @staticmethod
    def _validate_unit_interval(
        value: float,
        name: str,
    ) -> None:

        if not isfinite(
            value
        ):

            raise ValueError(
                f"{name} must be finite."
            )

        if not (
            0.0
            <= value
            <= 1.0
        ):

            raise ValueError(
                f"{name} must be between "
                "0.0 and 1.0."
            )


# ==========================================================
# Ranking signals
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SearchRankingSignals:
    """
    Independent mathematical ranking signals.
    """

    fusion: float | None

    retrieval: float | None

    agreement: float | None

    text: float | None

    def as_dict(
        self,
    ) -> dict[str, float]:
        """
        Return available signals.
        """

        values = {
            "fusion": self.fusion,
            "retrieval": self.retrieval,
            "agreement": self.agreement,
            "text": self.text,
        }

        return {
            name: value
            for name, value
            in values.items()
            if value is not None
        }


# ==========================================================
# Field relevance result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SearchFieldRelevance:
    """
    Explainable field-aware relevance result.
    """

    score: float

    best_field: str | None

    field_scores: dict[
        str,
        float,
    ]

    raw_field_scores: dict[
        str,
        float,
    ]

    field_multipliers: dict[
        str,
        float,
    ]

    def as_dict(
        self,
    ) -> dict:
        """
        Serialize explainable field relevance.
        """

        return {
            "score": self.score,
            "best_field": self.best_field,
            "field_scores": dict(
                self.field_scores
            ),
            "raw_field_scores": dict(
                self.raw_field_scores
            ),
            "field_multipliers": dict(
                self.field_multipliers
            ),
        }


# ==========================================================
# Ranking service
# ==========================================================


class SearchRankingService:
    """
    Global deterministic mathematical search ranker.

    Receives already fused search candidates and refines
    ordering using field-aware relevance.

    It does not make identity or evidence-confidence
    conclusions.
    """

    RANKING_METADATA_KEY = (
        "mathematical_ranking"
    )

    RANKING_REASON_KEY = (
        "search_ranking_service"
    )

    def __init__(
        self,
        config: SearchRankingConfig
        | None = None,
        *,
        field_extractor: (
            SearchIndexFieldExtractor
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or SearchRankingConfig()
        )

        self.field_extractor = (
            field_extractor
            or SearchIndexFieldExtractor()
        )

    # ======================================================
    # Public API
    # ======================================================

    def rank(
        self,
        *,
        query: InvestigationSearchQuery,
        hits: list[
            InvestigationSearchHit
        ],
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Refine fused search candidates.

        Original retrieval and fusion scores are preserved.

        scores.rerank and scores.final receive the
        mathematical ranking score.
        """

        if not hits:

            return []

        participating_methods = (
            self._collect_participating_methods(
                hits
            )
        )

        for hit in hits:

            fields = (
                self._extract_hit_fields(
                    hit
                )
            )

            field_relevance = (
                self._field_relevance(
                    query=query,
                    hit=hit,
                    fields=fields,
                )
            )

            signals = (
                self._calculate_signals(
                    hit=hit,
                    participating_methods=(
                        participating_methods
                    ),
                    field_relevance=(
                        field_relevance
                    ),
                )
            )

            ranking_score = (
                self._combine_signals(
                    signals
                )
            )

            hit.metadata[
                self.RANKING_METADATA_KEY
            ] = {
                "score": ranking_score,
                "signals": (
                    signals.as_dict()
                ),
                "weights": (
                    self._available_weights(
                        signals
                    )
                ),
                "field_relevance": (
                    field_relevance.as_dict()
                ),
            }

            hit.scores.rerank = (
                ranking_score
            )

            hit.scores.final = (
                ranking_score
            )

            self._replace_ranking_reason(
                hit=hit,
                score=ranking_score,
                signals=signals,
                field_relevance=(
                    field_relevance
                ),
            )

        ranked = list(
            hits
        )

        ranked.sort(
            key=lambda hit: (
                -hit.final_score,
                -(
                    hit.scores.fusion
                    if hit.scores.fusion
                    is not None
                    else 0.0
                ),
                str(
                    hit.object_id
                ),
            )
        )

        return ranked

    # ======================================================
    # Field extraction
    # ======================================================

    def _extract_hit_fields(
        self,
        hit: InvestigationSearchHit,
    ) -> SearchIndexFields:
        """
        Resolve structured fields from SearchIndex-backed
        hits.

        title/snippet are supplied as fallbacks because
        not every future retriever must expose SearchIndex
        as hit.source.
        """

        return self.field_extractor.extract(
            source=hit.source,
            object_type=(
                hit.object_type
            ),
            title=(
                hit.title
            ),
            content=(
                hit.snippet
            ),
        )

    # ======================================================
    # Signal calculation
    # ======================================================

    def _calculate_signals(
        self,
        *,
        hit: InvestigationSearchHit,
        participating_methods: set[
            SearchMethod
        ],
        field_relevance: (
            SearchFieldRelevance
        ),
    ) -> SearchRankingSignals:
        """
        Calculate all global ranking signals.
        """

        return SearchRankingSignals(
            fusion=(
                self._fusion_signal(
                    hit
                )
            ),
            retrieval=(
                self._retrieval_signal(
                    hit
                )
            ),
            agreement=(
                self._agreement_signal(
                    hit=hit,
                    participating_methods=(
                        participating_methods
                    ),
                )
            ),
            text=(
                field_relevance.score
            ),
        )

    # ======================================================
    # Fusion
    # ======================================================

    @staticmethod
    def _fusion_signal(
        hit: InvestigationSearchHit,
    ) -> float | None:
        """
        Preserve normalized RRF fusion score.
        """

        if hit.scores.fusion is None:

            return None

        return SearchRankingService._clamp(
            hit.scores.fusion
        )

    # ======================================================
    # Retrieval quality
    # ======================================================

    @staticmethod
    def _retrieval_signal(
        hit: InvestigationSearchHit,
    ) -> float | None:
        """
        Mean of available normalized retrieval signals.

        No search method receives a preference here.
        Method weighting belongs to RankFusionService.
        """

        values = list(
            hit.scores
            .retrieval_scores()
            .values()
        )

        if not values:

            return None

        return SearchRankingService._clamp(
            sum(
                values
            )
            /
            len(
                values
            )
        )

    # ======================================================
    # Method agreement
    # ======================================================

    @staticmethod
    def _agreement_signal(
        *,
        hit: InvestigationSearchHit,
        participating_methods: set[
            SearchMethod
        ],
    ) -> float | None:
        """
        Fraction of participating retrieval methods which
        matched this object.

        This is search-method agreement only.

        It must NOT later be interpreted as independent
        evidence confidence.
        """

        if not participating_methods:

            return None

        matched = {
            method
            for method
            in hit.matched_methods
            if (
                method
                != SearchMethod.AUTO
                and method
                in participating_methods
            )
        }

        return SearchRankingService._clamp(
            len(
                matched
            )
            /
            len(
                participating_methods
            )
        )

    # ======================================================
    # Field-aware relevance
    # ======================================================

    def _field_relevance(
        self,
        *,
        query: InvestigationSearchQuery,
        hit: InvestigationSearchHit,
        fields: SearchIndexFields,
    ) -> SearchFieldRelevance:
        """
        Calculate query relevance while respecting field
        semantics.
        """

        normalized_query = (
            self._normalize_text(
                query.query
            )
        )

        if not normalized_query:

            return SearchFieldRelevance(
                score=0.0,
                best_field=None,
                field_scores={},
                raw_field_scores={},
                field_multipliers={},
            )

        if (
            hit.object_type
            == "message"
        ):

            return (
                self._message_field_relevance(
                    query=normalized_query,
                    fields=fields,
                )
            )

        return (
            self._generic_field_relevance(
                query=normalized_query,
                hit=hit,
                fields=fields,
            )
        )

    # ======================================================
    # Message field relevance
    # ======================================================

    def _message_field_relevance(
        self,
        *,
        query: str,
        fields: SearchIndexFields,
    ) -> SearchFieldRelevance:
        """
        Rank message fields by their semantic role.

        MESSAGE_TEXT is primary.

        SENDER/RECEIVER/CHAT are context and therefore
        cannot receive the same contribution as direct
        message-text relevance.

        EXTERNAL_ID remains strong because an exact
        identifier query is highly specific.
        """

        candidates = {
            "message_text": (
                fields.message_text,
                self.config
                .message_text_multiplier,
            ),
            "external_id": (
                fields.external_id,
                self.config
                .message_external_id_multiplier,
            ),
            "sender": (
                fields.sender,
                self.config
                .message_sender_multiplier,
            ),
            "receiver": (
                fields.receiver,
                self.config
                .message_receiver_multiplier,
            ),
            "chat": (
                fields.chat,
                self.config
                .message_chat_multiplier,
            ),
            "sent_at": (
                fields.sent_at,
                self.config
                .message_sent_at_multiplier,
            ),
            "metadata": (
                fields.metadata_text,
                self.config
                .message_metadata_multiplier,
            ),
        }

        return self._score_fields(
            query=query,
            candidates=candidates,
        )

    # ======================================================
    # Generic object relevance
    # ======================================================

    def _generic_field_relevance(
        self,
        *,
        query: str,
        hit: InvestigationSearchHit,
        fields: SearchIndexFields,
    ) -> SearchFieldRelevance:
        """
        Field relevance for entities, documents, evidence,
        reports, notes, artifacts and future object types.
        """

        if (
            hit.object_type
            == "entity"
        ):

            content_multiplier = (
                self.config
                .entity_content_multiplier
            )

        else:

            content_multiplier = (
                self.config
                .generic_content_multiplier
            )

        candidates = {
            "title": (
                fields.title,
                1.0,
            ),
            "content": (
                fields.raw_content,
                content_multiplier,
            ),
        }

        return self._score_fields(
            query=query,
            candidates=candidates,
        )

    # ======================================================
    # Field scoring
    # ======================================================

    def _score_fields(
        self,
        *,
        query: str,
        candidates: dict[
            str,
            tuple[
                str,
                float,
            ],
        ],
    ) -> SearchFieldRelevance:
        """
        Score fields independently and use the strongest
        semantically weighted field.

        Fields are deliberately not summed.

        This prevents one fact repeated across several
        representations from appearing as several
        independent relevance signals.
        """

        raw_scores: dict[
            str,
            float,
        ] = {}

        weighted_scores: dict[
            str,
            float,
        ] = {}

        multipliers: dict[
            str,
            float,
        ] = {}

        best_field: str | None = None

        best_score = 0.0

        for (
            field_name,
            (
                value,
                multiplier,
            ),
        ) in candidates.items():

            normalized_value = (
                self._normalize_text(
                    value
                )
            )

            if not normalized_value:

                continue

            raw_score = (
                self._direct_text_relevance(
                    query=query,
                    candidate=(
                        normalized_value
                    ),
                )
            )

            weighted_score = (
                self._clamp(
                    raw_score
                    * multiplier
                )
            )

            raw_scores[
                field_name
            ] = raw_score

            weighted_scores[
                field_name
            ] = weighted_score

            multipliers[
                field_name
            ] = multiplier

            if (
                weighted_score
                > best_score
            ):

                best_score = (
                    weighted_score
                )

                best_field = (
                    field_name
                )

        return SearchFieldRelevance(
            score=(
                self._clamp(
                    best_score
                )
            ),
            best_field=best_field,
            field_scores=(
                weighted_scores
            ),
            raw_field_scores=(
                raw_scores
            ),
            field_multipliers=(
                multipliers
            ),
        )

    # ======================================================
    # Direct text relevance
    # ======================================================

    def _direct_text_relevance(
        self,
        *,
        query: str,
        candidate: str,
    ) -> float:
        """
        Measure direct textual relevance inside ONE
        semantic field.

        Scoring:

        exact complete match
            1.00

        query phrase contained in field
            0.95

        token coverage
            up to 0.90

        This deliberately reserves the strongest score for
        true direct matches.
        """

        if (
            not query
            or not candidate
        ):

            return 0.0

        if query == candidate:

            return 1.0

        if query in candidate:

            return 0.95

        query_tokens = (
            self._tokenize(
                query
            )
        )

        candidate_tokens = (
            self._tokenize(
                candidate
            )
        )

        if (
            not query_tokens
            or not candidate_tokens
        ):

            return 0.0

        coverage = (
            self._token_coverage(
                query_tokens=(
                    query_tokens
                ),
                candidate_tokens=(
                    candidate_tokens
                ),
            )
        )

        return self._clamp(
            coverage
            * 0.90
        )

    # ======================================================
    # Final mathematical score
    # ======================================================

    def _combine_signals(
        self,
        signals: SearchRankingSignals,
    ) -> float:
        """
        Combine available global signals using normalized
        weighted average.

        Missing signals do not penalize a candidate.
        """

        signal_values = {
            "fusion": signals.fusion,
            "retrieval": (
                signals.retrieval
            ),
            "agreement": (
                signals.agreement
            ),
            "text": signals.text,
        }

        signal_weights = {
            "fusion": (
                self.config
                .fusion_weight
            ),
            "retrieval": (
                self.config
                .retrieval_weight
            ),
            "agreement": (
                self.config
                .agreement_weight
            ),
            "text": (
                self.config
                .text_weight
            ),
        }

        weighted_sum = 0.0

        total_weight = 0.0

        for (
            name,
            value,
        ) in signal_values.items():

            if value is None:

                continue

            weight = (
                signal_weights[
                    name
                ]
            )

            if weight <= 0.0:

                continue

            weighted_sum += (
                self._clamp(
                    value
                )
                * weight
            )

            total_weight += weight

        if total_weight <= 0.0:

            return 0.0

        return self._clamp(
            weighted_sum
            /
            total_weight
        )

    # ======================================================
    # Participating methods
    # ======================================================

    @staticmethod
    def _collect_participating_methods(
        hits: list[
            InvestigationSearchHit
        ],
    ) -> set[
        SearchMethod
    ]:
        """
        Discover retrieval methods that actually
        participated in this response.
        """

        methods: set[
            SearchMethod
        ] = set()

        for hit in hits:

            for method in (
                hit.matched_methods
            ):

                if (
                    method
                    == SearchMethod.AUTO
                ):

                    continue

                methods.add(
                    method
                )

        return methods

    # ======================================================
    # Explainability
    # ======================================================

    def _replace_ranking_reason(
        self,
        *,
        hit: InvestigationSearchHit,
        score: float,
        signals: SearchRankingSignals,
        field_relevance: (
            SearchFieldRelevance
        ),
    ) -> None:
        """
        Store one idempotent explainable ranking reason.
        """

        hit.reasons = [
            reason
            for reason
            in hit.reasons
            if (
                reason.details.get(
                    "source"
                )
                != self.RANKING_REASON_KEY
            )
        ]

        hit.add_reason(
            SearchMatchReason(
                reason=(
                    "Mathematical ranking combined "
                    "RRF fusion, retrieval quality, "
                    "method agreement and field-aware "
                    "query relevance."
                ),
                method=None,
                score=score,
                details={
                    "source": (
                        self.RANKING_REASON_KEY
                    ),
                    "signals": (
                        signals.as_dict()
                    ),
                    "weights": (
                        self._available_weights(
                            signals
                        )
                    ),
                    "field_relevance": (
                        field_relevance
                        .as_dict()
                    ),
                },
            )
        )

    # ======================================================
    # Weight metadata
    # ======================================================

    def _available_weights(
        self,
        signals: SearchRankingSignals,
    ) -> dict[
        str,
        float
    ]:
        """
        Return active global signal weights.
        """

        values = {
            "fusion": (
                signals.fusion,
                self.config
                .fusion_weight,
            ),
            "retrieval": (
                signals.retrieval,
                self.config
                .retrieval_weight,
            ),
            "agreement": (
                signals.agreement,
                self.config
                .agreement_weight,
            ),
            "text": (
                signals.text,
                self.config
                .text_weight,
            ),
        }

        return {
            name: weight
            for (
                name,
                (
                    value,
                    weight,
                ),
            )
            in values.items()
            if (
                value is not None
                and weight > 0.0
            )
        }

    # ======================================================
    # Text helpers
    # ======================================================

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        """
        Normalize text for deterministic matching.
        """

        if not value:

            return ""

        return " ".join(
            value
            .casefold()
            .split()
        )

    @staticmethod
    def _tokenize(
        value: str,
    ) -> set[str]:
        """
        Tokenize Unicode text.
        """

        if not value:

            return set()

        return {
            token
            for token
            in _WORD_PATTERN.findall(
                value
            )
            if token
        }

    @staticmethod
    def _token_coverage(
        *,
        query_tokens: set[str],
        candidate_tokens: set[str],
    ) -> float:
        """
        Fraction of unique query tokens present in one
        candidate field.
        """

        if not query_tokens:

            return 0.0

        overlap = (
            query_tokens
            & candidate_tokens
        )

        return SearchRankingService._clamp(
            len(
                overlap
            )
            /
            len(
                query_tokens
            )
        )

    # ======================================================
    # Numerical helpers
    # ======================================================

    @staticmethod
    def _clamp(
        value: float,
    ) -> float:
        """
        Clamp numerical signal to 0..1.
        """

        if not isfinite(
            value
        ):

            return 0.0

        return min(
            1.0,
            max(
                0.0,
                float(
                    value
                ),
            ),
        )
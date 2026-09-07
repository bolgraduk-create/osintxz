"""
Semantic message reranker.

Performs lightweight local reranking of Message candidates
returned from semantic conversation chunks.

Architecture:

Semantic chunk similarity
        +
query/message textual relevance
        ↓
local ranking score

The service does NOT generate embeddings.

It exists to solve an important property of chunk search:

A semantically relevant conversation chunk does not imply
that every individual Message inside that chunk is equally
relevant.

Responsibilities:

- calculate token overlap
- detect direct phrase matches
- calculate fuzzy similarity
- combine local relevance with chunk similarity

Does NOT:

- query Ollama
- access PostgreSQL
- generate embeddings
- perform RRF
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.fuzzy_search_service import (
    FuzzySearchService,
)


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SemanticMessageRerankResult:
    """
    Message-level reranking result.
    """

    chunk_similarity: float

    local_relevance: float

    ranking_score: float

    phrase_score: float

    token_score: float

    fuzzy_score: float


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SemanticMessageRerankerConfig:
    """
    Reranker configuration.

    chunk_weight:
        Weight of conversation-level semantic similarity.

    local_weight:
        Weight of message-level textual relevance.

    The two values must sum to 1.0.
    """

    chunk_weight: float = 0.70

    local_weight: float = 0.30

    def __post_init__(
        self,
    ) -> None:

        if not (
            0.0
            <= self.chunk_weight
            <= 1.0
        ):

            raise ValueError(
                "chunk_weight must be between 0 and 1."
            )

        if not (
            0.0
            <= self.local_weight
            <= 1.0
        ):

            raise ValueError(
                "local_weight must be between 0 and 1."
            )

        total = (
            self.chunk_weight
            + self.local_weight
        )

        if abs(
            total - 1.0
        ) > 0.000001:

            raise ValueError(
                "chunk_weight and local_weight "
                "must sum to 1.0."
            )


# ==========================================================
# Reranker
# ==========================================================


class SemanticMessageReranker:
    """
    Lightweight semantic-message candidate reranker.
    """

    _TOKEN_PATTERN = re.compile(
        r"\w+",
        flags=re.UNICODE,
    )

    def __init__(
        self,
        *,
        fuzzy_search_service: (
            FuzzySearchService
            | None
        ) = None,
        config: (
            SemanticMessageRerankerConfig
            | None
        ) = None,
    ) -> None:

        self.fuzzy_search_service = (
            fuzzy_search_service
            or FuzzySearchService()
        )

        self.config = (
            config
            or SemanticMessageRerankerConfig()
        )

    # ======================================================
    # Public API
    # ======================================================

    def score(
        self,
        *,
        query: str,
        message_text: str,
        chunk_similarity: float,
    ) -> SemanticMessageRerankResult:
        """
        Calculate local Message relevance inside a
        semantic chunk.
        """

        normalized_query = (
            self._normalize(
                query
            )
        )

        normalized_message = (
            self._normalize(
                message_text
            )
        )

        normalized_chunk_similarity = (
            self._clamp(
                chunk_similarity
            )
        )

        if (
            not normalized_query
            or not normalized_message
        ):

            return SemanticMessageRerankResult(
                chunk_similarity=(
                    normalized_chunk_similarity
                ),
                local_relevance=0.0,
                ranking_score=(
                    self.config.chunk_weight
                    * normalized_chunk_similarity
                ),
                phrase_score=0.0,
                token_score=0.0,
                fuzzy_score=0.0,
            )

        phrase_score = (
            self._phrase_score(
                normalized_query,
                normalized_message,
            )
        )

        token_score = (
            self._token_score(
                normalized_query,
                normalized_message,
            )
        )

        fuzzy_score = (
            self._fuzzy_score(
                normalized_query,
                normalized_message,
            )
        )

        # --------------------------------------------------
        # Local relevance
        # --------------------------------------------------
        #
        # Phrase match is strongest.
        #
        # Token coverage is especially useful for queries
        # such as:
        #
        #     планы на субботу
        #
        # versus:
        #
        #     а у нас были планы на субботу?
        #
        # Fuzzy matching helps with typos and inflections.
        # --------------------------------------------------

        if token_score > 0.0:

            local_relevance = max(
                phrase_score,
                (
                    0.80
                    * token_score
                    + 0.20
                    * fuzzy_score
                ),
            )

        else:

            # Fuzzy similarity alone must not promote a message
            # strongly when there is no informative lexical
            # evidence.
            local_relevance = max(
                phrase_score,
                (
                    0.10
                    * fuzzy_score
                ),
            )

        local_relevance = (
            self._clamp(
                local_relevance
            )
        )

        ranking_score = (
            self.config.chunk_weight
            * normalized_chunk_similarity
            + self.config.local_weight
            * local_relevance
        )

        return SemanticMessageRerankResult(
            chunk_similarity=(
                normalized_chunk_similarity
            ),
            local_relevance=(
                local_relevance
            ),
            ranking_score=(
                self._clamp(
                    ranking_score
                )
            ),
            phrase_score=phrase_score,
            token_score=token_score,
            fuzzy_score=fuzzy_score,
        )

    # ======================================================
    # Phrase
    # ======================================================

    @staticmethod
    def _phrase_score(
        query: str,
        message: str,
    ) -> float:
        """
        Direct phrase containment score.
        """

        if query == message:

            return 1.0

        if query in message:

            return 1.0

        if message in query:

            ratio = (
                len(message)
                / max(
                    len(query),
                    1,
                )
            )

            return min(
                0.85,
                ratio,
            )

        return 0.0

    # ======================================================
    # Tokens
    # ======================================================

    def _token_score(
        self,
        query: str,
        message: str,
    ) -> float:
        """
        Measure how much of the query vocabulary appears
        in the Message.

        Query coverage is more important than symmetric
        Jaccard similarity because investigation messages
        often contain additional words.
        """

        query_tokens = set(
            self._tokens(
                query
            )
        )

        message_tokens = set(
            self._tokens(
                message
            )
        )

        if (
            not query_tokens
            or not message_tokens
        ):

            return 0.0

        intersection = (
            query_tokens
            & message_tokens
        )

        if not intersection:

            return 0.0

        query_coverage = (
            len(intersection)
            / len(query_tokens)
        )

        jaccard = (
            len(intersection)
            / len(
                query_tokens
                | message_tokens
            )
        )

        return self._clamp(
            0.80
            * query_coverage
            + 0.20
            * jaccard
        )

    # ======================================================
    # Fuzzy
    # ======================================================

    def _fuzzy_score(
        self,
        query: str,
        message: str,
    ) -> float:
        """
        Calculate existing project fuzzy similarity.
        """

        try:

            comparison = (
                self.fuzzy_search_service
                .compare(
                    query,
                    message,
                )
            )

        except Exception:

            return 0.0

        return self._clamp(
            float(
                comparison.combined
            )
        )

    # ======================================================
    # Normalization
    # ======================================================

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:

        return " ".join(
            str(
                value
            )
            .lower()
            .split()
        )

    def _tokens(
        self,
        value: str,
    ) -> list[str]:
        """
        Extract informative tokens.

        Common grammatical words are excluded because they
        provide almost no evidence of message-level relevance.
        """

        tokens = (
            self._TOKEN_PATTERN.findall(
                value.lower()
            )
        )

        return [
            token
            for token in tokens
            if (
                len(token) >= 2
                and token
                not in self._STOPWORDS
            )
        ]

    # ======================================================
    # Helpers
    # ======================================================

    @staticmethod
    def _clamp(
        value: float,
    ) -> float:

        return max(
            0.0,
            min(
                1.0,
                float(
                    value
                ),
            ),
        )

    _STOPWORDS = {
    # Russian
    "а",
    "и",
    "но",
    "или",
    "на",
    "в",
    "во",
    "к",
    "ко",
    "с",
    "со",
    "у",
    "о",
    "об",
    "от",
    "до",
    "за",
    "по",
    "из",
    "для",
    "при",
    "под",
    "над",
    "не",
    "ни",
    "бы",
    "же",
    "ли",
    "это",
    "этот",
    "эта",
    "эти",
    "то",
    "так",
    "как",
    "что",
    "чтобы",
    "кто",
    "где",
    "когда",

    # Ukrainian
    "і",
    "й",
    "та",
    "але",
    "або",
    "на",
    "в",
    "у",
    "з",
    "із",
    "до",
    "за",
    "по",
    "для",
    "не",
    "ні",
    "це",
    "що",
    "як",
    "де",
    "коли",

    # English
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "of",
    "for",
    "from",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
}
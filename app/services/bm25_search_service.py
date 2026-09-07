"""
BM25 search scoring service.

Provides mathematical BM25 relevance scoring for
the Unified Investigation Search Engine.

Architecture:

documents
    ↓
BM25SearchService
    ↓
tokenization
document frequency
IDF
document length normalization
    ↓
BM25 score
    ↓
LexicalSearchRetriever
    ↓
UnifiedSearchService
    ↓
RRF

Responsibilities:

- tokenize search text
- build BM25 corpus statistics
- calculate document frequency
- calculate inverse document frequency
- calculate BM25 relevance
- rank documents by BM25 score

Does NOT:

- access database
- know about SearchIndex
- perform fuzzy search
- perform rank fusion
- normalize scores into 0.0-1.0
- interact with UI
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from math import log
import re
import unicodedata
from typing import Generic
from typing import Iterable
from typing import TypeVar


T = TypeVar(
    "T"
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class BM25Config:
    """
    BM25 configuration.

    k1:
        Controls term-frequency saturation.

        Larger values give repeated occurrences of a
        term more influence.

    b:
        Controls document-length normalization.

        0.0:
            no length normalization

        1.0:
            full length normalization
    """

    k1: float = 1.5

    b: float = 0.75

    def __post_init__(
        self,
    ) -> None:

        if not isfinite(
            self.k1
        ):

            raise ValueError(
                "BM25 k1 must be finite."
            )

        if self.k1 < 0.0:

            raise ValueError(
                "BM25 k1 cannot be negative."
            )

        if not isfinite(
            self.b
        ):

            raise ValueError(
                "BM25 b must be finite."
            )

        if not (
            0.0
            <= self.b
            <= 1.0
        ):

            raise ValueError(
                "BM25 b must be between "
                "0.0 and 1.0."
            )


# ==========================================================
# Corpus document
# ==========================================================


@dataclass(
    slots=True,
)
class BM25Document(
    Generic[T]
):
    """
    One document participating in BM25 ranking.

    payload may contain any external object, such as
    SearchIndex.
    """

    payload: T

    text: str

    tokens: tuple[str, ...]

    length: int


# ==========================================================
# Ranked result
# ==========================================================


@dataclass(
    slots=True,
)
class BM25Result(
    Generic[T]
):
    """
    One BM25-ranked result.
    """

    payload: T

    score: float

    rank: int

    matched_terms: tuple[str, ...]


# ==========================================================
# Service
# ==========================================================


class BM25SearchService:
    """
    Mathematical BM25 scoring engine.
    """

    def __init__(
        self,
        config: BM25Config | None = None,
    ) -> None:

        self.config = (
            config
            or BM25Config()
        )

    # ======================================================
    # Public ranking
    # ======================================================

    def rank(
        self,
        query: str,
        documents: Iterable[
            tuple[
                T,
                str,
            ]
        ],
    ) -> list[
        BM25Result[T]
    ]:
        """
        Rank arbitrary documents using BM25.

        documents:

            iterable of:

                (
                    payload,
                    searchable_text,
                )

        payload is returned untouched in BM25Result.
        """

        query_tokens = self.tokenize(
            query
        )

        if not query_tokens:

            return []

        corpus = self.build_corpus(
            documents
        )

        if not corpus:

            return []

        document_frequency = (
            self.calculate_document_frequency(
                corpus
            )
        )

        average_document_length = (
            self.calculate_average_document_length(
                corpus
            )
        )

        results: list[
            BM25Result[T]
        ] = []

        unique_query_terms = tuple(
            dict.fromkeys(
                query_tokens
            )
        )

        for document in corpus:

            score = self.score_document(
                query_tokens=(
                    query_tokens
                ),
                document_tokens=(
                    document.tokens
                ),
                document_frequency=(
                    document_frequency
                ),
                document_count=len(
                    corpus
                ),
                average_document_length=(
                    average_document_length
                ),
            )

            if score <= 0.0:

                continue

            token_set = set(
                document.tokens
            )

            matched_terms = tuple(
                term
                for term
                in unique_query_terms
                if term in token_set
            )

            results.append(
                BM25Result(
                    payload=(
                        document.payload
                    ),
                    score=score,
                    rank=0,
                    matched_terms=(
                        matched_terms
                    ),
                )
            )

        # Higher BM25 score is better.
        results.sort(
            key=lambda result: (
                -result.score,
                str(
                    getattr(
                        result.payload,
                        "id",
                        "",
                    )
                ),
            )
        )

        for rank, result in enumerate(
            results,
            start=1,
        ):

            result.rank = rank

        return results

    # ======================================================
    # Corpus
    # ======================================================

    def build_corpus(
        self,
        documents: Iterable[
            tuple[
                T,
                str,
            ]
        ],
    ) -> list[
        BM25Document[T]
    ]:
        """
        Convert external documents into BM25 documents.
        """

        corpus: list[
            BM25Document[T]
        ] = []

        for payload, text in documents:

            normalized_text = (
                text
                or ""
            )

            tokens = tuple(
                self.tokenize(
                    normalized_text
                )
            )

            corpus.append(
                BM25Document(
                    payload=payload,
                    text=normalized_text,
                    tokens=tokens,
                    length=len(
                        tokens
                    ),
                )
            )

        return corpus

    # ======================================================
    # Tokenization
    # ======================================================

    def tokenize(
        self,
        value: str | None,
    ) -> list[str]:
        """
        Normalize and tokenize investigation text.

        Preserves common identifier characters used in:

        - email addresses
        - usernames
        - domains
        - URLs
        - phone-like identifiers

        Examples:

            john@example.com
            user_name
            example-domain.com
    """

        if value is None:

            return []

        text = unicodedata.normalize(
            "NFKC",
            str(
                value
            ),
        )

        text = text.casefold()

        return re.findall(
            r"[\w@.+:/-]+",
            text,
            flags=re.UNICODE,
        )

    # ======================================================
    # Document frequency
    # ======================================================

    def calculate_document_frequency(
        self,
        corpus: Iterable[
            BM25Document[T]
        ],
    ) -> dict[
        str,
        int,
    ]:
        """
        Calculate number of documents containing
        each unique term.
        """

        frequencies: dict[
            str,
            int,
        ] = {}

        for document in corpus:

            unique_terms = set(
                document.tokens
            )

            for term in unique_terms:

                frequencies[
                    term
                ] = (
                    frequencies.get(
                        term,
                        0,
                    )
                    + 1
                )

        return frequencies

    # ======================================================
    # Average document length
    # ======================================================

    def calculate_average_document_length(
        self,
        corpus: Iterable[
            BM25Document[T]
        ],
    ) -> float:
        """
        Calculate average token count in corpus.
        """

        documents = list(
            corpus
        )

        if not documents:

            return 0.0

        total_length = sum(
            document.length
            for document
            in documents
        )

        return (
            total_length
            / len(
                documents
            )
        )

    # ======================================================
    # IDF
    # ======================================================

    def calculate_idf(
        self,
        *,
        document_count: int,
        document_frequency: int,
    ) -> float:
        """
        Calculate BM25 inverse document frequency.

        Uses:

            ln(
                1 +
                (
                    N - df + 0.5
                )
                /
                (
                    df + 0.5
                )
            )

        The +1 form keeps IDF positive.
        """

        if document_count < 1:

            return 0.0

        if document_frequency < 0:

            raise ValueError(
                "Document frequency cannot "
                "be negative."
            )

        if document_frequency > document_count:

            raise ValueError(
                "Document frequency cannot "
                "exceed document count."
            )

        numerator = (
            document_count
            - document_frequency
            + 0.5
        )

        denominator = (
            document_frequency
            + 0.5
        )

        return log(
            1.0
            + (
                numerator
                / denominator
            )
        )

    # ======================================================
    # Term frequency
    # ======================================================

    @staticmethod
    def calculate_term_frequency(
        term: str,
        document_tokens: Iterable[
            str
        ],
    ) -> int:
        """
        Count occurrences of one term.
        """

        return sum(
            1
            for token
            in document_tokens
            if token == term
        )

    # ======================================================
    # Document score
    # ======================================================

    def score_document(
        self,
        *,
        query_tokens: Iterable[
            str
        ],
        document_tokens: Iterable[
            str
        ],
        document_frequency: dict[
            str,
            int,
        ],
        document_count: int,
        average_document_length: float,
    ) -> float:
        """
        Calculate BM25 score for one document.
        """

        query_tokens = tuple(
            query_tokens
        )

        document_tokens = tuple(
            document_tokens
        )

        if (
            not query_tokens
            or not document_tokens
            or document_count < 1
        ):

            return 0.0

        document_length = len(
            document_tokens
        )

        # Avoid division by zero if the entire corpus
        # contains empty documents.
        effective_average_length = (
            average_document_length
            if average_document_length > 0.0
            else 1.0
        )

        score = 0.0

        # Repeating the same word in the user query
        # should not multiply its contribution.
        unique_query_terms = tuple(
            dict.fromkeys(
                query_tokens
            )
        )

        for term in unique_query_terms:

            term_frequency = (
                self.calculate_term_frequency(
                    term,
                    document_tokens,
                )
            )

            if term_frequency <= 0:

                continue

            df = document_frequency.get(
                term,
                0,
            )

            idf = self.calculate_idf(
                document_count=(
                    document_count
                ),
                document_frequency=df,
            )

            length_normalization = (
                1.0
                - self.config.b
                + (
                    self.config.b
                    * (
                        document_length
                        / effective_average_length
                    )
                )
            )

            numerator = (
                term_frequency
                * (
                    self.config.k1
                    + 1.0
                )
            )

            denominator = (
                term_frequency
                + (
                    self.config.k1
                    * length_normalization
                )
            )

            if denominator <= 0.0:

                continue

            score += (
                idf
                * (
                    numerator
                    / denominator
                )
            )

        return max(
            0.0,
            score,
        )
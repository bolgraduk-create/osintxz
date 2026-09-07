"""
Fuzzy search retriever.

Connects mathematical fuzzy string similarity with
the existing SearchIndex infrastructure.

Architecture:

InvestigationSearchQuery
        ↓
FuzzySearchRetriever
        ↓
SearchIndexRepository
        ↓
FuzzySearchService
    ├── Levenshtein
    ├── Jaro-Winkler
    └── Trigram similarity
        ↓
InvestigationSearchHit[]
        ↓
UnifiedSearchService
        ↓
RRF

Responsibilities:

- search SearchIndex objects inside one case
- generate useful text candidates from title/content
- calculate fuzzy similarity
- filter weak matches
- rank candidates
- convert matches into InvestigationSearchHit objects
- preserve detailed similarity signals

Does NOT:

- perform lexical substring search
- perform semantic/vector search
- perform rank fusion
- perform query transliteration
- perform entity resolution
- interact with UI
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from uuid import UUID

from app.investigation.search_query import (
    InvestigationSearchQuery,
    SearchMethod,
)

from app.investigation.search_result import (
    InvestigationSearchHit,
    SearchMatchReason,
    SearchScores,
)

from app.repositories.search_index_repository import (
    SearchIndexRepository,
)

from app.services.fuzzy_search_service import (
    FuzzySearchService,
    FuzzySimilarityResult,
)

from app.services.search_retriever import (
    SearchRetriever,
    SearchRetrieverInfo,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class FuzzySearchRetrieverConfig:
    """
    Runtime configuration for fuzzy retrieval.

    minimum_score:
        default minimum fuzzy similarity required
        for a candidate to enter the ranking.

    maximum_content_length:
        prevents expensive fuzzy comparison against
        arbitrarily large text bodies.

    maximum_content_candidates:
        limits the number of token/window candidates
        generated from one indexed object.

    maximum_window_tokens:
        largest token window compared against query.

    minimum_prefilter_candidates:
        minimum number of SearchIndex objects preserved
        after the cheap candidate prefilter.

    maximum_prefilter_candidates:
        normal upper bound for the cheap candidate
        prefilter. If query.candidate_limit itself is
        larger, it is always respected.

    prefilter_candidate_multiplier:
        expands the requested candidate_limit before the
        expensive fuzzy stage so the final threshold still
        has enough candidates to work with.

    prefilter_content_length:
        maximum amount of SearchIndex content inspected by
        the cheap prefilter. This does not change the text
        available to the final fuzzy matcher.
    """

    minimum_score: float = 0.62

    maximum_content_length: int = 12_000

    maximum_content_candidates: int = 250

    maximum_window_tokens: int = 5

    minimum_prefilter_candidates: int = 300

    maximum_prefilter_candidates: int = 600

    prefilter_candidate_multiplier: int = 4

    prefilter_content_length: int = 4_000

    def __post_init__(
        self,
    ) -> None:

        if not (
            0.0
            <= self.minimum_score
            <= 1.0
        ):

            raise ValueError(
                "minimum_score must be between "
                "0.0 and 1.0."
            )

        if (
            self.maximum_content_length
            < 1
        ):

            raise ValueError(
                "maximum_content_length must "
                "be at least 1."
            )

        if (
            self.maximum_content_candidates
            < 1
        ):

            raise ValueError(
                "maximum_content_candidates must "
                "be at least 1."
            )

        if (
            self.maximum_window_tokens
            < 1
        ):

            raise ValueError(
                "maximum_window_tokens must "
                "be at least 1."
            )

        if (
            self.minimum_prefilter_candidates
            < 1
        ):

            raise ValueError(
                "minimum_prefilter_candidates must "
                "be at least 1."
            )

        if (
            self.maximum_prefilter_candidates
            < self.minimum_prefilter_candidates
        ):

            raise ValueError(
                "maximum_prefilter_candidates must "
                "be greater than or equal to "
                "minimum_prefilter_candidates."
            )

        if (
            self.prefilter_candidate_multiplier
            < 1
        ):

            raise ValueError(
                "prefilter_candidate_multiplier must "
                "be at least 1."
            )

        if (
            self.prefilter_content_length
            < 1
        ):

            raise ValueError(
                "prefilter_content_length must "
                "be at least 1."
            )


# ==========================================================
# Internal match
# ==========================================================


@dataclass(
    slots=True,
)
class _FuzzyIndexMatch:
    """
    Internal fuzzy match representation.
    """

    index: object

    score: float

    field: str

    matched_text: str

    similarity: FuzzySimilarityResult


# ==========================================================
# Retriever
# ==========================================================


class FuzzySearchRetriever(
    SearchRetriever
):
    """
    Fuzzy retrieval over investigation SearchIndex objects.
    """

    def __init__(
        self,
        repository: SearchIndexRepository,
        fuzzy_search_service: FuzzySearchService
        | None = None,
        config: FuzzySearchRetrieverConfig
        | None = None,
    ) -> None:

        self.repository = repository

        self.fuzzy_search_service = (
            fuzzy_search_service
            or FuzzySearchService()
        )

        self.config = (
            config
            or FuzzySearchRetrieverConfig()
        )

        self._info = SearchRetrieverInfo(
            name="fuzzy",
            method=SearchMethod.FUZZY,
            description=(
                "Approximate fuzzy search over "
                "investigation indexes."
            ),
            enabled=True,
            priority=200,
        )

    # ==========================================================
    # Retriever information
    # ==========================================================

    @property
    def info(
        self,
    ) -> SearchRetrieverInfo:

        return self._info

    # ==========================================================
    # Query compatibility
    # ==========================================================

    def can_handle(
        self,
        query: InvestigationSearchQuery,
    ) -> bool:
        """
        Fuzzy retrieval currently works inside one case
        and requires textual input.
        """

        return (
            query.has_text_query
            and query.case_id is not None
        )

    # ==========================================================
    # Retrieval
    # ==========================================================

    def retrieve(
        self,
        query: InvestigationSearchQuery,
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Execute fuzzy retrieval.

        The expensive fuzzy algorithms are intentionally
        applied only after a cheap high-recall prefilter.

        This avoids running Levenshtein, Jaro-Winkler and
        trigram scoring across every SearchIndex object in
        a large investigation.
        """

        if not self.can_handle(
            query
        ):

            return []

        indexes = (
            self.repository.get_by_case(
                query.case_id
            )
        )

        indexes = self._filter_indexes(
            indexes,
            query,
        )

        indexes = self._prefilter_indexes(
            indexes=indexes,
            query=query.query,
            candidate_limit=(
                query.candidate_limit
            ),
        )

        matches: list[
            _FuzzyIndexMatch
        ] = []

        minimum_score = max(
            self.config.minimum_score,
            query.minimum_score,
        )

        for index in indexes:

            match = self._match_index(
                index,
                query.query,
            )

            if match is None:

                continue

            if (
                match.score
                < minimum_score
            ):

                continue

            matches.append(
                match
            )

        # Higher fuzzy similarity is better.
        matches.sort(
            key=lambda item: (
                -item.score,
                str(
                    item.index.object_id
                ),
            )
        )

        return [
            self._build_hit(
                match
            )
            for match in matches[
                :query.candidate_limit
            ]
        ]

    # ==========================================================
    # Cheap candidate prefilter
    # ==========================================================

    def _prefilter_indexes(
        self,
        *,
        indexes,
        query: str,
        candidate_limit: int,
    ):
        """
        Reduce the SearchIndex corpus before expensive
        mathematical fuzzy scoring.

        The prefilter is deliberately cheap and high-recall.
        It does not replace fuzzy similarity.

        Signals:

        - exact normalized substring
        - exact query-token coverage
        - character bigram coverage
        - character trigram coverage

        Only the best SearchIndex objects continue into
        _match_index(), where the full Levenshtein,
        Jaro-Winkler and trigram algorithms still run.
        """

        if not indexes:

            return []

        normalized_query = (
            self.fuzzy_search_service
            .normalize(
                query
            )
        )

        if not normalized_query:

            return []

        query_tokens = tuple(
            self._tokenize(
                normalized_query
            )
        )

        query_bigrams = (
            self._character_ngrams(
                normalized_query,
                size=2,
            )
        )

        query_trigrams = (
            self._character_ngrams(
                normalized_query,
                size=3,
            )
        )

        ranked = []

        for index in indexes:

            score = (
                self._prefilter_index_score(
                    index=index,
                    normalized_query=(
                        normalized_query
                    ),
                    query_tokens=(
                        query_tokens
                    ),
                    query_bigrams=(
                        query_bigrams
                    ),
                    query_trigrams=(
                        query_trigrams
                    ),
                )
            )

            ranked.append(
                (
                    score,
                    str(
                        index.object_id
                    ),
                    index,
                )
            )

        ranked.sort(
            key=lambda item: (
                -item[0],
                item[1],
            )
        )

        prefilter_limit = (
            self._prefilter_limit(
                requested_candidate_limit=(
                    candidate_limit
                ),
                available_count=len(
                    ranked
                ),
            )
        )

        return [
            item[2]
            for item
            in ranked[
                :prefilter_limit
            ]
        ]

    def _prefilter_limit(
        self,
        *,
        requested_candidate_limit: int,
        available_count: int,
    ) -> int:
        """
        Calculate how many SearchIndex objects should reach
        the expensive fuzzy stage.
        """

        expanded_limit = max(
            self.config
            .minimum_prefilter_candidates,
            (
                requested_candidate_limit
                * self.config
                .prefilter_candidate_multiplier
            ),
        )

        expanded_limit = min(
            self.config
            .maximum_prefilter_candidates,
            expanded_limit,
        )

        # Never preserve fewer candidates than the caller
        # explicitly requested.
        expanded_limit = max(
            requested_candidate_limit,
            expanded_limit,
        )

        return min(
            available_count,
            expanded_limit,
        )

    def _prefilter_index_score(
        self,
        *,
        index,
        normalized_query: str,
        query_tokens: tuple[str, ...],
        query_bigrams: set[str],
        query_trigrams: set[str],
    ) -> float:
        """
        Calculate a cheap relevance estimate for one
        SearchIndex.

        Title and content are evaluated independently so a
        short useful title is not diluted by a long body.
        """

        title = (
            index.title
            or ""
        )

        content = (
            index.content
            or ""
        )

        content = content[
            :self.config.prefilter_content_length
        ]

        normalized_title = (
            self.fuzzy_search_service
            .normalize(
                title
            )
        )

        normalized_content = (
            self.fuzzy_search_service
            .normalize(
                content
            )
        )

        title_score = (
            self._prefilter_text_score(
                text=normalized_title,
                normalized_query=(
                    normalized_query
                ),
                query_tokens=(
                    query_tokens
                ),
                query_bigrams=(
                    query_bigrams
                ),
                query_trigrams=(
                    query_trigrams
                ),
            )
        )

        content_score = (
            self._prefilter_text_score(
                text=normalized_content,
                normalized_query=(
                    normalized_query
                ),
                query_tokens=(
                    query_tokens
                ),
                query_bigrams=(
                    query_bigrams
                ),
                query_trigrams=(
                    query_trigrams
                ),
            )
        )

        return max(
            title_score,
            content_score,
        )

    def _prefilter_text_score(
        self,
        *,
        text: str,
        normalized_query: str,
        query_tokens: tuple[str, ...],
        query_bigrams: set[str],
        query_trigrams: set[str],
    ) -> float:
        """
        Cheap high-recall text score.

        Unlike final fuzzy similarity, this function never
        computes edit-distance matrices.
        """

        if not text:

            return 0.0

        if text == normalized_query:

            return 1.0

        if normalized_query in text:

            return 0.99

        token_coverage = (
            self._substring_coverage(
                needles=query_tokens,
                haystack=text,
            )
        )

        bigram_coverage = (
            self._substring_coverage(
                needles=query_bigrams,
                haystack=text,
            )
        )

        trigram_coverage = (
            self._substring_coverage(
                needles=query_trigrams,
                haystack=text,
            )
        )

        # Short queries have too few trigrams to make
        # trigram coverage stable, so bigrams carry more
        # weight there.
        if len(
            normalized_query
        ) <= 4:

            weighted = (
                0.70
                * bigram_coverage
                + 0.30
                * token_coverage
            )

            return max(
                weighted,
                bigram_coverage,
                0.90
                * token_coverage,
            )

        weighted = (
            0.55
            * trigram_coverage
            + 0.25
            * bigram_coverage
            + 0.20
            * token_coverage
        )

        return max(
            weighted,
            0.90
            * trigram_coverage,
            0.85
            * token_coverage,
        )

    @staticmethod
    def _substring_coverage(
        *,
        needles,
        haystack: str,
    ) -> float:
        """
        Fraction of query fragments that occur somewhere in
        the candidate text.

        This is intentionally asymmetric: the query is
        usually short while SearchIndex content may be much
        longer.
        """

        if not needles:

            return 0.0

        matched = sum(
            1
            for needle
            in needles
            if needle
            and needle in haystack
        )

        return (
            matched
            / len(
                needles
            )
        )

    @staticmethod
    def _character_ngrams(
        value: str,
        *,
        size: int,
    ) -> set[str]:
        """
        Build cheap character n-grams for candidate
        prefiltering.
        """

        if size < 1:

            raise ValueError(
                "size must be at least 1."
            )

        if not value:

            return set()

        if len(
            value
        ) <= size:

            return {
                value
            }

        return {
            value[
                index:
                index + size
            ]
            for index in range(
                len(
                    value
                )
                - size
                + 1
            )
        }

    # ==========================================================
    # Index filtering
    # ==========================================================

    def _filter_indexes(
        self,
        indexes,
        query: InvestigationSearchQuery,
    ):
        """
        Apply common Unified Search scope filters.
        """

        filtered = []

        allowed_types = {
            value
            .strip()
            .lower()

            for value
            in query.object_types

            if value
            and value.strip()
        }

        allowed_ids = set(
            query.object_ids
        )

        for index in indexes:

            # --------------------------------------------------
            # Deleted objects
            # --------------------------------------------------

            if (
                not query.include_deleted
                and getattr(
                    index,
                    "deleted_at",
                    None,
                )
                is not None
            ):

                continue

            # --------------------------------------------------
            # Object type
            # --------------------------------------------------

            object_type = (
                index.object_type.value
                if hasattr(
                    index.object_type,
                    "value",
                )
                else str(
                    index.object_type
                )
            )

            object_type = (
                object_type
                .strip()
                .lower()
            )

            if (
                allowed_types
                and object_type
                not in allowed_types
            ):

                continue

            # --------------------------------------------------
            # Explicit IDs
            # --------------------------------------------------

            if (
                allowed_ids
                and index.object_id
                not in allowed_ids
            ):

                continue

            filtered.append(
                index
            )

        return filtered

    # ==========================================================
    # Index comparison
    # ==========================================================

    def _match_index(
        self,
        index,
        query: str,
    ) -> _FuzzyIndexMatch | None:
        """
        Find the strongest fuzzy match inside one
        SearchIndex.

        Important:

        We do not compare a short query against an entire
        long document as one string.

        Instead we evaluate:

        - title
        - content tokens
        - token windows
        - short complete content when appropriate
        """

        best_match: (
            _FuzzyIndexMatch
            | None
        ) = None

        # ------------------------------------------------------
        # Title
        # ------------------------------------------------------

        title = (
            index.title
            or ""
        )

        if title:

            similarity = (
                self.fuzzy_search_service
                .compare(
                    query,
                    title,
                )
            )

            best_match = (
                _FuzzyIndexMatch(
                    index=index,
                    score=(
                        similarity.combined
                    ),
                    field="title",
                    matched_text=title,
                    similarity=similarity,
                )
            )

        # ------------------------------------------------------
        # Content candidates
        # ------------------------------------------------------

        content = (
            index.content
            or ""
        )

        if content:

            for candidate in (
                self._build_content_candidates(
                    content,
                    query,
                )
            ):

                similarity = (
                    self.fuzzy_search_service
                    .compare(
                        query,
                        candidate,
                    )
                )

                if (
                    best_match is None
                    or similarity.combined
                    > best_match.score
                ):

                    best_match = (
                        _FuzzyIndexMatch(
                            index=index,
                            score=(
                                similarity
                                .combined
                            ),
                            field="content",
                            matched_text=(
                                candidate
                            ),
                            similarity=(
                                similarity
                            ),
                        )
                    )

                    # Exact normalized match cannot
                    # be improved further.
                    if (
                        similarity.combined
                        >= 1.0
                    ):

                        break

        return best_match

    # ==========================================================
    # Content candidate generation
    # ==========================================================

    def _build_content_candidates(
        self,
        content: str,
        query: str,
    ) -> list[str]:
        """
        Produce fuzzy-comparable fragments from content.

        Example content:

            John Alexander Petroff uses
            john.petrov@example.com

        query:

            John Petrov

        Candidate windows include:

            John
            Alexander
            Petroff
            John Alexander
            Alexander Petroff
            John Alexander Petroff
            john.petrov@example.com

        This is much more meaningful than comparing
        "John Petrov" against the entire document.
        """

        content = content[
            :self.config.maximum_content_length
        ]

        normalized_query = (
            self.fuzzy_search_service
            .normalize(
                query
            )
        )

        query_tokens = self._tokenize(
            normalized_query
        )

        content_tokens = self._tokenize(
            content
        )

        if not content_tokens:

            return []

        candidates: list[str] = []

        seen: set[str] = set()

        # ------------------------------------------------------
        # Short complete content
        # ------------------------------------------------------

        if len(
            content_tokens
        ) <= self.config.maximum_window_tokens:

            self._add_candidate(
                candidates,
                seen,
                " ".join(
                    content_tokens
                ),
            )

        # ------------------------------------------------------
        # Determine useful window range
        # ------------------------------------------------------

        query_token_count = max(
            1,
            len(
                query_tokens
            ),
        )

        minimum_window = max(
            1,
            query_token_count
            - 1,
        )

        maximum_window = min(
            self.config.maximum_window_tokens,
            query_token_count
            + 1,
        )

        # Single-token candidates remain important for:
        #
        # usernames
        # emails
        # surnames
        # domains
        # identifiers

        window_sizes = {
            1,
        }

        window_sizes.update(
            range(
                minimum_window,
                maximum_window + 1,
            )
        )

        # ------------------------------------------------------
        # Sliding token windows
        # ------------------------------------------------------

        for window_size in sorted(
            window_sizes
        ):

            if (
                window_size
                > len(
                    content_tokens
                )
            ):

                continue

            for start in range(
                len(
                    content_tokens
                )
                - window_size
                + 1
            ):

                candidate = " ".join(
                    content_tokens[
                        start:
                        start + window_size
                    ]
                )

                self._add_candidate(
                    candidates,
                    seen,
                    candidate,
                )

                if (
                    len(
                        candidates
                    )
                    >= self.config
                    .maximum_content_candidates
                ):

                    return candidates

        return candidates

    # ==========================================================
    # Tokenization
    # ==========================================================

    def _tokenize(
        self,
        value: str,
    ) -> list[str]:
        """
        Extract investigation-friendly text tokens.

        Punctuation useful for identifiers is preserved:

            john@example.com
            user_name
            example-domain.com
            +380501234567
        """

        normalized = (
            self.fuzzy_search_service
            .normalize(
                value
            )
        )

        if not normalized:

            return []

        return re.findall(
            r"[\w@.+:/-]+",
            normalized,
            flags=re.UNICODE,
        )

    # ==========================================================
    # Candidate helper
    # ==========================================================

    @staticmethod
    def _add_candidate(
        candidates: list[str],
        seen: set[str],
        candidate: str,
    ) -> None:
        """
        Add unique non-empty comparison candidate.
        """

        candidate = (
            candidate.strip()
        )

        if not candidate:

            return

        if candidate in seen:

            return

        seen.add(
            candidate
        )

        candidates.append(
            candidate
        )

    # ==========================================================
    # Unified hit conversion
    # ==========================================================

    def _build_hit(
        self,
        match: _FuzzyIndexMatch,
    ) -> InvestigationSearchHit:
        """
        Convert fuzzy match into common search result.
        """

        index = match.index

        object_type = (
            index.object_type.value
            if hasattr(
                index.object_type,
                "value",
            )
            else str(
                index.object_type
            )
        )

        similarity = (
            match.similarity
        )

        hit = InvestigationSearchHit(
            object_id=index.object_id,
            object_type=object_type,
            case_id=index.case_id,
            title=(
                index.title
                or ""
            ),
            snippet=(
                self._build_snippet(
                    index=index,
                    match=match,
                )
            ),
            scores=SearchScores(
                fuzzy=match.score,
            ),
            matched_methods=[
                SearchMethod.FUZZY,
            ],
            source=index,
            metadata={
                "search_index_id": str(
                    index.id
                ),
                "fuzzy_field": (
                    match.field
                ),
                "fuzzy_matched_text": (
                    match.matched_text
                ),
                "fuzzy_levenshtein": (
                    similarity.levenshtein
                ),
                "fuzzy_jaro_winkler": (
                    similarity.jaro_winkler
                ),
                "fuzzy_trigram": (
                    similarity.trigram
                ),
            },
        )

        hit.add_reason(
            SearchMatchReason(
                reason=(
                    self._build_reason(
                        match
                    )
                ),
                method=SearchMethod.FUZZY,
                score=match.score,
                details={
                    "field": (
                        match.field
                    ),
                    "matched_text": (
                        match.matched_text
                    ),
                    "levenshtein": (
                        similarity
                        .levenshtein
                    ),
                    "jaro_winkler": (
                        similarity
                        .jaro_winkler
                    ),
                    "trigram": (
                        similarity
                        .trigram
                    ),
                    "exact": (
                        similarity.exact
                    ),
                },
            )
        )

        return hit

    # ==========================================================
    # Explanation
    # ==========================================================

    @staticmethod
    def _build_reason(
        match: _FuzzyIndexMatch,
    ) -> str:
        """
        Build readable fuzzy match explanation.
        """

        similarity = (
            match.similarity
        )

        if similarity.exact:

            return (
                "Exact normalized fuzzy match "
                f"in {match.field}."
            )

        if (
            similarity.jaro_winkler
            >= 0.90
        ):

            return (
                "Very similar text found "
                f"in {match.field}."
            )

        if (
            similarity.combined
            >= 0.80
        ):

            return (
                "Strong fuzzy similarity "
                f"in {match.field}."
            )

        return (
            "Approximate text similarity "
            f"in {match.field}."
        )

    # ==========================================================
    # Snippet
    # ==========================================================

    def _build_snippet(
        self,
        *,
        index,
        match: _FuzzyIndexMatch,
    ) -> str:
        """
        Build compact display snippet.
        """

        if match.field == "title":

            content = (
                index.content
                or ""
            )

            if content:

                return (
                    content[
                        :220
                    ]
                    .strip()
                )

            return (
                index.title
                or ""
            )

        matched_text = (
            match.matched_text
        )

        content = (
            index.content
            or ""
        )

        if not content:

            return matched_text

        normalized_content = (
            self.fuzzy_search_service
            .normalize(
                content
            )
        )

        normalized_match = (
            self.fuzzy_search_service
            .normalize(
                matched_text
            )
        )

        position = (
            normalized_content.find(
                normalized_match
            )
        )

        if position < 0:

            return matched_text

        context_size = 100

        start = max(
            0,
            position
            - context_size,
        )

        end = min(
            len(
                content
            ),
            position
            + len(
                matched_text
            )
            + context_size,
        )

        snippet = (
            content[
                start:end
            ]
            .strip()
        )

        if start > 0:

            snippet = (
                "..."
                + snippet
            )

        if end < len(
            content
        ):

            snippet = (
                snippet
                + "..."
            )

        return snippet
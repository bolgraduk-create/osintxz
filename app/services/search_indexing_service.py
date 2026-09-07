"""
Unified search indexing orchestration.

Keeps searchable representations synchronized across
lexical, fuzzy and semantic search infrastructure.

Architecture:

Domain object
    ↓
SearchIndexingService
    ↓
SearchIndexBuilder
    ↓
SearchIndex
    ↓
optional SearchEmbeddingIndexer
    ↓
SearchEmbedding / pgvector

Responsibilities:

- index one domain object
- support lightweight text-only indexing
- index several domain objects
- reindex existing objects
- backfill an entire case
- keep SearchIndex and SearchEmbedding synchronized
- isolate embedding failures from textual indexing
- expose one indexing API to the application layer

Does NOT:

- perform retrieval
- perform BM25
- perform fuzzy matching
- perform semantic similarity search
- perform rank fusion
- interact with UI
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from app.models.search_index import (
    SearchIndex,
)

from app.repositories.search_index_repository import (
    SearchIndexRepository,
)

from app.services.search_embedding_indexer import (
    SearchEmbeddingIndexer,
    SearchEmbeddingIndexResult,
)

from app.services.search_index_builder import (
    SearchIndexBuildResult,
    SearchIndexBuilder,
)

from app.repositories.search_embedding_repository import (
    SearchEmbeddingRepository,
)


@dataclass(
    slots=True,
)
class SearchObjectIndexingResult:
    """
    Result of indexing one domain object.
    """

    text_indexed: bool = False

    embedding_indexed: bool = False

    embedding_requested: bool = False

    skipped: bool = False

    embedding_failed: bool = False


@dataclass(
    slots=True,
)
class SearchCaseIndexingResult:
    """
    Combined result of complete case indexing.
    """

    search_indexes: SearchIndexBuildResult

    embeddings: SearchEmbeddingIndexResult

    @property
    def successful(
        self,
    ) -> bool:

        return (
            self.search_indexes.failed == 0
            and self.embeddings.failed == 0
        )


    @dataclass(
    slots=True,
    )
    class SearchObjectRemovalResult:
        """
        Result of removing one object from search.
        """

        found: bool = False

        embeddings_deleted: int = 0

        search_indexes_deleted: int = 0

    @property
    def removed(
        self,
    ) -> bool:

        return (
            self.embeddings_deleted > 0
            or self.search_indexes_deleted > 0
        )


class SearchIndexingService:
    """
    Unified indexing facade for investigation search.
    """

    def __init__(
        self,
        *,
        search_index_builder: SearchIndexBuilder,
        search_index_repository: SearchIndexRepository,
        search_embedding_repository: SearchEmbeddingRepository,
        search_embedding_indexer: SearchEmbeddingIndexer,
    ) -> None:

        self.search_index_builder = (
            search_index_builder
        )

        self.search_index_repository = (
            search_index_repository
        )

        self.search_embedding_repository = (
            search_embedding_repository
        )

        self.search_embedding_indexer = (
            search_embedding_indexer
        )

    # ======================================================
    # One object
    # ======================================================

    def index_object(
        self,
        obj: object,
        *,
        include_embedding: bool = True,
        force_embedding: bool = False,
    ) -> SearchObjectIndexingResult:
        """
        Index one domain object.

        Flow:

            domain object
                ↓
            SearchIndexBuilder
                ↓
            SearchIndex
                ↓
            optional SearchEmbeddingIndexer

        If include_embedding=False:

            SearchIndex is updated immediately,
            existing semantic embedding is removed
            because it may now be stale.

        A fresh embedding can later be generated
        through batch indexing.
        """

        result = (
            SearchObjectIndexingResult(
                embedding_requested=(
                    include_embedding
                ),
            )
        )

        # --------------------------------------------------
        # Build / update SearchIndex
        # --------------------------------------------------

        status = (
            self.search_index_builder
            .build_object(
                obj
            )
        )

        if status == "skipped":

            result.skipped = True

            return result

        result.text_indexed = True

        # --------------------------------------------------
        # Resolve domain object identity
        # --------------------------------------------------

        search_document = (
            self.search_index_builder
            .to_search_document(
                obj
            )
        )

        if search_document is None:

            result.skipped = True

            return result

        # --------------------------------------------------
        # Load resulting SearchIndex
        # --------------------------------------------------

        search_index = (
            self.search_index_repository
            .get_by_object(
                search_document.object_type,
                search_document.object_id,
            )
        )

        if search_index is None:

            raise RuntimeError(
                "SearchIndexBuilder completed, "
                "but SearchIndex could not be loaded."
            )

        # --------------------------------------------------
        # Text-only mode
        #
        # SearchIndex already contains the current text.
        #
        # An existing embedding may represent the old text,
        # therefore it must be invalidated.
        # --------------------------------------------------

        if not include_embedding:

            self.search_embedding_repository \
                .delete_for_search_index(
                    search_index_id=(
                        search_index.id
                    ),
                )

            return result

        # --------------------------------------------------
        # Semantic indexing
        # --------------------------------------------------

        try:

            embedding_written = (
                self.search_embedding_indexer
                .index_one(
                    search_index,
                    force=(
                        force_embedding
                    ),
                )
            )

            result.embedding_indexed = (
                embedding_written
            )

        except Exception:

            # Lexical / fuzzy indexing must remain usable
            # even when the embedding provider is unavailable.
            result.embedding_failed = True

        return result

    # ======================================================
    # Text-only indexing
    # ======================================================

    def index_object_text_only(
        self,
        obj: object,
    ) -> SearchObjectIndexingResult:
        """
        Update SearchIndex without generating embedding.

        Preferred for high-volume ingestion.
        """

        return self.index_object(
            obj,
            include_embedding=False,
        )

    # ======================================================
    # Reindex one object
    # ======================================================

    def reindex_object(
        self,
        obj: object,
    ) -> SearchObjectIndexingResult:
        """
        Refresh textual and semantic representations.
        """

        return self.index_object(
            obj,
            include_embedding=True,
            force_embedding=True,
        )

    # ======================================================
    # Multiple objects
    # ======================================================

    def index_objects(
        self,
        objects: Iterable[
            object
        ],
        *,
        include_embeddings: bool = True,
        force_embeddings: bool = False,
    ) -> list[
        SearchObjectIndexingResult
    ]:

        results: list[
            SearchObjectIndexingResult
        ] = []

        for obj in objects:

            try:

                result = self.index_object(
                    obj,
                    include_embedding=(
                        include_embeddings
                    ),
                    force_embedding=(
                        force_embeddings
                    ),
                )

            except Exception:

                result = (
                    SearchObjectIndexingResult(
                        embedding_requested=(
                            include_embeddings
                        ),
                        embedding_failed=(
                            include_embeddings
                        ),
                    )
                )

            results.append(
                result
            )

        return results

    # ======================================================
    # Text-only bulk indexing
    # ======================================================

    def index_objects_text_only(
        self,
        objects: Iterable[
            object
        ],
    ) -> list[
        SearchObjectIndexingResult
    ]:
        """
        Build SearchIndex rows without embeddings.
        """

        return self.index_objects(
            objects,
            include_embeddings=False,
        )

    # ======================================================
    # Complete case
    # ======================================================

    def index_case(
        self,
        case_id: UUID,
        *,
        force_embeddings: bool = False,
    ) -> SearchCaseIndexingResult:
        """
        Build textual indexes and batch semantic
        embeddings for a complete case.
        """

        search_result = (
            self.search_index_builder
            .build_case(
                case_id
            )
        )

        embedding_result = (
            self.search_embedding_indexer
            .index_case(
                case_id,
                force=(
                    force_embeddings
                ),
            )
        )

        return SearchCaseIndexingResult(
            search_indexes=(
                search_result
            ),
            embeddings=(
                embedding_result
            ),
        )

    # ======================================================
    # Semantic-only refresh
    # ======================================================

    def rebuild_embeddings(
        self,
        case_id: UUID,
    ) -> SearchEmbeddingIndexResult:

        return (
            self.search_embedding_indexer
            .index_case(
                case_id,
                force=True,
            )
        )

        # ======================================================
    # Remove object
    # ======================================================

    def remove_object(
        self,
        obj: object,
    ) -> SearchObjectRemovalResult:
        """
        Remove one domain object from all search
        representations.

        Order is important:

        SearchEmbedding
            ↓
        SearchIndex

        Domain data itself is never deleted here.
        """

        result = (
            SearchObjectRemovalResult()
        )

        document = (
            self.search_index_builder
            .to_search_document(
                obj
            )
        )

        if document is None:

            return result

        search_index = (
            self.search_index_repository
            .get_by_object(
                document.object_type,
                document.object_id,
            )
        )

        if search_index is None:

            return result

        result.found = True

        result.embeddings_deleted = (
            self.search_embedding_repository
            .delete_for_search_index(
                search_index_id=(
                    search_index.id
                ),
            )
        )

        result.search_indexes_deleted = (
            self.search_index_repository
            .delete_by_object(
                object_type=(
                    document.object_type
                ),
                object_id=(
                    document.object_id
                ),
            )
        )

        return result

    # ======================================================
    # SearchIndex helper
    # ======================================================

    def get_search_index(
        self,
        obj: object,
    ) -> SearchIndex | None:

        document = (
            self.search_index_builder
            .to_search_document(
                obj
            )
        )

        if document is None:

            return None

        return (
            self.search_index_repository
            .get_by_object(
                document.object_type,
                document.object_id,
            )
        )
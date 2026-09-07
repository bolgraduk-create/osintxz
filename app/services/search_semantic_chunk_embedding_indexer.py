"""
Search semantic chunk embedding indexer.

Generates and maintains vector embeddings for
SearchSemanticChunk objects.

Architecture:

SearchSemanticChunk[]
        ↓
existing lightweight embedding state
        ↓
new / stale chunk selection
        ↓
batching
        ↓
OllamaEmbeddingService.embed_many()
        ↓
SearchSemanticChunkEmbedding
        ↓
pgvector

Primary goals:

- avoid one Ollama request per chunk
- avoid loading existing vectors during stale detection
- skip unchanged chunks
- update stale embeddings
- support efficient incremental indexing

Does NOT:

- build message chunks
- perform semantic retrieval
- perform rank fusion
- commit transactions
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from app.models.search_semantic_chunk import (
    SearchSemanticChunk,
)

from app.models.search_semantic_chunk_embedding import (
    SearchSemanticChunkEmbedding,
)

from app.repositories.search_semantic_chunk_repository import (
    SearchSemanticChunkRepository,
)

from app.repositories.search_semantic_chunk_embedding_repository import (
    SearchSemanticChunkEmbeddingRepository,
)

from app.services.ollama_embedding_service import (
    OllamaEmbeddingService,
)


# ==========================================================
# Configuration
# ==========================================================

@dataclass(
    frozen=True,
    slots=True,
)
class SearchSemanticChunkEmbeddingIndexerConfig:
    """
    Semantic chunk embedding indexing configuration.

    batch_size:
        Number of chunk texts sent to Ollama in one
        embed_many() request.

    flush_every_batches:
        Flush SQLAlchemy changes after this many batches.

        This does NOT commit the transaction.
    """

    batch_size: int = 32

    flush_every_batches: int = 5

    def __post_init__(
        self,
    ) -> None:

        if self.batch_size < 1:

            raise ValueError(
                "batch_size must be at least 1."
            )

        if self.flush_every_batches < 1:

            raise ValueError(
                "flush_every_batches must be at least 1."
            )


# ==========================================================
# Result
# ==========================================================

@dataclass(
    slots=True,
)
class SearchSemanticChunkEmbeddingIndexResult:
    """
    Result of semantic chunk embedding indexing.
    """

    processed: int = 0

    eligible: int = 0

    already_current: int = 0

    embedded: int = 0

    created: int = 0

    updated: int = 0

    failed: int = 0

    batches: int = 0

    elapsed_seconds: float = 0.0

    @property
    def successful(
        self,
    ) -> bool:

        return (
            self.failed == 0
        )

    @property
    def changed(
        self,
    ) -> int:

        return (
            self.created
            + self.updated
        )


# ==========================================================
# Internal candidate
# ==========================================================

@dataclass(
    frozen=True,
    slots=True,
)
class _EmbeddingCandidate:
    """
    Chunk requiring embedding generation.
    """

    chunk: SearchSemanticChunk

    exists: bool


# ==========================================================
# Indexer
# ==========================================================

class SearchSemanticChunkEmbeddingIndexer:
    """
    Bulk embedding indexer for semantic chunks.
    """

    def __init__(
        self,
        *,
        chunk_repository: (
            SearchSemanticChunkRepository
        ),
        embedding_repository: (
            SearchSemanticChunkEmbeddingRepository
        ),
        embedding_service: (
            OllamaEmbeddingService
        ),
        config: (
            SearchSemanticChunkEmbeddingIndexerConfig
            | None
        ) = None,
    ) -> None:

        self.chunk_repository = (
            chunk_repository
        )

        self.embedding_repository = (
            embedding_repository
        )

        self.embedding_service = (
            embedding_service
        )

        self.config = (
            config
            or SearchSemanticChunkEmbeddingIndexerConfig()
        )

    # ======================================================
    # Public API
    # ======================================================

    def index_case(
        self,
        case_id: UUID,
    ) -> SearchSemanticChunkEmbeddingIndexResult:
        """
        Generate missing or stale embeddings for one case.

        Existing current embeddings are skipped without
        loading vector data.

        Transaction commit is intentionally left to the
        caller.
        """

        started = perf_counter()

        result = (
            SearchSemanticChunkEmbeddingIndexResult()
        )

        # --------------------------------------------------
        # Load chunks
        # --------------------------------------------------

        chunks = (
            self.chunk_repository
            .get_by_case(
                case_id
            )
        )

        result.processed = len(
            chunks
        )

        if not chunks:

            result.elapsed_seconds = (
                perf_counter()
                - started
            )

            return result

        # --------------------------------------------------
        # Model
        # --------------------------------------------------

        model_name = (
            self._get_model_name()
        )

        # --------------------------------------------------
        # Lightweight existing state
        # --------------------------------------------------

        states = (
            self.embedding_repository
            .get_states_by_case(
                case_id=case_id,
                model=model_name,
            )
        )

        # --------------------------------------------------
        # Determine candidates
        # --------------------------------------------------

        candidates: list[
            _EmbeddingCandidate
        ] = []

        for chunk in chunks:

            state = states.get(
                chunk.id
            )

            if state is None:

                candidates.append(
                    _EmbeddingCandidate(
                        chunk=chunk,
                        exists=False,
                    )
                )

                continue

            if (
                state.content_hash
                == chunk.content_hash
            ):

                result.already_current += 1

                continue

            candidates.append(
                _EmbeddingCandidate(
                    chunk=chunk,
                    exists=True,
                )
            )

        result.eligible = len(
            candidates
        )

        # --------------------------------------------------
        # Nothing to do
        # --------------------------------------------------

        if not candidates:

            result.elapsed_seconds = (
                perf_counter()
                - started
            )

            return result

        # --------------------------------------------------
        # Process batches
        # --------------------------------------------------

        for batch_number, start_index in enumerate(
            range(
                0,
                len(candidates),
                self.config.batch_size,
            ),
            start=1,
        ):

            batch = candidates[
                start_index:
                start_index
                + self.config.batch_size
            ]

            self._process_batch(
                batch=batch,
                model_name=model_name,
                result=result,
            )

            result.batches += 1

            if (
                batch_number
                % self.config.flush_every_batches
                == 0
            ):

                self.embedding_repository.session.flush()

        # --------------------------------------------------
        # Final flush
        # --------------------------------------------------

        self.embedding_repository.session.flush()

        result.elapsed_seconds = (
            perf_counter()
            - started
        )

        return result

    # ======================================================
    # Batch
    # ======================================================

    def _process_batch(
        self,
        *,
        batch: list[_EmbeddingCandidate],
        model_name: str,
        result: SearchSemanticChunkEmbeddingIndexResult,
    ) -> None:
        """
        Generate and persist one embedding batch.

        If the bulk Ollama request itself fails, the whole
        batch is counted as failed.

        Persistence failures are isolated per chunk.
        """

        if not batch:

            return

        texts = [
            candidate.chunk.text
            for candidate in batch
        ]

        # --------------------------------------------------
        # Ollama bulk request
        # --------------------------------------------------

        try:

            embedding_results = (
                self.embedding_service
                .embed_many(
                    texts
                )
            )

        except Exception:

            result.failed += len(
                batch
            )

            return

        # --------------------------------------------------
        # Validate response size
        # --------------------------------------------------

        if (
            len(embedding_results)
            != len(batch)
        ):

            result.failed += len(
                batch
            )

            return

        # --------------------------------------------------
        # Persist results
        # --------------------------------------------------

        for candidate, embedding_result in zip(
            batch,
            embedding_results,
        ):

            try:

                self._persist_embedding(
                    candidate=candidate,
                    embedding_result=embedding_result,
                    model_name=model_name,
                    result=result,
                )

                result.embedded += 1

            except Exception:

                result.failed += 1

    # ======================================================
    # Persistence
    # ======================================================

    def _persist_embedding(
        self,
        *,
        candidate: _EmbeddingCandidate,
        embedding_result,
        model_name: str,
        result: SearchSemanticChunkEmbeddingIndexResult,
    ) -> None:
        """
        Create or update one chunk embedding.
        """

        chunk = (
            candidate.chunk
        )

        vector = list(
            embedding_result.vector
        )

        dimensions = int(
            embedding_result.dimensions
        )

        if not vector:

            raise ValueError(
                "Embedding vector cannot be empty."
            )

        if (
            len(vector)
            != dimensions
        ):

            raise ValueError(
                "Embedding vector length does not "
                "match dimensions metadata."
            )

        # Current database column is Vector(768).
        if dimensions != 768:

            raise ValueError(
                "Semantic chunk embedding dimensions "
                f"must be 768, received {dimensions}."
            )

        # --------------------------------------------------
        # Create
        # --------------------------------------------------

        if not candidate.exists:

            embedding = (
                SearchSemanticChunkEmbedding(
                    case_id=chunk.case_id,
                    chunk_id=chunk.id,
                    content_hash=(
                        chunk.content_hash
                    ),
                    model=model_name,
                    dimensions=dimensions,
                    embedding=vector,
                )
            )

            self.embedding_repository.create(
                embedding
            )

            result.created += 1

            return

        # --------------------------------------------------
        # Update stale
        # --------------------------------------------------

        existing = (
            self.embedding_repository
            .get_by_chunk(
                chunk_id=chunk.id,
                model=model_name,
            )
        )

        if existing is None:
            # Defensive fallback.
            #
            # State existed during candidate selection but
            # disappeared before persistence.

            embedding = (
                SearchSemanticChunkEmbedding(
                    case_id=chunk.case_id,
                    chunk_id=chunk.id,
                    content_hash=(
                        chunk.content_hash
                    ),
                    model=model_name,
                    dimensions=dimensions,
                    embedding=vector,
                )
            )

            self.embedding_repository.create(
                embedding
            )

            result.created += 1

            return

        existing.content_hash = (
            chunk.content_hash
        )

        existing.dimensions = (
            dimensions
        )

        existing.embedding = (
            vector
        )

        self.embedding_repository.update(
            existing
        )

        result.updated += 1

    # ======================================================
    # Model helper
    # ======================================================

    def _get_model_name(
        self,
    ) -> str:
        """
        Return normalized embedding model name.
        """

        model_name = getattr(
            self.embedding_service,
            "model_name",
            None,
        )

        if model_name is None:

            model_name = getattr(
                self.embedding_service,
                "model",
                None,
            )

        if model_name is None:

            raise RuntimeError(
                "Embedding service does not expose "
                "model_name or model."
            )

        normalized = str(
            model_name
        ).strip()

        if not normalized:

            raise RuntimeError(
                "Embedding model name cannot be empty."
            )

        return normalized
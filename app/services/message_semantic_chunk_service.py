"""
Message semantic chunk persistence service.

Synchronizes Message-derived semantic chunks with
SearchSemanticChunk storage.

Architecture:

Message[]
    ↓
MessageSemanticChunkBuilder
    ↓
SemanticChunkDraft[]
    ↓
MessageSemanticChunkService
    ↓
SearchSemanticChunkRepository

Responsibilities:

- build chunks for one case
- create new chunks
- update changed chunks
- skip unchanged chunks
- remove stale chunks
- preserve deterministic chunk identity

Does NOT:

- generate embeddings
- perform vector search
- perform rank fusion
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.models.search_semantic_chunk import (
    SearchSemanticChunk,
)

from app.repositories.message_repository import (
    MessageRepository,
)

from app.repositories.search_semantic_chunk_repository import (
    SearchSemanticChunkRepository,
)

from app.services.message_semantic_chunk_builder import (
    MessageSemanticChunkBuilder,
    SemanticChunkDraft,
)


@dataclass(
    slots=True,
)
class MessageSemanticChunkSyncResult:
    """
    Result of one case chunk synchronization.
    """

    messages: int = 0

    drafts: int = 0

    created: int = 0

    updated: int = 0

    skipped: int = 0

    deleted: int = 0

    failed: int = 0

    @property
    def successful(
        self,
    ) -> bool:

        return (
            self.failed == 0
        )


class MessageSemanticChunkService:
    """
    Synchronizes persisted semantic chunks with
    current Message data.
    """

    def __init__(
        self,
        *,
        message_repository: MessageRepository,
        chunk_repository: SearchSemanticChunkRepository,
        chunk_builder: MessageSemanticChunkBuilder,
    ) -> None:

        self.message_repository = (
            message_repository
        )

        self.chunk_repository = (
            chunk_repository
        )

        self.chunk_builder = (
            chunk_builder
        )

    # ======================================================
    # Case synchronization
    # ======================================================

    def sync_case(
        self,
        case_id: UUID,
    ) -> MessageSemanticChunkSyncResult:
        """
        Reconcile semantic chunks for one case.

        Existing unchanged chunks are preserved.

        Changed chunks are updated.

        Chunks that no longer exist according to the
        current deterministic build are removed.
        """

        result = (
            MessageSemanticChunkSyncResult()
        )

        # --------------------------------------------------
        # Messages
        # --------------------------------------------------

        messages = (
            self.message_repository
            .get_by_case(
                case_id
            )
        )

        result.messages = len(
            messages
        )

        # --------------------------------------------------
        # Build drafts
        # --------------------------------------------------

        drafts = (
            self.chunk_builder.build(
                messages
            )
        )

        result.drafts = len(
            drafts
        )

        # --------------------------------------------------
        # Existing chunks
        # --------------------------------------------------

        existing_chunks = (
            self.chunk_repository
            .get_by_case(
                case_id
            )
        )

        existing_by_key = {
            chunk.chunk_key: chunk
            for chunk
            in existing_chunks
        }

        current_keys: set[str] = (
            set()
        )

        # --------------------------------------------------
        # Create / update
        # --------------------------------------------------

        for draft in drafts:

            current_keys.add(
                draft.chunk_key
            )

            existing = (
                existing_by_key.get(
                    draft.chunk_key
                )
            )

            if existing is None:

                try:

                    chunk = (
                        self._create_chunk(
                            draft
                        )
                    )

                    self.chunk_repository.create(
                        chunk
                    )

                    result.created += 1

                except Exception:

                    result.failed += 1

                continue

            # --------------------------------------------------
            # Unchanged
            # --------------------------------------------------

            if (
                existing.content_hash
                == draft.content_hash
            ):

                result.skipped += 1

                continue

            # --------------------------------------------------
            # Changed
            # --------------------------------------------------

            try:

                self._apply_draft(
                    existing,
                    draft,
                )

                self.chunk_repository.update(
                    existing
                )

                result.updated += 1

            except Exception:

                result.failed += 1

        # --------------------------------------------------
        # Delete stale chunks
        # --------------------------------------------------

        for chunk in existing_chunks:

            if (
                chunk.chunk_key
                in current_keys
            ):

                continue

            try:

                self.chunk_repository.delete(
                    chunk
                )

                result.deleted += 1

            except Exception:

                result.failed += 1

        return result

    # ======================================================
    # Create helper
    # ======================================================

    @staticmethod
    def _create_chunk(
        draft: SemanticChunkDraft,
    ) -> SearchSemanticChunk:
        """
        Create ORM chunk from draft.
        """

        return SearchSemanticChunk(
            case_id=draft.case_id,
            source_id=draft.source_id,
            chunk_key=draft.chunk_key,
            content_hash=draft.content_hash,
            chat_name=draft.chat_name,
            chunk_order=draft.chunk_order,
            started_at=draft.started_at,
            ended_at=draft.ended_at,
            message_count=draft.message_count,
            message_ids=[
                str(
                    message_id
                )
                for message_id
                in draft.message_ids
            ],
            text=draft.text,
        )

    # ======================================================
    # Update helper
    # ======================================================

    @staticmethod
    def _apply_draft(
        chunk: SearchSemanticChunk,
        draft: SemanticChunkDraft,
    ) -> None:
        """
        Apply current draft to persisted chunk.
        """

        chunk.source_id = (
            draft.source_id
        )

        chunk.content_hash = (
            draft.content_hash
        )

        chunk.chat_name = (
            draft.chat_name
        )

        chunk.chunk_order = (
            draft.chunk_order
        )

        chunk.started_at = (
            draft.started_at
        )

        chunk.ended_at = (
            draft.ended_at
        )

        chunk.message_count = (
            draft.message_count
        )

        chunk.message_ids = [
            str(
                message_id
            )
            for message_id
            in draft.message_ids
        ]

        chunk.text = (
            draft.text
        )
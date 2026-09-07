"""
Message semantic chunk builder.

Builds compact semantic chunks from investigation messages.

Architecture:

Message[]
    ↓
MessageSemanticChunkBuilder
    ↓
SemanticChunkDraft[]
    ↓
SearchSemanticChunk
    ↓
SearchSemanticChunkEmbedding

The builder is intentionally independent from Ollama,
pgvector and persistence.

This allows chunking strategies to be tested and tuned
without generating embeddings.

Primary goals:

- dramatically reduce the number of semantic vectors
- preserve conversational context
- preserve chronological order
- never mix unrelated chats or sources
- keep deterministic message grouping
- support dry-run analysis
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
)
import hashlib
from statistics import mean
from typing import Iterable
from uuid import UUID

from app.models.message import (
    Message,
)


# ==========================================================
# Configuration
# ==========================================================

@dataclass(
    frozen=True,
    slots=True,
)
class MessageSemanticChunkConfig:
    """
    Message chunking configuration.

    max_messages:
        Maximum number of messages in one chunk.

    target_characters:
        Preferred approximate semantic text size.

    max_characters:
        Hard maximum semantic text size.

    max_time_gap_minutes:
        Start a new chunk when two chronological messages
        are separated by more than this amount of time.

    include_sender:
        Include sender labels in semantic text.

    include_chat_name:
        Include chat name once in chunk text.
    """

    max_messages: int = 20

    target_characters: int = 1200

    max_characters: int = 2000

    max_time_gap_minutes: int = 60

    include_sender: bool = True

    include_chat_name: bool = False

    def __post_init__(
        self,
    ) -> None:

        if self.max_messages < 1:

            raise ValueError(
                "max_messages must be at least 1."
            )

        if self.target_characters < 1:

            raise ValueError(
                "target_characters must be at least 1."
            )

        if (
            self.max_characters
            < self.target_characters
        ):

            raise ValueError(
                "max_characters must be greater than "
                "or equal to target_characters."
            )

        if self.max_time_gap_minutes < 1:

            raise ValueError(
                "max_time_gap_minutes must be at least 1."
            )


# ==========================================================
# Draft
# ==========================================================

@dataclass(
    frozen=True,
    slots=True,
)
class SemanticChunkDraft:
    """
    In-memory semantic chunk.

    This object contains everything required later to create
    a SearchSemanticChunk database row.
    """

    case_id: UUID

    source_id: UUID | None

    chat_name: str | None

    chunk_order: int

    started_at: datetime | None

    ended_at: datetime | None

    message_ids: tuple[UUID, ...]

    message_count: int

    text: str

    chunk_key: str

    content_hash: str

    @property
    def character_count(
        self,
    ) -> int:
        """
        Number of characters in semantic text.
        """

        return len(
            self.text
        )


# ==========================================================
# Statistics
# ==========================================================

@dataclass(
    frozen=True,
    slots=True,
)
class SemanticChunkBuildStatistics:
    """
    Statistics produced by a dry-run chunk build.
    """

    input_messages: int

    usable_messages: int

    skipped_empty_messages: int

    chunks_created: int

    minimum_messages_per_chunk: int

    maximum_messages_per_chunk: int

    average_messages_per_chunk: float

    minimum_characters_per_chunk: int

    maximum_characters_per_chunk: int

    average_characters_per_chunk: float

    reduction_percent: float

    split_reasons: dict[str, int]


# ==========================================================
# Internal prepared message
# ==========================================================

@dataclass(
    frozen=True,
    slots=True,
)
class _PreparedMessage:
    """
    Normalized message used internally by the builder.
    """

    message: Message

    text: str

    rendered_text: str


# ==========================================================
# Builder
# ==========================================================

class MessageSemanticChunkBuilder:
    """
    Builds semantic chunks from Message objects.
    """

    def __init__(
        self,
        config: (
            MessageSemanticChunkConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or MessageSemanticChunkConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def build(
        self,
        messages: Iterable[Message],
    ) -> list[SemanticChunkDraft]:
        """
        Build semantic chunks.

        Messages are separated by case, source and chat
        before chunking.

        Empty messages are ignored.
        """

        message_list = list(
            messages
        )

        groups = self._group_messages(
            message_list
        )

        drafts: list[
            SemanticChunkDraft
        ] = []

        for group_messages in groups.values():

            drafts.extend(
                self._build_group(
                    group_messages
                )
            )

        return drafts

    def analyze(
        self,
        messages: Iterable[Message],
    ) -> SemanticChunkBuildStatistics:
        """
        Perform dry-run and return chunking statistics.

        No database writes are performed.
        """

        message_list = list(
            messages
        )

        usable_messages = [
            message
            for message in message_list
            if self._normalize_text(
                message.text
            )
        ]

        drafts = self.build(
            message_list
        )

        skipped_empty = (
            len(message_list)
            - len(usable_messages)
        )

        if not drafts:

            return (
                SemanticChunkBuildStatistics(
                    input_messages=len(
                        message_list
                    ),
                    usable_messages=len(
                        usable_messages
                    ),
                    skipped_empty_messages=(
                        skipped_empty
                    ),
                    chunks_created=0,
                    minimum_messages_per_chunk=0,
                    maximum_messages_per_chunk=0,
                    average_messages_per_chunk=0.0,
                    minimum_characters_per_chunk=0,
                    maximum_characters_per_chunk=0,
                    average_characters_per_chunk=0.0,
                    reduction_percent=0.0,
                    split_reasons={},
                )
            )

        message_counts = [
            draft.message_count
            for draft in drafts
        ]

        character_counts = [
            draft.character_count
            for draft in drafts
        ]

        split_reasons = (
            self._analyze_split_reasons(
                message_list
            )
        )

        reduction_percent = (
            100.0
            * (
                1.0
                - (
                    len(drafts)
                    / max(
                        len(usable_messages),
                        1,
                    )
                )
            )
        )

        return SemanticChunkBuildStatistics(
            input_messages=len(
                message_list
            ),
            usable_messages=len(
                usable_messages
            ),
            skipped_empty_messages=(
                skipped_empty
            ),
            chunks_created=len(
                drafts
            ),
            minimum_messages_per_chunk=min(
                message_counts
            ),
            maximum_messages_per_chunk=max(
                message_counts
            ),
            average_messages_per_chunk=mean(
                message_counts
            ),
            minimum_characters_per_chunk=min(
                character_counts
            ),
            maximum_characters_per_chunk=max(
                character_counts
            ),
            average_characters_per_chunk=mean(
                character_counts
            ),
            reduction_percent=(
                reduction_percent
            ),
            split_reasons=dict(
                split_reasons
            ),
        )

    # ==========================================================
    # Grouping
    # ==========================================================

    def _group_messages(
        self,
        messages: list[Message],
    ) -> dict[
        tuple[
            UUID,
            UUID | None,
            str,
        ],
        list[Message],
    ]:
        """
        Group messages by case/source/chat.

        Messages from unrelated conversations must never
        enter the same semantic chunk.
        """

        groups: dict[
            tuple[
                UUID,
                UUID | None,
                str,
            ],
            list[Message],
        ] = {}

        for message in messages:

            text = self._normalize_text(
                message.text
            )

            if not text:

                continue

            chat_name = (
                self._normalize_chat_name(
                    message.chat_name
                )
            )

            key = (
                message.case_id,
                message.source_id,
                chat_name,
            )

            groups.setdefault(
                key,
                [],
            ).append(
                message
            )

        for group in groups.values():

            group.sort(
                key=self._message_sort_key
            )

        return groups

    # ==========================================================
    # Group chunking
    # ==========================================================

    def _build_group(
        self,
        messages: list[Message],
    ) -> list[SemanticChunkDraft]:
        """
        Build chunks for one conversation group.
        """

        if not messages:

            return []

        prepared = [
            self._prepare_message(
                message
            )
            for message in messages
        ]

        drafts: list[
            SemanticChunkDraft
        ] = []

        current: list[
            _PreparedMessage
        ] = []

        current_characters = 0

        chunk_order = 0

        previous: (
            _PreparedMessage
            | None
        ) = None

        for item in prepared:

            should_split = False

            if current:

                if (
                    len(current)
                    >= self.config.max_messages
                ):

                    should_split = True

                elif (
                    current_characters
                    + self._separator_size(
                        current
                    )
                    + len(
                        item.rendered_text
                    )
                    > self.config.max_characters
                ):

                    should_split = True

                elif (
                    previous is not None
                    and self._has_large_time_gap(
                        previous.message,
                        item.message,
                    )
                ):

                    should_split = True

                elif (
                    current_characters
                    >= self.config.target_characters
                ):

                    should_split = True

            if should_split:

                drafts.append(
                    self._create_draft(
                        current,
                        chunk_order=chunk_order,
                    )
                )

                chunk_order += 1

                current = []

                current_characters = 0

            if current:

                current_characters += (
                    self._separator_size(
                        current
                    )
                )

            current.append(
                item
            )

            current_characters += len(
                item.rendered_text
            )

            previous = item

        if current:

            drafts.append(
                self._create_draft(
                    current,
                    chunk_order=chunk_order,
                )
            )

        return drafts

    # ==========================================================
    # Draft creation
    # ==========================================================

    def _create_draft(
        self,
        messages: list[_PreparedMessage],
        *,
        chunk_order: int,
    ) -> SemanticChunkDraft:
        """
        Convert prepared messages into one draft.
        """

        if not messages:

            raise ValueError(
                "Cannot create an empty semantic chunk."
            )

        first = messages[
            0
        ].message

        last = messages[
            -1
        ].message

        message_ids = tuple(
            item.message.id
            for item in messages
        )

        body = "\n".join(
            item.rendered_text
            for item in messages
        )

        chat_name = (
            first.chat_name.strip()
            if first.chat_name
            else None
        )

        if (
            self.config.include_chat_name
            and chat_name
        ):

            text = (
                f"Chat: {chat_name}\n\n"
                f"{body}"
            )

        else:

            text = body

        chunk_key = (
            self._build_chunk_key(
                case_id=first.case_id,
                message_ids=message_ids,
            )
        )

        content_hash = (
            self._build_content_hash(
                text
            )
        )

        return SemanticChunkDraft(
            case_id=first.case_id,
            source_id=first.source_id,
            chat_name=chat_name,
            chunk_order=chunk_order,
            started_at=first.sent_at,
            ended_at=last.sent_at,
            message_ids=message_ids,
            message_count=len(
                message_ids
            ),
            text=text,
            chunk_key=chunk_key,
            content_hash=content_hash,
        )

    # ==========================================================
    # Message preparation
    # ==========================================================

    def _prepare_message(
        self,
        message: Message,
    ) -> _PreparedMessage:
        """
        Normalize and render one message.
        """

        text = self._normalize_text(
            message.text
        )

        sender = (
            message.sender.strip()
            if message.sender
            else ""
        )

        if (
            self.config.include_sender
            and sender
        ):

            rendered = (
                f"{sender}: {text}"
            )

        else:

            rendered = text

        return _PreparedMessage(
            message=message,
            text=text,
            rendered_text=rendered,
        )

    # ==========================================================
    # Split analysis
    # ==========================================================

    def _analyze_split_reasons(
        self,
        messages: list[Message],
    ) -> Counter[str]:
        """
        Estimate why chunks are split.

        Used only for dry-run diagnostics.
        """

        groups = self._group_messages(
            messages
        )

        reasons: Counter[str] = Counter()

        for group in groups.values():

            prepared = [
                self._prepare_message(
                    message
                )
                for message in group
            ]

            current: list[
                _PreparedMessage
            ] = []

            current_characters = 0

            previous: (
                _PreparedMessage
                | None
            ) = None

            for item in prepared:

                reason: (
                    str
                    | None
                ) = None

                if current:

                    if (
                        len(current)
                        >= self.config.max_messages
                    ):

                        reason = (
                            "max_messages"
                        )

                    elif (
                        current_characters
                        + self._separator_size(
                            current
                        )
                        + len(
                            item.rendered_text
                        )
                        > self.config.max_characters
                    ):

                        reason = (
                            "max_characters"
                        )

                    elif (
                        previous is not None
                        and self._has_large_time_gap(
                            previous.message,
                            item.message,
                        )
                    ):

                        reason = (
                            "time_gap"
                        )

                    elif (
                        current_characters
                        >= self.config.target_characters
                    ):

                        reason = (
                            "target_characters"
                        )

                if reason is not None:

                    reasons.update(
                        [
                            reason
                        ]
                    )

                    current = []

                    current_characters = 0

                if current:

                    current_characters += (
                        self._separator_size(
                            current
                        )
                    )

                current.append(
                    item
                )

                current_characters += len(
                    item.rendered_text
                )

                previous = item

        return reasons

    # ==========================================================
    # Time
    # ==========================================================

    def _has_large_time_gap(
        self,
        previous: Message,
        current: Message,
    ) -> bool:
        """
        Check whether messages are too far apart in time.
        """

        if (
            previous.sent_at is None
            or current.sent_at is None
        ):

            return False

        difference = (
            current.sent_at
            - previous.sent_at
        )

        return (
            difference
            > timedelta(
                minutes=(
                    self.config
                    .max_time_gap_minutes
                )
            )
        )

    # ==========================================================
    # Deterministic identity
    # ==========================================================

    def _build_chunk_key(
        self,
        *,
        case_id: UUID,
        message_ids: tuple[
            UUID,
            ...,
        ],
    ) -> str:
        """
        Build deterministic SHA256 chunk identity.
        """

        payload = "|".join(
            [
                str(
                    case_id
                ),
                *(
                    str(
                        message_id
                    )
                    for message_id
                    in message_ids
                ),
            ]
        )

        return hashlib.sha256(
            payload.encode(
                "utf-8"
            )
        ).hexdigest()

    def _build_content_hash(
        self,
        text: str,
    ) -> str:
        """
        Build SHA256 semantic-content hash.
        """

        return hashlib.sha256(
            text.encode(
                "utf-8"
            )
        ).hexdigest()

    # ==========================================================
    # Normalization
    # ==========================================================

    def _normalize_text(
        self,
        value: str | None,
    ) -> str:
        """
        Normalize message text.

        Internal whitespace inside the message is preserved
        because it may carry semantic structure.
        """

        if value is None:

            return ""

        return value.strip()

    def _normalize_chat_name(
        self,
        value: str | None,
    ) -> str:
        """
        Normalize chat grouping key.
        """

        if value is None:

            return ""

        return value.strip()

    # ==========================================================
    # Sorting
    # ==========================================================

    def _message_sort_key(
        self,
        message: Message,
    ) -> tuple:
        """
        Stable chronological ordering.

        sent_at is preferred.

        UUID string provides deterministic ordering when
        timestamps are identical or missing.
        """

        if message.sent_at is None:

            return (
                1,
                datetime.max,
                str(
                    message.id
                ),
            )

        sent_at = (
            message.sent_at
        )

        if (
            sent_at.tzinfo
            is not None
        ):

            sent_at = (
                sent_at.replace(
                    tzinfo=None
                )
            )

        return (
            0,
            sent_at,
            str(
                message.id
            ),
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    def _separator_size(
        self,
        current: list[
            _PreparedMessage
        ],
    ) -> int:
        """
        Size of separator inserted between messages.
        """

        if not current:

            return 0

        return 1
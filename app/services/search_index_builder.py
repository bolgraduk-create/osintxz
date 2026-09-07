"""
Search index builder.

Builds and maintains SearchIndex records from
investigation domain models.

Architecture:

Domain objects
    ├── Entity
    ├── Evidence
    ├── Document
    ├── Message
    ├── Note
    ├── Artifact
    └── Report
        ↓
SearchIndexBuilder
        ↓
SearchIndexRepository
        ↓
SearchIndex
        ↓
Unified Search
    ├── BM25
    ├── Fuzzy
    └── Semantic embeddings

Responsibilities:

- convert domain objects into searchable representations
- create missing SearchIndex records
- update existing SearchIndex records
- backfill complete investigation cases
- skip soft-deleted objects
- keep object identity stable

Does NOT:

- perform retrieval
- calculate BM25
- calculate fuzzy similarity
- generate embeddings
- perform rank fusion
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artifact import (
    Artifact,
)

from app.models.document import (
    Document,
)

from app.models.entity import (
    Entity,
)

from app.models.evidence import (
    Evidence,
)

from app.models.message import (
    Message,
)

from app.models.note import (
    Note,
)

from app.models.report import (
    Report,
)

from app.models.search_index import (
    SearchIndex,
    SearchObjectType,
)

from app.repositories.search_index_repository import (
    SearchIndexRepository,
)


# ==========================================================
# Result
# ==========================================================


@dataclass(
    slots=True,
)
class SearchIndexBuildResult:
    """
    Summary of one indexing operation.
    """

    processed: int = 0

    created: int = 0

    updated: int = 0

    skipped: int = 0

    failed: int = 0

    @property
    def indexed(
        self,
    ) -> int:
        """
        Number of created or updated indexes.
        """

        return (
            self.created
            + self.updated
        )


# ==========================================================
# Search representation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SearchIndexDocument:
    """
    Normalized searchable representation of
    one domain object.
    """

    case_id: UUID

    object_type: SearchObjectType

    object_id: UUID

    title: str

    content: str


# ==========================================================
# Builder
# ==========================================================


class SearchIndexBuilder:
    """
    Builds SearchIndex records from investigation objects.
    """

    def __init__(
        self,
        session: Session,
        repository: SearchIndexRepository
        | None = None,
    ) -> None:

        self.session = session

        self.repository = (
            repository
            or SearchIndexRepository(
                session
            )
        )

    # ======================================================
    # Full case backfill
    # ======================================================

    def build_case(
        self,
        case_id: UUID,
    ) -> SearchIndexBuildResult:
        """
        Backfill every supported searchable object
        belonging to one investigation case.
        """

        result = (
            SearchIndexBuildResult()
        )

        model_types = (
            Entity,
            Evidence,
            Document,
            Message,
            Note,
            Artifact,
            Report,
        )

        for model in model_types:

            objects = (
                self._load_case_objects(
                    model,
                    case_id,
                )
            )

            self._build_many(
                objects,
                result,
            )

        return result

    # ======================================================
    # Multiple objects
    # ======================================================

    def build_many(
        self,
        objects: Iterable[
            object
        ],
    ) -> SearchIndexBuildResult:
        """
        Index arbitrary supported domain objects.
        """

        result = (
            SearchIndexBuildResult()
        )

        self._build_many(
            objects,
            result,
        )

        return result

    def _build_many(
        self,
        objects: Iterable[
            object
        ],
        result: SearchIndexBuildResult,
    ) -> None:
        """
        Internal multiple-object indexing.
        """

        for obj in objects:

            result.processed += 1

            try:

                status = (
                    self.build_object(
                        obj
                    )
                )

            except Exception:

                result.failed += 1

                continue

            if status == "created":

                result.created += 1

            elif status == "updated":

                result.updated += 1

            else:

                result.skipped += 1

    # ======================================================
    # One object
    # ======================================================

    def build_object(
        self,
        obj: object,
    ) -> str:
        """
        Build or update SearchIndex for one object.

        Returns:

            "created"
            "updated"
            "skipped"
        """

        if self._is_deleted(
            obj
        ):

            return "skipped"

        document = (
            self.to_search_document(
                obj
            )
        )

        if document is None:

            return "skipped"

        if (
            not document.title
            and not document.content
        ):

            return "skipped"

        existing = (
            self.repository.get_by_object(
                document.object_type,
                document.object_id,
            )
        )

        if existing is None:

            index = SearchIndex(
                case_id=(
                    document.case_id
                ),
                object_type=(
                    document.object_type
                ),
                object_id=(
                    document.object_id
                ),
                title=(
                    document.title
                ),
                content=(
                    document.content
                ),
            )

            self.repository.create(
                index
            )

            return "created"

        changed = False

        if (
            existing.case_id
            != document.case_id
        ):

            existing.case_id = (
                document.case_id
            )

            changed = True

        if (
            existing.title
            != document.title
        ):

            existing.title = (
                document.title
            )

            changed = True

        if (
            existing.content
            != document.content
        ):

            existing.content = (
                document.content
            )

            changed = True

        if (
            getattr(
                existing,
                "deleted_at",
                None,
            )
            is not None
        ):

            existing.deleted_at = None

            changed = True

        if changed:

            self.session.flush()

            return "updated"

        return "skipped"

    # ======================================================
    # Domain → SearchIndex
    # ======================================================

    def to_search_document(
        self,
        obj: object,
    ) -> SearchIndexDocument | None:
        """
        Convert supported domain model into one
        normalized searchable document.
        """

        if isinstance(
            obj,
            Entity,
        ):

            return self._entity_document(
                obj
            )

        if isinstance(
            obj,
            Evidence,
        ):

            return self._evidence_document(
                obj
            )

        if isinstance(
            obj,
            Document,
        ):

            return self._document_document(
                obj
            )

        if isinstance(
            obj,
            Message,
        ):

            return self._message_document(
                obj
            )

        if isinstance(
            obj,
            Note,
        ):

            return self._note_document(
                obj
            )

        if isinstance(
            obj,
            Artifact,
        ):

            return self._artifact_document(
                obj
            )

        if isinstance(
            obj,
            Report,
        ):

            return self._report_document(
                obj
            )

        return None

    # ======================================================
    # Entity
    # ======================================================

    def _entity_document(
        self,
        entity: Entity,
    ) -> SearchIndexDocument:
        """
        Search representation for Entity.
        """

        entity_type = (
            entity.entity_type.value
            if hasattr(
                entity.entity_type,
                "value",
            )
            else str(
                entity.entity_type
            )
        )

        title = (
            entity.value
            or entity.normalized_value
            or entity_type
        )

        content = self._join_parts(
            [
                entity.value,
                entity.normalized_value,
                entity_type,
                entity.description,
                entity.metadata_json,
            ]
        )

        return SearchIndexDocument(
            case_id=entity.case_id,
            object_type=(
                SearchObjectType.ENTITY
            ),
            object_id=entity.id,
            title=self._title(
                title
            ),
            content=content,
        )

    # ======================================================
    # Evidence
    # ======================================================

    def _evidence_document(
        self,
        evidence: Evidence,
    ) -> SearchIndexDocument:

        evidence_type = (
            evidence.evidence_type.value
            if hasattr(
                evidence.evidence_type,
                "value",
            )
            else str(
                evidence.evidence_type
            )
        )

        content = self._join_parts(
            [
                evidence.title,
                evidence.value,
                evidence_type,
                evidence.description,
                evidence.file_path,
                evidence.mime_type,
                evidence.sha256,
                evidence.metadata_json,
            ]
        )

        return SearchIndexDocument(
            case_id=evidence.case_id,
            object_type=(
                SearchObjectType.EVIDENCE
            ),
            object_id=evidence.id,
            title=self._title(
                evidence.title
            ),
            content=content,
        )

    # ======================================================
    # Document
    # ======================================================

    def _document_document(
        self,
        document: Document,
    ) -> SearchIndexDocument:

        document_type = (
            document.document_type.value
            if hasattr(
                document.document_type,
                "value",
            )
            else str(
                document.document_type
            )
        )

        content = self._join_parts(
            [
                document.title,
                document.content,
                document_type,
                document.description,
                document.file_path,
                document.sha256,
                document.metadata_json,
            ]
        )

        return SearchIndexDocument(
            case_id=document.case_id,
            object_type=(
                SearchObjectType.DOCUMENT
            ),
            object_id=document.id,
            title=self._title(
                document.title
            ),
            content=content,
        )

    # ======================================================
    # Message
    # ======================================================

    def _message_document(
        self,
        message: Message,
    ) -> SearchIndexDocument:
        """
        Build structured searchable representation
        for Message.

        SearchIndex keeps both message text and useful
        metadata for lexical/fuzzy retrieval.

        Explicit field markers also allow semantic indexing
        to distinguish actual message content from technical
        metadata.
        """

        sender = (
            message.sender
            or ""
        ).strip()

        receiver = (
            message.receiver
            or ""
        ).strip()

        chat_name = (
            message.chat_name
            or ""
        ).strip()

        message_text = (
            message.text
            or ""
        ).strip()

        external_id = (
            message.external_id
            or ""
        ).strip()

        sent_at = (
            message.sent_at.isoformat()
            if message.sent_at
            else ""
        )

        # ------------------------------------------------------
        # Title
        # ------------------------------------------------------

        title_parts: list[str] = []

        if sender:

            title_parts.append(
                sender
            )

        if chat_name:

            title_parts.append(
                chat_name
            )

        title = (
            " — ".join(
                title_parts
            )
            or "Message"
        )

        # ------------------------------------------------------
        # Structured content
        # ------------------------------------------------------

        sections: list[str] = []

        if message_text:

            sections.append(
                "MESSAGE_TEXT:\n"
                + message_text
            )

        if sender:

            sections.append(
                "SENDER:\n"
                + sender
            )

        if receiver:

            sections.append(
                "RECEIVER:\n"
                + receiver
            )

        if chat_name:

            sections.append(
                "CHAT:\n"
                + chat_name
            )

        if external_id:

            sections.append(
                "EXTERNAL_ID:\n"
                + external_id
            )

        if sent_at:

            sections.append(
                "SENT_AT:\n"
                + sent_at
            )

        if message.metadata_json:

            sections.append(
                "METADATA:\n"
                + str(
                    message.metadata_json
                )
            )

        content = "\n\n".join(
            sections
        ).strip()

        return SearchIndexDocument(
            case_id=message.case_id,
            object_type=(
                SearchObjectType.MESSAGE
            ),
            object_id=message.id,
            title=self._title(
                title
            ),
            content=content,
        )

    # ======================================================
    # Note
    # ======================================================

    def _note_document(
        self,
        note: Note,
    ) -> SearchIndexDocument:

        content = self._join_parts(
            [
                note.title,
                note.content,
                note.description,
            ]
        )

        return SearchIndexDocument(
            case_id=note.case_id,
            object_type=(
                SearchObjectType.NOTE
            ),
            object_id=note.id,
            title=self._title(
                note.title
            ),
            content=content,
        )

    # ======================================================
    # Artifact
    # ======================================================

    def _artifact_document(
        self,
        artifact: Artifact,
    ) -> SearchIndexDocument:

        artifact_type = (
            artifact.artifact_type.value
            if hasattr(
                artifact.artifact_type,
                "value",
            )
            else str(
                artifact.artifact_type
            )
        )

        content = self._join_parts(
            [
                artifact.name,
                artifact_type,
                artifact.description,
                artifact.file_path,
                artifact.mime_type,
                artifact.metadata_json,
            ]
        )

        return SearchIndexDocument(
            case_id=artifact.case_id,
            object_type=(
                SearchObjectType.ARTIFACT
            ),
            object_id=artifact.id,
            title=self._title(
                artifact.name
            ),
            content=content,
        )

    # ======================================================
    # Report
    # ======================================================

    def _report_document(
        self,
        report: Report,
    ) -> SearchIndexDocument:

        report_type = (
            report.report_type.value
            if hasattr(
                report.report_type,
                "value",
            )
            else str(
                report.report_type
            )
        )

        content = self._join_parts(
            [
                report.title,
                report.content,
                report_type,
                report.description,
                report.metadata_json,
            ]
        )

        return SearchIndexDocument(
            case_id=report.case_id,
            object_type=(
                SearchObjectType.REPORT
            ),
            object_id=report.id,
            title=self._title(
                report.title
            ),
            content=content,
        )

    # ======================================================
    # Loading
    # ======================================================

    def _load_case_objects(
        self,
        model,
        case_id: UUID,
    ) -> list:
        """
        Load model instances belonging to one case.
        """

        statement = (
            select(
                model
            )
            .where(
                model.case_id
                == case_id
            )
        )

        result = (
            self.session.execute(
                statement
            )
        )

        return list(
            result.scalars().all()
        )

    # ======================================================
    # Helpers
    # ======================================================

    @staticmethod
    def _is_deleted(
        obj: object,
    ) -> bool:
        """
        Detect SoftDeleteMixin records.
        """

        return (
            getattr(
                obj,
                "deleted_at",
                None,
            )
            is not None
        )

    @staticmethod
    def _join_parts(
        parts,
    ) -> str:
        """
        Join searchable values while removing
        empty and duplicate fragments.
        """

        result: list[str] = []

        seen: set[str] = set()

        for value in parts:

            if value is None:

                continue

            text = str(
                value
            ).strip()

            if not text:

                continue

            if text in seen:

                continue

            seen.add(
                text
            )

            result.append(
                text
            )

        return "\n".join(
            result
        )

    @staticmethod
    def _title(
        value: str | None,
    ) -> str:
        """
        Normalize SearchIndex title to fit VARCHAR(255).
        """

        text = (
            str(
                value
                or "Untitled"
            )
            .strip()
        )

        if not text:

            text = "Untitled"

        return text[
            :255
        ]
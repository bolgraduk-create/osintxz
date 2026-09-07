"""
Collection service.

Responsible for:

- collecting imported investigation data
- creating raw investigation objects
- delegating persistence to domain services

Does NOT:

- perform analysis
- create entities
- create relationships
- execute AI
- build reports
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.collectors.base.models import (
    CollectedItem,
    CollectedItemType,
)

from app.models.artifact import Artifact
from app.models.document import (
    Document,
    DocumentType,
)
from app.models.evidence import (
    Evidence,
    EvidenceType,
)
from app.models.message import Message
from app.models.source import (
    Source,
    SourceType,
)

from app.services.artifact_service import (
    ArtifactService,
)
from app.services.document_service import (
    DocumentService,
)
from app.services.evidence_service import (
    EvidenceService,
)
from app.services.message_service import (
    MessageService,
)
from app.services.source_service import (
    SourceService,
)


class CollectionService:
    """
    Stores imported investigation data.
    """

    def __init__(
        self,
        source_service: SourceService,
        evidence_service: EvidenceService,
        message_service: MessageService,
        document_service: DocumentService,
        artifact_service: ArtifactService,
    ) -> None:

        self.source_service = source_service
        self.evidence_service = evidence_service
        self.message_service = message_service
        self.document_service = document_service
        self.artifact_service = artifact_service

    # ==========================================================
    # Source
    # ==========================================================

    def create_source(
        self,
        case_id: UUID,
        name: str,
        source_type: SourceType,
        path: str | Path | None = None,
        description: str | None = None,
    ) -> Source:

        return self.source_service.create_source(
            case_id=case_id,
            name=name,
            source_type=source_type,
            path=str(path) if path else None,
            description=description,
        )

    # ==========================================================
    # Messages
    # ==========================================================

    def create_message(
        self,
        **kwargs,
    ) -> Message:

        return self.message_service.create_message(
            **kwargs,
        )

    # ==========================================================
    # Documents
    # ==========================================================

    def create_document(
        self,
        case_id: UUID,
        title: str,
        document_type: DocumentType,
        source_id: UUID | None = None,
        file_path: str | None = None,
        content: str | None = None,
        description: str | None = None,
    ) -> Document:

        return self.document_service.create_document(
            case_id=case_id,
            title=title,
            document_type=document_type,
            source_id=source_id,
            file_path=file_path,
            content=content,
            description=description,
        )

    # ==========================================================
    # Evidence
    # ==========================================================

    def create_evidence(
        self,
        case_id: UUID,
        source_id: UUID,
        evidence_type: EvidenceType,
        title: str,
        value: str | None = None,
        file_path: str | None = None,
        mime_type: str | None = None,
        description: str | None = None,
    ) -> Evidence:

        return self.evidence_service.create_evidence(
            case_id=case_id,
            source_id=source_id,
            evidence_type=evidence_type,
            title=title,
            value=value,
            file_path=file_path,
            mime_type=mime_type,
            description=description,
        )
        # ==========================================================
    # Artifacts
    # ==========================================================

    def create_artifact(
        self,
        case_id: UUID,
        artifact_type,
        name: str,
        file_path: str | None = None,
        mime_type: str | None = None,
        metadata_json: str | None = None,
        description: str | None = None,
    ) -> Artifact:

        return self.artifact_service.create_artifact(
            case_id=case_id,
            artifact_type=artifact_type,
            name=name,
            file_path=file_path,
            mime_type=mime_type,
            metadata_json=metadata_json,
            description=description,
        )

    # ==========================================================
    # Bulk collection
    # ==========================================================

    def collect_many(
        self,
        case_id: UUID,
        source_id: UUID,
        items: list[CollectedItem],
    ) -> None:
        """
        Store objects produced by collectors.

        High-volume collection deliberately performs only
        lightweight search indexing during message creation.

        Semantic embeddings are generated later, once the
        complete import operation has finished.
        """

        for item in items:

            # --------------------------------------------------
            # MESSAGE
            # --------------------------------------------------

            if (
                item.item_type
                == CollectedItemType.MESSAGE
            ):

                self.create_message(
                    case_id=case_id,
                    source_id=source_id,
                    text=item.content,
                    sender=item.author,
                    receiver=None,
                    chat_name=item.title,
                    sent_at=item.timestamp,
                    external_id=item.external_id,
                    evidence_id=None,
                    update_search_index=True,
                )

                continue

            # --------------------------------------------------
            # DOCUMENT
            # --------------------------------------------------

            if (
                item.item_type
                == CollectedItemType.DOCUMENT
            ):

                self.create_document(
                    case_id=case_id,
                    source_id=source_id,
                    title=(
                        item.title
                        or "Document"
                    ),
                    document_type=(
                        DocumentType.OTHER
                    ),
                    file_path=(
                        item.metadata.get(
                            "file_path"
                        )
                    ),
                    content=item.content,
                    description=None,
                )

                continue

            # --------------------------------------------------
            # IMAGE
            # --------------------------------------------------

            if (
                item.item_type
                == CollectedItemType.IMAGE
            ):

                self.create_evidence(
                    case_id=case_id,
                    source_id=source_id,
                    evidence_type=(
                        EvidenceType.IMAGE
                    ),
                    title=(
                        item.title
                        or "Image"
                    ),
                    value=item.content,
                    file_path=(
                        item.metadata.get(
                            "file_path"
                        )
                    ),
                    mime_type=(
                        item.metadata.get(
                            "mime_type"
                        )
                    ),
                    description=None,
                )

                continue

            # --------------------------------------------------
            # VIDEO
            # --------------------------------------------------

            if (
                item.item_type
                == CollectedItemType.VIDEO
            ):

                self.create_evidence(
                    case_id=case_id,
                    source_id=source_id,
                    evidence_type=(
                        EvidenceType.VIDEO
                    ),
                    title=(
                        item.title
                        or "Video"
                    ),
                    value=item.content,
                    file_path=(
                        item.metadata.get(
                            "file_path"
                        )
                    ),
                    mime_type=(
                        item.metadata.get(
                            "mime_type"
                        )
                    ),
                    description=None,
                )

                continue

            # --------------------------------------------------
            # AUDIO
            # --------------------------------------------------

            if (
                item.item_type
                == CollectedItemType.AUDIO
            ):

                self.create_evidence(
                    case_id=case_id,
                    source_id=source_id,
                    evidence_type=(
                        EvidenceType.AUDIO
                    ),
                    title=(
                        item.title
                        or "Audio"
                    ),
                    value=item.content,
                    file_path=(
                        item.metadata.get(
                            "file_path"
                        )
                    ),
                    mime_type=(
                        item.metadata.get(
                            "mime_type"
                        )
                    ),
                    description=None,
                )

                continue

            # --------------------------------------------------
            # CONTACT
            # --------------------------------------------------

            if (
                item.item_type
                == CollectedItemType.CONTACT
            ):

                self.create_evidence(
                    case_id=case_id,
                    source_id=source_id,
                    evidence_type=(
                        EvidenceType.CONTACT
                    ),
                    title=(
                        item.title
                        or "Contact"
                    ),
                    value=item.content,
                    description=None,
                )

                continue

            # --------------------------------------------------
            # LOCATION
            # --------------------------------------------------

            if (
                item.item_type
                == CollectedItemType.LOCATION
            ):

                self.create_evidence(
                    case_id=case_id,
                    source_id=source_id,
                    evidence_type=(
                        EvidenceType.LOCATION
                    ),
                    title=(
                        item.title
                        or "Location"
                    ),
                    value=item.content,
                    description=None,
                )

                continue

            # --------------------------------------------------
            # WEBSITE
            # --------------------------------------------------

            if (
                item.item_type
                == CollectedItemType.WEBSITE
            ):

                self.create_evidence(
                    case_id=case_id,
                    source_id=source_id,
                    evidence_type=(
                        EvidenceType.LINK
                    ),
                    title=(
                        item.title
                        or "Website"
                    ),
                    value=item.content,
                    description=None,
                )

                continue

            # --------------------------------------------------
            # FALLBACK
            # --------------------------------------------------

            self.create_evidence(
                case_id=case_id,
                source_id=source_id,
                evidence_type=(
                    EvidenceType.OTHER
                ),
                title=(
                    item.title
                    or "Collected Item"
                ),
                value=item.content,
                description=None,
            )
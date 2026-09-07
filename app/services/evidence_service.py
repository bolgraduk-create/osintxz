"""
Evidence service.

Contains business logic related
to extracted evidence objects.

Examples:

- images
- videos
- audio files
- contacts
- links
- hashes
- messages
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.evidence import (
    Evidence,
    EvidenceType,
)

from app.repositories.evidence_repository import (
    EvidenceRepository,
)

from app.services.search_indexing_service import (
    SearchIndexingService,
)


class EvidenceService:
    """
    Service for managing evidence objects.
    """

    def __init__(
        self,
        session: Session,
        *,
        search_indexing_service: (
            SearchIndexingService
            | None
        ) = None,
    ) -> None:

        self.repository = (
            EvidenceRepository(
                session
            )
        )

        self.search_indexing_service = (
            search_indexing_service
        )

    # ==========================================================
    # Creation
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
        *,
        metadata_json: str | None = None,
        update_search_index: bool = True,
    ) -> Evidence:
        """
        Create a new evidence object.
        """

        evidence = Evidence(
            case_id=case_id,
            source_id=source_id,
            evidence_type=evidence_type,
            title=title,
            value=value,
            file_path=file_path,
            mime_type=mime_type,
            metadata_json=metadata_json,
            description=description,
        )

        evidence = (
            self.repository.create(
                evidence
            )
        )

        if (
            update_search_index
            and self.search_indexing_service
            is not None
        ):

            self.search_indexing_service \
                .index_object_text_only(
                    evidence
                )

        return evidence

    def create_from_message(
        self,
        case_id: str | UUID,
        message_data: dict[str, Any],
        *,
        metadata_json: str | None = None,
        update_search_index: bool = True,
    ) -> Evidence:
        """
        Create message evidence from UI-ready message data.

        The method converts identifiers to UUID values and prepares
        a readable title, compact value and full description.

        Raises:
            TypeError:
                If message_data is not a dictionary.

            ValueError:
                If the message does not contain a valid source ID.
        """

        if not isinstance(
            message_data,
            dict,
        ):
            raise TypeError(
                "message_data must be a dictionary"
            )

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        source_id = message_data.get(
            "source_id"
        )

        if source_id is None:

            raise ValueError(
                "Message data does not contain source_id."
            )

        source_uuid = self._normalize_uuid(
            source_id,
            field_name="source_id",
        )

        sender = self._normalize_text(
            message_data.get(
                "sender"
            )
        )

        receiver = self._normalize_text(
            message_data.get(
                "receiver"
            )
        )

        chat_name = self._normalize_text(
            message_data.get(
                "chat_name"
            )
        )

        sent_at = self._normalize_text(
            message_data.get(
                "sent_at"
            )
        )

        external_id = self._normalize_text(
            message_data.get(
                "external_id"
            )
        )

        message_text = self._normalize_text(
            message_data.get(
                "text"
            )
        )

        title = self._build_message_title(
            sender=sender,
            chat_name=chat_name,
            sent_at=sent_at,
        )

        value = self._build_message_value(
            message_text
        )

        description = self._build_message_description(
            sender=sender,
            receiver=receiver,
            chat_name=chat_name,
            sent_at=sent_at,
            external_id=external_id,
            message_text=message_text,
        )

        return self.create_evidence(
            case_id=case_uuid,
            source_id=source_uuid,
            evidence_type=EvidenceType.MESSAGE,
            title=title,
            value=value,
            description=description,
            metadata_json=metadata_json,
            update_search_index=update_search_index,
        )

    # ==========================================================
    # Reading
    # ==========================================================

    def get_evidence(
        self,
        evidence_id: UUID,
    ) -> Evidence | None:
        """
        Get evidence by ID.
        """

        return self.repository.get(
            evidence_id
        )

    def get_case_evidence(
        self,
        case_id: UUID,
    ) -> list[Evidence]:
        """
        Return evidence belonging to a case.
        """

        return self.repository.get_by_case(
            case_id
        )


    def find_case_evidence_by_hash(
        self,
        case_id: UUID,
        sha256: str,
    ) -> Evidence | None:
        """
        Find active evidence with the same SHA256 inside one case.
        """

        normalized_hash = str(
            sha256
            or ""
        ).strip().lower()

        if not normalized_hash:

            return None

        return self.repository.find_by_case_and_hash(
            case_id=case_id,
            sha256=normalized_hash,
        )

    # ==========================================================
    # Updating
    # ==========================================================

    def set_hash(
        self,
        evidence_id: UUID,
        sha256: str,
    ) -> Evidence | None:
        """
        Store SHA256 hash.
        """

        evidence = self.repository.get(
            evidence_id
        )

        if evidence is None:

            return None

        evidence.sha256 = sha256

        self.repository.session.flush()

        return evidence

    def update_metadata(
        self,
        evidence_id: UUID,
        metadata_json: str,
    ) -> Evidence | None:
        """
        Update evidence metadata.
        """

        evidence = self.repository.get(
            evidence_id
        )

        if evidence is None:

            return None

        evidence.metadata_json = metadata_json

        self.repository.session.flush()

        return evidence

    # ==========================================================
    # Deletion
    # ==========================================================

    def delete_evidence(
        self,
        evidence_id: UUID,
    ) -> bool:
        """
        Soft-delete evidence and remove its search
        representations.
        """

        evidence = (
            self.repository.get(
                evidence_id
            )
        )

        if evidence is None:

            return False

        evidence.soft_delete()

        self.repository.session.flush()

        if (
            self.search_indexing_service
            is not None
        ):

            self.search_indexing_service \
                .remove_object(
                    evidence
                )

        return True

    # ==========================================================
    # Message evidence helpers
    # ==========================================================

    @staticmethod
    def _build_message_title(
        *,
        sender: str,
        chat_name: str,
        sent_at: str,
    ) -> str:
        """
        Build a concise title for message evidence.
        """

        subject = (
            sender
            or chat_name
            or "Unknown sender"
        )

        if sent_at:

            title = (
                f"Message from {subject} — "
                f"{sent_at}"
            )

        else:

            title = (
                f"Message from {subject}"
            )

        return title[
            :255
        ]

    @staticmethod
    def _build_message_value(
        message_text: str,
    ) -> str | None:
        """
        Build compact evidence value suitable for String(1024).
        """

        if not message_text:

            return None

        compact_text = " ".join(
            message_text.split()
        )

        return compact_text[
            :1024
        ]

    @staticmethod
    def _build_message_description(
        *,
        sender: str,
        receiver: str,
        chat_name: str,
        sent_at: str,
        external_id: str,
        message_text: str,
    ) -> str:
        """
        Build full readable message evidence description.
        """

        unavailable = "Unavailable"

        return (
            "Message evidence\n\n"
            f"Date:\n"
            f"{sent_at or unavailable}\n\n"
            f"Sender:\n"
            f"{sender or unavailable}\n\n"
            f"Receiver:\n"
            f"{receiver or unavailable}\n\n"
            f"Chat:\n"
            f"{chat_name or unavailable}\n\n"
            f"External ID:\n"
            f"{external_id or unavailable}\n\n"
            f"Message:\n"
            f"{message_text or 'No text content'}"
        )

    # ==========================================================
    # General helpers
    # ==========================================================

    @staticmethod
    def _normalize_uuid(
        value: str | UUID,
        *,
        field_name: str,
    ) -> UUID:
        """
        Convert an identifier to UUID.
        """

        if isinstance(
            value,
            UUID,
        ):

            return value

        try:

            return UUID(
                str(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                f"{field_name} must contain a valid UUID."
            ) from error

    @staticmethod
    def _normalize_text(
        value: Any,
    ) -> str:
        """
        Convert an optional value to normalized text.
        """

        if value is None:

            return ""

        return str(
            value
        ).strip()
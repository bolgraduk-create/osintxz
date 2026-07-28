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
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.evidence import (
    Evidence,
    EvidenceType,
)

from app.repositories.evidence_repository import (
    EvidenceRepository,
)


class EvidenceService:
    """
    Service for managing evidence objects.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.repository = EvidenceRepository(
            session
        )


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
        """
        Create new evidence object.
        """

        evidence = Evidence(
            case_id=case_id,
            source_id=source_id,
            evidence_type=evidence_type,
            title=title,
            value=value,
            file_path=file_path,
            mime_type=mime_type,
            description=description,
        )

        return self.repository.create(
            evidence
        )


    def get_evidence(
        self,
        evidence_id: UUID,
    ) -> Evidence | None:
        """
        Get evidence by id.
        """

        return self.repository.get(
            evidence_id
        )


    def get_case_evidence(
        self,
        case_id: UUID,
    ) -> list[Evidence]:
        """
        Return evidence belonging
        to a case.
        """

        return self.repository.get_by_case(
            case_id
        )


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


    def delete_evidence(
        self,
        evidence_id: UUID,
    ) -> bool:
        """
        Soft delete evidence.
        """

        evidence = self.repository.get(
            evidence_id
        )

        if evidence is None:
            return False

        evidence.soft_delete()

        self.repository.session.flush()

        return True
"""
Unified extraction service.

Coordinates source-agnostic textual extraction, entity persistence and
occurrence-level provenance.

Current production source:
    - Message.text

Future sources can reuse the same extraction contract:
    - document text
    - OCR text
    - audio/video transcripts
    - registry documents
    - permitted public web content

The service does NOT implement identifier patterns itself. Pattern
recognition is delegated to IdentifierExtractor / EntityAnalyzer.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.models.entity import Entity
from app.processing.extraction import ExtractionCandidate
from app.processing.extraction import ExtractionObjectType
from app.processing.extraction import ExtractionOrigin
from app.processing.extraction import IdentifierExtractor
from app.repositories.message_repository import MessageRepository
from app.services.evidence_link_service import EvidenceLinkService
from app.services.evidence_service import EvidenceService

if TYPE_CHECKING:
    from app.models.message import Message
    from app.services.entity_service import EntityService


class UnifiedExtractionService:
    """Application-wide extraction coordinator."""

    MAX_ENTITY_VALUE_LENGTH = 512

    def __init__(
        self,
        session: Session | None,
        entity_service: EntityService,
        *,
        identifier_extractor: IdentifierExtractor | None = None,
        message_repository: MessageRepository | None = None,
        evidence_service: EvidenceService | None = None,
        evidence_link_service: EvidenceLinkService | None = None,
    ) -> None:
        self.session = session
        self.entity_service = entity_service
        self.identifier_extractor = (
            identifier_extractor or IdentifierExtractor()
        )
        self.message_repository = (
            message_repository
            or (
                MessageRepository(session)
                if session is not None
                else None
            )
        )
        self.evidence_service = (
            evidence_service
            or (
                EvidenceService(session)
                if session is not None
                else None
            )
        )
        self.evidence_link_service = (
            evidence_link_service
            or (
                EvidenceLinkService(session)
                if session is not None
                else None
            )
        )

        if self.message_repository is None:
            raise ValueError(
                "message_repository is required when session is None."
            )

    # ==========================================================
    # Extraction API
    # ==========================================================

    def extract_text(
        self,
        text: str | None,
    ) -> list[ExtractionCandidate]:
        """Extract typed identifier candidates without persistence."""

        return self.identifier_extractor.extract(text)

    def extract_case_messages(
        self,
        case_id: str | UUID,
        *,
        source_id: str | UUID | None = None,
    ) -> dict[str, Any]:
        """
        Extract identifiers from stored messages and persist Entities.

        When ``source_id`` is supplied, only messages from that source
        are processed. This is used by import workflows so a new import
        does not unnecessarily reprocess every message in the case.

        For every message that produces at least one persisted logical
        Entity, the service also ensures a MESSAGE Evidence record and
        an idempotent EvidenceEntity link. This keeps one Entity per
        normalized identifier while preserving every message occurrence.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        source_uuid = (
            self._normalize_uuid(
                source_id,
                field_name="source_id",
            )
            if source_id is not None
            else None
        )

        messages = self._load_messages(
            case_id=case_uuid,
            source_id=source_uuid,
        )

        statistics: dict[str, Any] = {
            "case_id": str(case_uuid),
            "source_id": (
                str(source_uuid)
                if source_uuid is not None
                else None
            ),
            "extractor": self.identifier_extractor.name,
            "processed_messages": 0,
            "messages_with_text": 0,
            "extracted_candidates": 0,
            "created_entities": 0,
            "existing_entities": 0,
            "skipped_oversized": 0,
            "skipped_invalid": 0,
            "created_by_type": {},
            "existing_by_type": {},
            "provenance_evidence_created": 0,
            "provenance_evidence_existing": 0,
            "provenance_evidence_unavailable": 0,
            "evidence_links_created": 0,
            "evidence_links_existing": 0,
        }

        for message in messages:
            # Defensive case isolation when loading by source.
            if message.case_id != case_uuid:
                continue

            statistics["processed_messages"] += 1

            text = message.text or ""
            if not text.strip():
                continue

            statistics["messages_with_text"] += 1

            candidates = self.extract_text(text)
            statistics["extracted_candidates"] += len(candidates)

            if not candidates:
                continue

            origin = self._message_origin(
                case_id=case_uuid,
                message=message,
            )

            persisted_candidates: list[
                tuple[ExtractionCandidate, Entity]
            ] = []

            for candidate in candidates:
                status, entity = self._persist_candidate(
                    case_id=case_uuid,
                    candidate=candidate,
                    origin=origin,
                )

                type_name = candidate.entity_type.value

                if status == "created":
                    statistics["created_entities"] += 1
                    self._increment_type_counter(
                        statistics["created_by_type"],
                        type_name,
                    )
                elif status == "existing":
                    statistics["existing_entities"] += 1
                    self._increment_type_counter(
                        statistics["existing_by_type"],
                        type_name,
                    )
                elif status == "oversized":
                    statistics["skipped_oversized"] += 1
                else:
                    statistics["skipped_invalid"] += 1

                if entity is not None:
                    persisted_candidates.append(
                        (candidate, entity)
                    )

            if not persisted_candidates:
                continue

            evidence, evidence_status = self._ensure_message_evidence(
                message=message,
                origin=origin,
                candidates=[
                    candidate
                    for candidate, _entity
                    in persisted_candidates
                ],
            )

            if evidence_status == "created":
                statistics["provenance_evidence_created"] += 1
            elif evidence_status == "existing":
                statistics["provenance_evidence_existing"] += 1
            else:
                statistics["provenance_evidence_unavailable"] += 1

            if evidence is None or self.evidence_link_service is None:
                continue

            linked_entity_ids: set[UUID] = set()

            for _candidate, entity in persisted_candidates:
                entity_id = getattr(entity, "id", None)

                if not isinstance(entity_id, UUID):
                    continue

                # Multiple textual occurrences of the same normalized
                # Entity in one message still require only one link.
                if entity_id in linked_entity_ids:
                    continue

                linked_entity_ids.add(entity_id)

                _link, created = self.evidence_link_service.ensure_link(
                    evidence_id=evidence.id,
                    entity_id=entity_id,
                )

                if created:
                    statistics["evidence_links_created"] += 1
                else:
                    statistics["evidence_links_existing"] += 1

        return statistics

    # ==========================================================
    # Persistence
    # ==========================================================

    def _persist_candidate(
        self,
        *,
        case_id: UUID,
        candidate: ExtractionCandidate,
        origin: ExtractionOrigin,
    ) -> tuple[str, Entity | None]:
        """Persist one candidate idempotently inside the case."""

        value = candidate.value.strip()
        normalized_value = candidate.normalized_value.strip()

        if not value or not normalized_value:
            return "invalid", None

        if (
            len(value) > self.MAX_ENTITY_VALUE_LENGTH
            or len(normalized_value) > self.MAX_ENTITY_VALUE_LENGTH
        ):
            return "oversized", None

        metadata = {
            "extraction": {
                "source": self._origin_source_name(origin),
                "extractor": self.identifier_extractor.name,
                **origin.to_metadata(),
            },
            "analyzer_metadata": dict(candidate.metadata),
        }

        metadata_json = json.dumps(
            metadata,
            ensure_ascii=False,
            default=str,
        )

        # Production EntityService owns the canonical identity boundary:
        # normalization -> exact case-scoped lookup -> create-if-missing.
        # Keeping this decision in EntityService prevents extraction from
        # using a different normalization contract than Entity Resolution.
        resolve_or_create = getattr(
            self.entity_service,
            "resolve_or_create_entity",
            None,
        )

        if callable(resolve_or_create):
            entity, created = resolve_or_create(
                case_id=case_id,
                entity_type=candidate.entity_type,
                value=value,
                normalized_value=normalized_value,
                confidence=candidate.confidence,
                metadata_json=metadata_json,
            )

            return (
                "created" if created else "existing",
                entity,
            )

        # Compatibility path for small test doubles / legacy adapters.
        # Real application wiring always uses EntityService above.
        existing = self.entity_service.repository.find_in_case(
            case_id=case_id,
            entity_type=candidate.entity_type,
            normalized_value=normalized_value,
        )

        if existing is not None:
            return "existing", existing

        entity = self.entity_service.create_entity(
            case_id=case_id,
            entity_type=candidate.entity_type,
            value=value,
            normalized_value=normalized_value,
            confidence=candidate.confidence,
            metadata_json=metadata_json,
        )

        return "created", entity

    # ==========================================================
    # Provenance / Evidence
    # ==========================================================

    def _ensure_message_evidence(
        self,
        *,
        message: Message,
        origin: ExtractionOrigin,
        candidates: list[ExtractionCandidate],
    ) -> tuple[Evidence | None, str]:
        """Ensure one MESSAGE Evidence object represents the message."""

        if self.evidence_service is None:
            return None, "unavailable"

        evidence: Evidence | None = None
        evidence_status = "existing"

        message_evidence_id = getattr(message, "evidence_id", None)

        if isinstance(message_evidence_id, UUID):
            evidence = self.evidence_service.get_evidence(
                message_evidence_id
            )

        if evidence is None:
            message_data = {
                "source_id": message.source_id,
                "sender": getattr(message, "sender", None),
                "receiver": getattr(message, "receiver", None),
                "chat_name": getattr(message, "chat_name", None),
                "sent_at": getattr(message, "sent_at", None),
                "external_id": getattr(message, "external_id", None),
                "text": getattr(message, "text", None),
            }

            evidence = self.evidence_service.create_from_message(
                case_id=origin.case_id,
                message_data=message_data,
                metadata_json=self._build_provenance_metadata_json(
                    origin=origin,
                    candidates=candidates,
                ),
                # Message itself is already indexed. Creating a second
                # SearchIndex row for provenance-only Evidence would
                # duplicate the same text in search results.
                update_search_index=False,
            )

            message.evidence_id = evidence.id

            if self.session is not None:
                self.session.flush()

            evidence_status = "created"
        else:
            merged_metadata = self._merge_provenance_metadata(
                existing_metadata_json=evidence.metadata_json,
                origin=origin,
                candidates=candidates,
            )

            if merged_metadata != evidence.metadata_json:
                self.evidence_service.update_metadata(
                    evidence.id,
                    merged_metadata,
                )

        return evidence, evidence_status

    def _build_provenance_metadata_json(
        self,
        *,
        origin: ExtractionOrigin,
        candidates: list[ExtractionCandidate],
    ) -> str:
        payload = {
            "extraction_provenance": self._provenance_payload(
                origin=origin,
                candidates=candidates,
            )
        }

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )

    def _merge_provenance_metadata(
        self,
        *,
        existing_metadata_json: str | None,
        origin: ExtractionOrigin,
        candidates: list[ExtractionCandidate],
    ) -> str:
        try:
            payload = json.loads(existing_metadata_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}

        if not isinstance(payload, dict):
            payload = {}

        payload["extraction_provenance"] = self._provenance_payload(
            origin=origin,
            candidates=candidates,
        )

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )

    def _provenance_payload(
        self,
        *,
        origin: ExtractionOrigin,
        candidates: list[ExtractionCandidate],
    ) -> dict[str, Any]:
        return {
            "extractor": self.identifier_extractor.name,
            "origin": origin.to_metadata(),
            "candidates": [
                {
                    "entity_type": candidate.entity_type.value,
                    "value": candidate.value,
                    "normalized_value": candidate.normalized_value,
                    "confidence": candidate.confidence,
                    "metadata": dict(candidate.metadata),
                }
                for candidate in candidates
            ],
        }

    # ==========================================================
    # Source adapters
    # ==========================================================

    def _load_messages(
        self,
        *,
        case_id: UUID,
        source_id: UUID | None,
    ) -> list[Message]:
        if source_id is not None:
            return self.message_repository.get_by_source(source_id)

        return self.message_repository.get_by_case(case_id)

    @staticmethod
    def _message_origin(
        *,
        case_id: UUID,
        message: Message,
    ) -> ExtractionOrigin:
        return ExtractionOrigin(
            case_id=case_id,
            object_type=ExtractionObjectType.MESSAGE,
            source_id=message.source_id,
            object_id=message.id,
            evidence_id=message.evidence_id,
            external_id=message.external_id,
            sender=message.sender,
            chat_name=message.chat_name,
        )

    @staticmethod
    def _origin_source_name(
        origin: ExtractionOrigin,
    ) -> str:
        if origin.object_type == ExtractionObjectType.MESSAGE:
            return "message_text"

        return origin.object_type.value

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _increment_type_counter(
        counter: dict[str, int],
        type_name: str,
    ) -> None:
        counter[type_name] = counter.get(type_name, 0) + 1

    @staticmethod
    def _normalize_uuid(
        value: str | UUID,
        *,
        field_name: str,
    ) -> UUID:
        if isinstance(value, UUID):
            return value

        try:
            return UUID(str(value))
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError(
                f"{field_name} must contain a valid UUID."
            ) from error

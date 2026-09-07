"""Block 10.6 regression tests for extraction provenance and Evidence links."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID
from uuid import uuid4

from app.models.entity import EntityType
from app.processing.extraction import ExtractionCandidate
from app.services.unified_extraction_service import UnifiedExtractionService


class StubIdentifierExtractor:
    name = "StubIdentifierExtractor"

    def extract(self, text):
        results = []

        if text and "PHONE" in text:
            results.append(
                ExtractionCandidate(
                    entity_type=EntityType.PHONE,
                    value="+380 67 123 45 67",
                    normalized_value="380671234567",
                    confidence=0.95,
                    metadata={"identifier_kind": "phone"},
                )
            )

        if text and "EMAIL" in text:
            results.append(
                ExtractionCandidate(
                    entity_type=EntityType.EMAIL,
                    value="alice@example.com",
                    normalized_value="alice@example.com",
                    confidence=0.95,
                    metadata={"identifier_kind": "email"},
                )
            )

        return results


class FakeEntityRepository:
    def __init__(self):
        self.entities = {}

    def find_in_case(self, case_id, entity_type, normalized_value):
        return self.entities.get(
            (case_id, entity_type, normalized_value)
        )


class FakeEntityService:
    def __init__(self):
        self.repository = FakeEntityRepository()
        self.created = []

    def create_entity(self, **kwargs):
        entity = SimpleNamespace(id=uuid4(), **kwargs)
        self.created.append(entity)
        self.repository.entities[
            (
                kwargs["case_id"],
                kwargs["entity_type"],
                kwargs["normalized_value"],
            )
        ] = entity
        return entity


class FakeMessageRepository:
    def __init__(self, messages):
        self.messages = list(messages)

    def get_by_case(self, case_id):
        return [
            message
            for message in self.messages
            if message.case_id == case_id
        ]

    def get_by_source(self, source_id):
        return [
            message
            for message in self.messages
            if message.source_id == source_id
        ]


class FakeEvidenceService:
    def __init__(self):
        self.evidences = {}
        self.created_count = 0
        self.update_count = 0

    def create_from_message(
        self,
        case_id,
        message_data,
        *,
        metadata_json=None,
        update_search_index=True,
    ):
        evidence = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            source_id=message_data["source_id"],
            metadata_json=metadata_json,
            update_search_index=update_search_index,
        )
        self.evidences[evidence.id] = evidence
        self.created_count += 1
        return evidence

    def get_evidence(self, evidence_id):
        return self.evidences.get(evidence_id)

    def update_metadata(self, evidence_id, metadata_json):
        evidence = self.evidences[evidence_id]
        evidence.metadata_json = metadata_json
        self.update_count += 1
        return evidence


class FakeEvidenceLinkService:
    def __init__(self):
        self.links = {}

    def ensure_link(self, evidence_id, entity_id):
        key = (evidence_id, entity_id)

        if key in self.links:
            return self.links[key], False

        link = SimpleNamespace(
            id=uuid4(),
            evidence_id=evidence_id,
            entity_id=entity_id,
        )
        self.links[key] = link
        return link, True


class FakeSession:
    def __init__(self):
        self.flush_count = 0

    def flush(self):
        self.flush_count += 1


def _message(case_id, source_id, text, external_id):
    return SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        source_id=source_id,
        evidence_id=None,
        external_id=external_id,
        sender="Alice",
        receiver=None,
        chat_name="Test chat",
        sent_at=None,
        text=text,
    )


def _service(messages):
    session = FakeSession()
    entity_service = FakeEntityService()
    evidence_service = FakeEvidenceService()
    evidence_link_service = FakeEvidenceLinkService()

    service = UnifiedExtractionService(
        session=session,
        entity_service=entity_service,
        identifier_extractor=StubIdentifierExtractor(),
        message_repository=FakeMessageRepository(messages),
        evidence_service=evidence_service,
        evidence_link_service=evidence_link_service,
    )

    return (
        service,
        session,
        entity_service,
        evidence_service,
        evidence_link_service,
    )


def test_same_entity_in_two_messages_keeps_two_occurrence_evidences():
    case_id = uuid4()
    source_id = uuid4()
    messages = [
        _message(case_id, source_id, "PHONE first", "1"),
        _message(case_id, source_id, "PHONE second", "2"),
    ]

    (
        service,
        _session,
        entity_service,
        evidence_service,
        evidence_link_service,
    ) = _service(messages)

    result = service.extract_case_messages(
        case_id=case_id,
        source_id=source_id,
    )

    assert result["created_entities"] == 1
    assert result["existing_entities"] == 1
    assert result["provenance_evidence_created"] == 2
    assert result["evidence_links_created"] == 2

    assert len(entity_service.created) == 1
    assert evidence_service.created_count == 2
    assert len(evidence_link_service.links) == 2

    assert isinstance(messages[0].evidence_id, UUID)
    assert isinstance(messages[1].evidence_id, UUID)
    assert messages[0].evidence_id != messages[1].evidence_id


def test_rerun_reuses_evidence_and_links_idempotently():
    case_id = uuid4()
    source_id = uuid4()
    messages = [
        _message(case_id, source_id, "PHONE first", "1"),
        _message(case_id, source_id, "PHONE second", "2"),
    ]

    (
        service,
        _session,
        _entity_service,
        evidence_service,
        evidence_link_service,
    ) = _service(messages)

    first = service.extract_case_messages(
        case_id=case_id,
        source_id=source_id,
    )

    evidence_ids = [message.evidence_id for message in messages]

    second = service.extract_case_messages(
        case_id=case_id,
        source_id=source_id,
    )

    assert first["provenance_evidence_created"] == 2
    assert first["evidence_links_created"] == 2

    assert second["created_entities"] == 0
    assert second["existing_entities"] == 2
    assert second["provenance_evidence_created"] == 0
    assert second["provenance_evidence_existing"] == 2
    assert second["evidence_links_created"] == 0
    assert second["evidence_links_existing"] == 2

    assert [message.evidence_id for message in messages] == evidence_ids
    assert evidence_service.created_count == 2
    assert len(evidence_link_service.links) == 2


def test_one_message_with_two_entities_creates_one_evidence_and_two_links():
    case_id = uuid4()
    source_id = uuid4()
    message = _message(
        case_id,
        source_id,
        "PHONE and EMAIL",
        "42",
    )

    (
        service,
        _session,
        entity_service,
        evidence_service,
        evidence_link_service,
    ) = _service([message])

    result = service.extract_case_messages(
        case_id=case_id,
        source_id=source_id,
    )

    assert result["created_entities"] == 2
    assert result["provenance_evidence_created"] == 1
    assert result["evidence_links_created"] == 2
    assert len(entity_service.created) == 2
    assert evidence_service.created_count == 1
    assert len(evidence_link_service.links) == 2

    evidence = evidence_service.evidences[message.evidence_id]
    metadata = json.loads(evidence.metadata_json)
    provenance = metadata["extraction_provenance"]

    assert provenance["origin"]["object_type"] == "message"
    assert provenance["origin"]["object_id"] == str(message.id)
    assert provenance["origin"]["source_id"] == str(source_id)
    assert provenance["origin"]["external_id"] == "42"
    assert provenance["extractor"] == "StubIdentifierExtractor"

    candidate_types = {
        candidate["entity_type"]
        for candidate in provenance["candidates"]
    }
    assert candidate_types == {"phone", "email"}

    # Provenance-only MESSAGE Evidence must not duplicate the Message
    # itself in SearchIndex.
    assert evidence.update_search_index is False


def test_existing_evidence_metadata_is_preserved_when_provenance_is_added():
    case_id = uuid4()
    source_id = uuid4()
    message = _message(case_id, source_id, "PHONE", "7")

    (
        service,
        _session,
        _entity_service,
        evidence_service,
        evidence_link_service,
    ) = _service([message])

    existing_id = uuid4()
    existing = SimpleNamespace(
        id=existing_id,
        case_id=case_id,
        source_id=source_id,
        metadata_json=json.dumps(
            {"manual_tag": "keep-me"},
            ensure_ascii=False,
        ),
    )
    evidence_service.evidences[existing_id] = existing
    message.evidence_id = existing_id

    result = service.extract_case_messages(
        case_id=case_id,
        source_id=source_id,
    )

    assert result["provenance_evidence_existing"] == 1
    assert result["evidence_links_created"] == 1
    assert evidence_service.created_count == 0
    assert evidence_service.update_count == 1
    assert len(evidence_link_service.links) == 1

    metadata = json.loads(existing.metadata_json)
    assert metadata["manual_tag"] == "keep-me"
    assert "extraction_provenance" in metadata


def test_message_without_candidates_does_not_create_provenance_evidence():
    case_id = uuid4()
    source_id = uuid4()
    message = _message(case_id, source_id, "ordinary text", "8")

    (
        service,
        _session,
        _entity_service,
        evidence_service,
        evidence_link_service,
    ) = _service([message])

    result = service.extract_case_messages(
        case_id=case_id,
        source_id=source_id,
    )

    assert result["extracted_candidates"] == 0
    assert result["provenance_evidence_created"] == 0
    assert result["evidence_links_created"] == 0
    assert evidence_service.created_count == 0
    assert len(evidence_link_service.links) == 0
    assert message.evidence_id is None

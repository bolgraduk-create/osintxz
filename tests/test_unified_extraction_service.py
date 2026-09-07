"""Block 10.3 regression tests for the unified extraction layer."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from app.models.entity import EntityType
from app.processing.extraction import ExtractionCandidate
from app.services.unified_extraction_service import UnifiedExtractionService


class StubIdentifierExtractor:
    name = "StubIdentifierExtractor"

    def extract(self, text):
        if not text or "PHONE" not in text:
            return []

        return [
            ExtractionCandidate(
                entity_type=EntityType.PHONE,
                value="+380 67 123 45 67",
                normalized_value="380671234567",
                confidence=0.9,
                metadata={"test": True},
            )
        ]


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
        entity = SimpleNamespace(**kwargs)
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


def _message(case_id, source_id, text, external_id):
    return SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        source_id=source_id,
        evidence_id=None,
        external_id=external_id,
        sender="Alice",
        chat_name="Test chat",
        text=text,
    )


def test_extract_case_messages_is_case_scoped_and_idempotent():
    case_id = uuid4()
    source_id = uuid4()

    messages = [
        _message(case_id, source_id, "PHONE first", "1"),
        _message(case_id, source_id, "PHONE second", "2"),
    ]

    entity_service = FakeEntityService()

    service = UnifiedExtractionService(
        session=None,
        entity_service=entity_service,
        identifier_extractor=StubIdentifierExtractor(),
        message_repository=FakeMessageRepository(messages),
    )

    result = service.extract_case_messages(
        case_id=case_id,
        source_id=source_id,
    )

    assert result["processed_messages"] == 2
    assert result["extracted_candidates"] == 2
    assert result["created_entities"] == 1
    assert result["existing_entities"] == 1
    assert result["created_by_type"] == {"phone": 1}
    assert result["existing_by_type"] == {"phone": 1}


def test_created_entity_contains_message_provenance():
    case_id = uuid4()
    source_id = uuid4()
    message = _message(case_id, source_id, "PHONE", "42")

    entity_service = FakeEntityService()

    service = UnifiedExtractionService(
        session=None,
        entity_service=entity_service,
        identifier_extractor=StubIdentifierExtractor(),
        message_repository=FakeMessageRepository([message]),
    )

    result = service.extract_case_messages(
        case_id=case_id,
        source_id=source_id,
    )

    assert result["created_entities"] == 1

    created = entity_service.created[0]
    metadata = json.loads(created.metadata_json)

    extraction = metadata["extraction"]

    assert extraction["source"] == "message_text"
    assert extraction["extractor"] == "StubIdentifierExtractor"
    assert extraction["object_type"] == "message"
    assert extraction["object_id"] == str(message.id)
    assert extraction["source_id"] == str(source_id)
    assert extraction["external_id"] == "42"
    assert extraction["sender"] == "Alice"
    assert extraction["chat_name"] == "Test chat"

"""Block 10.7 regression tests: Extraction -> Entity Resolution boundary."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.entity_resolution.comparator import EntityComparator
from app.entity_resolution.normalizer import EntityNormalizer
from app.models.entity import EntityType
from app.processing.extraction import ExtractionCandidate
from app.services.entity_service import EntityService
from app.services.unified_extraction_service import UnifiedExtractionService


class InMemoryEntityRepository:
    def __init__(self):
        self.entities = {}

    def find_in_case(self, case_id, entity_type, normalized_value):
        return self.entities.get((case_id, entity_type, normalized_value))

    def create(self, entity):
        if entity.id is None:
            entity.id = uuid4()
        self.entities[
            (entity.case_id, entity.entity_type, entity.normalized_value)
        ] = entity
        return entity


def _entity_service():
    service = EntityService.__new__(EntityService)
    service.normalizer = EntityNormalizer()
    service.repository = InMemoryEntityRepository()
    return service


def test_exact_resolution_uses_canonical_phone_before_lookup():
    service = _entity_service()
    case_id = uuid4()

    first, first_created = service.resolve_or_create_entity(
        case_id=case_id,
        entity_type=EntityType.PHONE,
        value="+380 (67) 123-45-67",
        normalized_value="+380 (67) 123-45-67",
    )
    second, second_created = service.resolve_or_create_entity(
        case_id=case_id,
        entity_type=EntityType.PHONE,
        value="380671234567",
        normalized_value="380671234567",
    )

    assert first_created is True
    assert second_created is False
    assert second is first
    assert first.normalized_value == "380671234567"
    assert len(service.repository.entities) == 1


def test_exact_resolution_reuses_username_display_variants():
    service = _entity_service()
    case_id = uuid4()

    first, first_created = service.resolve_or_create_entity(
        case_id=case_id,
        entity_type=EntityType.USERNAME,
        value="@Alice",
    )
    second, second_created = service.resolve_or_create_entity(
        case_id=case_id,
        entity_type=EntityType.USERNAME,
        value="alice",
    )

    assert first_created is True
    assert second_created is False
    assert second is first
    assert first.normalized_value == "alice"


def test_exact_resolution_reuses_bank_card_formatting_variants():
    service = _entity_service()
    case_id = uuid4()

    first, first_created = service.resolve_or_create_entity(
        case_id=case_id,
        entity_type=EntityType.BANK_CARD,
        value="1234 5678 9012 3452",
    )
    second, second_created = service.resolve_or_create_entity(
        case_id=case_id,
        entity_type=EntityType.BANK_CARD,
        value="1234-5678-9012-3452",
    )

    assert first_created is True
    assert second_created is False
    assert second is first
    assert first.normalized_value == "1234567890123452"


def test_exact_resolution_remains_case_scoped():
    service = _entity_service()
    first_case = uuid4()
    second_case = uuid4()

    first, first_created = service.resolve_or_create_entity(
        case_id=first_case,
        entity_type=EntityType.EMAIL,
        value="Alice@Example.com",
    )
    second, second_created = service.resolve_or_create_entity(
        case_id=second_case,
        entity_type=EntityType.EMAIL,
        value="alice@example.com",
    )

    assert first_created is True
    assert second_created is True
    assert first is not second
    assert len(service.repository.entities) == 2


class StubExtractor:
    name = "Block107StubExtractor"

    def extract(self, text):
        if not text:
            return []
        return [
            ExtractionCandidate(
                entity_type=EntityType.USERNAME,
                value="@Alice",
                # Deliberately non-canonical. The EntityService boundary
                # must canonicalize it before identity lookup.
                normalized_value="@@ALICE",
                confidence=0.9,
                metadata={"test": True},
            )
        ]


class FakeMessageRepository:
    def __init__(self, message):
        self.message = message

    def get_by_case(self, case_id):
        return [self.message] if self.message.case_id == case_id else []

    def get_by_source(self, source_id):
        return [self.message] if self.message.source_id == source_id else []


def test_unified_extraction_delegates_identity_to_entity_service():
    entity_service = _entity_service()
    case_id = uuid4()
    source_id = uuid4()
    message = SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        source_id=source_id,
        evidence_id=None,
        external_id="107",
        sender="Alice",
        receiver=None,
        chat_name="Resolution test",
        sent_at=None,
        text="@Alice",
    )

    extraction = UnifiedExtractionService(
        session=None,
        entity_service=entity_service,
        identifier_extractor=StubExtractor(),
        message_repository=FakeMessageRepository(message),
    )

    first = extraction.extract_case_messages(
        case_id=case_id,
        source_id=source_id,
    )
    second = extraction.extract_case_messages(
        case_id=case_id,
        source_id=source_id,
    )

    assert first["created_entities"] == 1
    assert second["created_entities"] == 0
    assert second["existing_entities"] == 1
    assert len(entity_service.repository.entities) == 1

    entity = next(iter(entity_service.repository.entities.values()))
    assert entity.normalized_value == "alice"


def test_bank_card_exact_comparison_uses_shared_normalizer():
    comparator = EntityComparator()

    assert comparator.compare(
        EntityType.BANK_CARD,
        "1234 5678 9012 3452",
        "1234-5678-9012-3452",
    ) is True

    assert comparator.compare(
        EntityType.BANK_CARD,
        "1234 5678 9012 3452",
        "1234 5678 9012 3453",
    ) is False

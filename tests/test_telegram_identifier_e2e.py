"""Block 10.8: Telegram result.json -> Message -> Extraction -> Entity/Evidence E2E."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.collectors.telegram.telegram_collector import TelegramCollector
from app.entity_resolution.normalizer import EntityNormalizer
from app.models.entity import EntityType
from app.processing.extraction.identifier_extractor import IdentifierExtractor
from app.services.collection_service import CollectionService
from app.services.entity_service import EntityService
from app.services.telegram_import_service import TelegramImportService
from app.services.unified_extraction_service import UnifiedExtractionService


class InMemoryMessageRepository:
    def __init__(self):
        self.messages = []

    def get_by_case(self, case_id):
        return [m for m in self.messages if m.case_id == case_id]

    def get_by_source(self, source_id):
        return [m for m in self.messages if m.source_id == source_id]


class InMemoryMessageService:
    def __init__(self, repository):
        self.repository = repository

    def create_message(self, **kwargs):
        message = SimpleNamespace(id=uuid4(), **kwargs)
        # update_search_index is a service option, not a Message field.
        if hasattr(message, "update_search_index"):
            delattr(message, "update_search_index")
        self.repository.messages.append(message)
        return message


class InMemoryEntityRepository:
    def __init__(self):
        self.entities = {}

    def find_in_case(self, case_id, entity_type, normalized_value):
        return self.entities.get((case_id, entity_type, normalized_value))

    def create(self, entity):
        if entity.id is None:
            entity.id = uuid4()
        self.entities[(entity.case_id, entity.entity_type, entity.normalized_value)] = entity
        return entity


class InMemoryEvidenceService:
    def __init__(self):
        self.evidences = {}

    def create_from_message(self, case_id, message_data, *, metadata_json=None, update_search_index=True):
        evidence = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            source_id=message_data["source_id"],
            metadata_json=metadata_json,
        )
        self.evidences[evidence.id] = evidence
        return evidence

    def get_evidence(self, evidence_id):
        return self.evidences.get(evidence_id)

    def update_metadata(self, evidence_id, metadata_json):
        evidence = self.evidences[evidence_id]
        evidence.metadata_json = metadata_json
        return evidence


class InMemoryEvidenceLinkService:
    def __init__(self):
        self.links = {}

    def ensure_link(self, evidence_id, entity_id):
        key = (evidence_id, entity_id)
        if key in self.links:
            return self.links[key], False
        link = SimpleNamespace(id=uuid4(), evidence_id=evidence_id, entity_id=entity_id)
        self.links[key] = link
        return link, True


class InMemorySourceService:
    def __init__(self):
        self.sources = []

    def create_source(self, **kwargs):
        source = SimpleNamespace(id=uuid4(), **kwargs)
        self.sources.append(source)
        return source


class NoopObjectService:
    def create_document(self, **kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)

    def create_artifact(self, **kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)


class NoopCollectionEvidenceService:
    def create_evidence(self, **kwargs):
        return SimpleNamespace(id=uuid4(), **kwargs)


class StageStatsStub:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def import_entities(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.payload)

    def import_relationships(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.payload)

    def import_events(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.payload)

    def import_reports(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.payload)


class SearchIndexingStub:
    def __init__(self):
        self.case_ids = []

    def index_case(self, case_id):
        self.case_ids.append(case_id)
        empty = SimpleNamespace(processed=0, created=0, updated=0, skipped=0, failed=0)
        embeddings = SimpleNamespace(processed=0, created_or_updated=0, skipped=0, failed=0)
        return SimpleNamespace(search_indexes=empty, embeddings=embeddings, successful=True)


class FakeSession:
    def __init__(self):
        self.flush_count = 0

    def flush(self):
        self.flush_count += 1


def _write_export(root: Path) -> Path:
    payload = {
        "about": "Telegram Desktop",
        "chats": {
            "list": [
                {
                    "name": "Identifier E2E",
                    "type": "private",
                    "id": 777,
                    "messages": [
                        {
                            "id": 1,
                            "type": "message",
                            "date": "2026-08-30T10:00:00",
                            "from": "Alice",
                            "from_id": "user1",
                            "text": [
                                "Phone: ",
                                {"type": "phone", "text": "+380 (67) 123-45-67"},
                            ],
                        },
                        {
                            "id": 2,
                            "type": "message",
                            "date": "2026-08-30T10:01:00",
                            "from": "Alice",
                            "from_id": "user1",
                            "text": "Same phone again: 380671234567",
                        },
                        {
                            "id": 3,
                            "type": "message",
                            "date": "2026-08-30T10:02:00",
                            "from": "Bob",
                            "from_id": "user2",
                            "text": "Card number: 1234 5678 9012 3452",
                        },
                        {
                            "id": 4,
                            "type": "message",
                            "date": "2026-08-30T10:03:00",
                            "from": "Bob",
                            "from_id": "user2",
                            "text": "Contact: alice@example.com and @Alice_01",
                        },
                    ],
                }
            ]
        },
    }

    result_json = root / "result.json"
    result_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return result_json


def _build_import_service():
    case_id = uuid4()
    message_repository = InMemoryMessageRepository()
    message_service = InMemoryMessageService(message_repository)
    source_service = InMemorySourceService()

    collection_service = CollectionService(
        source_service=source_service,
        evidence_service=NoopCollectionEvidenceService(),
        message_service=message_service,
        document_service=NoopObjectService(),
        artifact_service=NoopObjectService(),
    )

    entity_service = EntityService.__new__(EntityService)
    entity_service.normalizer = EntityNormalizer()
    entity_service.repository = InMemoryEntityRepository()

    evidence_service = InMemoryEvidenceService()
    evidence_link_service = InMemoryEvidenceLinkService()

    extraction_service = UnifiedExtractionService(
        session=FakeSession(),
        entity_service=entity_service,
        identifier_extractor=IdentifierExtractor(),
        message_repository=message_repository,
        evidence_service=evidence_service,
        evidence_link_service=evidence_link_service,
    )

    entity_stage = StageStatsStub({"found": 0, "created": 0, "skipped": 0})
    relationship_stage = StageStatsStub({"found": 0, "created": 0, "skipped": 0, "unresolved": 0})
    timeline_stage = StageStatsStub({"found": 0, "created": 0, "skipped": 0, "unresolved": 0})
    report_stage = StageStatsStub({"found": 0, "created": 0, "updated": 0, "skipped": 0, "report_id": None})
    search_stage = SearchIndexingStub()

    importer = TelegramImportService(
        collector=TelegramCollector(),
        collection_service=collection_service,
        extraction_service=extraction_service,
        source_service=source_service,
        entity_import_service=entity_stage,
        relationship_import_service=relationship_stage,
        timeline_import_service=timeline_stage,
        report_import_service=report_stage,
        search_indexing_service=search_stage,
    )

    return SimpleNamespace(
        case_id=case_id,
        importer=importer,
        messages=message_repository,
        entities=entity_service.repository,
        evidences=evidence_service,
        links=evidence_link_service,
        search=search_stage,
    )


def test_telegram_result_json_full_identifier_pipeline(tmp_path):
    export_dir = tmp_path / "telegram_export"
    export_dir.mkdir()
    _write_export(export_dir)

    runtime = _build_import_service()
    result = runtime.importer.import_export(runtime.case_id, export_dir)

    # Parser -> Collector -> CollectionService
    assert result["items_imported"] == 4
    assert len(runtime.messages.messages) == 4
    assert runtime.messages.messages[0].text == "Phone: +380 (67) 123-45-67"
    assert runtime.messages.messages[0].external_id == "1"

    # Unified Extraction -> canonical Entity Resolution
    assert result["identifiers_found"] == 5
    assert result["identifiers_created"] == 4
    assert result["identifiers_existing"] == 1

    entities = list(runtime.entities.entities.values())
    by_type = {}
    for entity in entities:
        by_type.setdefault(entity.entity_type, []).append(entity)

    assert [e.normalized_value for e in by_type[EntityType.PHONE]] == ["380671234567"]
    assert [e.normalized_value for e in by_type[EntityType.BANK_CARD]] == ["1234567890123452"]
    assert [e.normalized_value for e in by_type[EntityType.EMAIL]] == ["alice@example.com"]
    assert [e.normalized_value for e in by_type[EntityType.USERNAME]] == ["alice_01"]

    # Provenance: four messages contain identifiers, but repeated PHONE
    # remains one Entity while retaining two occurrence evidences.
    assert result["identifier_provenance_evidence_created"] == 4
    assert result["identifier_evidence_links_created"] == 5
    assert len(runtime.evidences.evidences) == 4
    assert len(runtime.links.links) == 5
    assert all(message.evidence_id is not None for message in runtime.messages.messages)

    # Telegram importer still finalizes Search indexing after extraction.
    assert result["search_indexing_successful"] is True
    assert runtime.search.case_ids == [runtime.case_id]

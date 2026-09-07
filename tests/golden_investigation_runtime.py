"""Deterministic runtime used by the Stage 23 golden investigation fixture."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.collectors.telegram.telegram_collector import TelegramCollector
from app.entity_resolution.normalizer import EntityNormalizer
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

    def search_case_structured(
        self,
        case_id,
        *,
        entity_types=(),
        object_ids=(),
        values=(),
        normalized_values=(),
        include_deleted=False,
        limit=200,
    ):
        rows = [entity for entity in self.entities.values() if entity.case_id == case_id]
        if entity_types:
            rows = [entity for entity in rows if entity.entity_type in entity_types]
        if object_ids:
            rows = [entity for entity in rows if entity.id in object_ids]
        if values:
            rows = [entity for entity in rows if entity.value in values]
        if normalized_values:
            rows = [entity for entity in rows if entity.normalized_value in normalized_values]
        if not include_deleted:
            rows = [entity for entity in rows if getattr(entity, "deleted_at", None) is None]
        return rows[:limit]


class InMemoryEvidenceService:
    def __init__(self):
        self.evidences = {}

    def create_from_message(self, case_id, message_data, *, metadata_json=None, update_search_index=True):
        evidence = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            source_id=message_data["source_id"],
            evidence_type=SimpleNamespace(value="message"),
            title=f"Message {message_data.get('external_id') or ''}".strip(),
            value=message_data.get("text"),
            file_path=None,
            sha256=None,
            metadata_json=metadata_json,
            deleted_at=None,
            created_at=None,
        )
        self.evidences[evidence.id] = evidence
        return evidence

    def get_evidence(self, evidence_id):
        return self.evidences.get(evidence_id)

    def update_metadata(self, evidence_id, metadata_json):
        evidence = self.evidences[evidence_id]
        evidence.metadata_json = metadata_json
        return evidence


class InMemoryEvidenceRepository:
    def __init__(self, evidence_service):
        self.evidence_service = evidence_service

    def search_case_structured(
        self,
        case_id,
        *,
        evidence_types=(),
        object_ids=(),
        source_ids=(),
        values=(),
        include_deleted=False,
        limit=200,
    ):
        rows = [e for e in self.evidence_service.evidences.values() if e.case_id == case_id]
        if evidence_types:
            allowed = {getattr(value, "value", value) for value in evidence_types}
            rows = [e for e in rows if getattr(e.evidence_type, "value", e.evidence_type) in allowed]
        if object_ids:
            rows = [e for e in rows if e.id in object_ids]
        if source_ids:
            rows = [e for e in rows if e.source_id in source_ids]
        if values:
            rows = [e for e in rows if e.value in values]
        return rows[:limit]


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
        source = SimpleNamespace(id=uuid4(), checksum="golden-fixture-checksum", **kwargs)
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

    def import_entities(self, **kwargs):
        return dict(self.payload)

    def import_relationships(self, **kwargs):
        return dict(self.payload)

    def import_events(self, **kwargs):
        return dict(self.payload)

    def import_reports(self, **kwargs):
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
    def flush(self):
        return None


def build_golden_runtime():
    case_id = uuid4()
    messages = InMemoryMessageRepository()
    message_service = InMemoryMessageService(messages)
    sources = InMemorySourceService()

    collection_service = CollectionService(
        source_service=sources,
        evidence_service=NoopCollectionEvidenceService(),
        message_service=message_service,
        document_service=NoopObjectService(),
        artifact_service=NoopObjectService(),
    )

    entity_service = EntityService.__new__(EntityService)
    entity_service.normalizer = EntityNormalizer()
    entity_service.repository = InMemoryEntityRepository()

    evidences = InMemoryEvidenceService()
    links = InMemoryEvidenceLinkService()

    extraction = UnifiedExtractionService(
        session=FakeSession(),
        entity_service=entity_service,
        identifier_extractor=IdentifierExtractor(),
        message_repository=messages,
        evidence_service=evidences,
        evidence_link_service=links,
    )

    importer = TelegramImportService(
        collector=TelegramCollector(),
        collection_service=collection_service,
        extraction_service=extraction,
        source_service=sources,
        entity_import_service=StageStatsStub({"found": 0, "created": 0, "skipped": 0}),
        relationship_import_service=StageStatsStub({"found": 0, "created": 0, "skipped": 0, "unresolved": 0}),
        timeline_import_service=StageStatsStub({"found": 0, "created": 0, "skipped": 0, "unresolved": 0}),
        report_import_service=StageStatsStub({"found": 0, "created": 0, "updated": 0, "skipped": 0, "report_id": None}),
        search_indexing_service=SearchIndexingStub(),
    )

    return SimpleNamespace(
        case_id=case_id,
        importer=importer,
        messages=messages,
        entities=entity_service.repository,
        evidences=evidences,
        evidence_repository=InMemoryEvidenceRepository(evidences),
        links=links,
        sources=sources,
    )

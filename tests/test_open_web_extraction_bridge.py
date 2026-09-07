from __future__ import annotations

from app.models.entity import EntityType
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebDocument, OpenWebQuery
from app.osint.open_web.extraction_bridge import OpenWebIdentifierExtractionBridge
from app.processing.extraction.contracts import ExtractionCandidate
from app.services.unified_extraction_service import UnifiedExtractionService


class StubExtractionService:
    def __init__(self, candidates=None, error=None):
        self.candidates = list(candidates or [])
        self.error = error
        self.inputs = []

    def extract_text(self, text):
        self.inputs.append(text)
        if self.error is not None:
            raise self.error
        return list(self.candidates)


def candidate(entity_type, value, normalized=None, confidence=0.9, metadata=None):
    return ExtractionCandidate(
        entity_type=entity_type,
        value=value,
        normalized_value=normalized or value,
        confidence=confidence,
        metadata=dict(metadata or {}),
    )


def document(**kwargs):
    values = dict(
        url="https://example.test/profile/alice",
        provider="fixture",
        title="Alice profile",
        snippet="Contact alice@example.com",
        text="Phone +380501234567",
        confidence=0.8,
        reliability=0.7,
        metadata={"fixture": True},
    )
    values.update(kwargs)
    return OpenWebDocument(**values)


def test_bridge_uses_unified_extraction_service_extract_text_contract():
    extraction = StubExtractionService()
    bridge = OpenWebIdentifierExtractionBridge(extraction)

    bridge.extract_document(document())

    assert len(extraction.inputs) == 1
    assert "https://example.test/profile/alice" not in extraction.inputs[0]
    assert "Alice profile" in extraction.inputs[0]
    assert "alice@example.com" in extraction.inputs[0]
    assert "+380501234567" in extraction.inputs[0]


def test_candidate_maps_to_standard_osint_finding_with_provenance():
    extraction = StubExtractionService(
        [
            candidate(
                EntityType.EMAIL,
                "Alice@Example.com",
                "alice@example.com",
                confidence=0.95,
                metadata={"extractor_rule": "email"},
            )
        ]
    )
    bridge = OpenWebIdentifierExtractionBridge(extraction)

    query = OpenWebQuery(
        target_type=OsintTargetType.USERNAME,
        value="alice",
        case_id="case-1",
        depth=1,
        parent_entity_id="entity-1",
    )

    result = bridge.extract_document(document(), query=query)

    assert result.total_findings == 1
    finding = result.findings[0]

    assert finding.category == EntityType.EMAIL.value
    assert finding.value == "Alice@Example.com"
    assert finding.source == "fixture"
    assert finding.url == "https://example.test/profile/alice"
    assert finding.confidence == 0.8
    assert finding.reliability == 0.7
    assert finding.metadata["workflow"] == "open_web_discovery"
    assert finding.metadata["lead_only"] is True
    assert finding.metadata["verified_ownership"] is False
    assert finding.metadata["normalized_value"] == "alice@example.com"
    assert finding.metadata["origin"]["target_type"] == "username"
    assert finding.metadata["origin"]["target_value"] == "alice"
    assert finding.metadata["origin"]["depth"] == 1
    assert finding.metadata["document"]["provider"] == "fixture"


def test_duplicate_normalized_candidates_inside_document_are_collapsed():
    extraction = StubExtractionService(
        [
            candidate(EntityType.EMAIL, "Alice@Example.com", "alice@example.com"),
            candidate(EntityType.EMAIL, "alice@example.com", "alice@example.com"),
        ]
    )
    bridge = OpenWebIdentifierExtractionBridge(extraction)

    result = bridge.extract_document(document())

    assert result.total_candidates == 1
    assert result.total_findings == 1
    assert result.skipped_duplicates == 1


def test_same_value_with_different_entity_types_is_not_collapsed():
    extraction = StubExtractionService(
        [
            candidate(EntityType.USERNAME, "alice", "alice"),
            candidate(EntityType.DOMAIN, "alice", "alice"),
        ]
    )

    result = OpenWebIdentifierExtractionBridge(
        extraction
    ).extract_document(document())

    assert result.total_findings == 2


def test_empty_document_does_not_call_extractor():
    extraction = StubExtractionService()

    result = OpenWebIdentifierExtractionBridge(
        extraction
    ).extract_document(
        OpenWebDocument(
            url="",
            provider="fixture",
        )
    )

    assert extraction.inputs == []
    assert result.total_findings == 0
    assert result.success is True


def test_one_document_extraction_failure_is_isolated_in_batch():
    class ConditionalExtractionService:
        def extract_text(self, text):
            if "bad.test" in text:
                raise RuntimeError("bad document")
            return [
                candidate(
                    EntityType.EMAIL,
                    "ok@example.com",
                    "ok@example.com",
                )
            ]

    bridge = OpenWebIdentifierExtractionBridge(
        ConditionalExtractionService()
    )

    batch = bridge.extract_documents(
        [
            document(url="https://bad.test", text="bad.test extraction fixture"),
            document(url="https://good.test"),
        ]
    )

    assert batch.failed_documents == 1
    assert batch.successful_documents == 1
    assert batch.total_findings == 1


def test_bridge_does_not_persist_or_recurse_by_itself():
    extraction = StubExtractionService(
        [
            candidate(
                EntityType.URL,
                "https://next.test",
                "https://next.test",
            )
        ]
    )
    bridge = OpenWebIdentifierExtractionBridge(extraction)

    result = bridge.extract_document(document())

    assert result.total_findings == 1
    assert not hasattr(bridge, "persistence_service")
    assert not hasattr(bridge, "recursive_service")
    assert not hasattr(bridge, "relationship_service")


def test_real_unified_extraction_service_api_is_compatible_with_bridge():
    class DummyEntityService:
        pass

    class DummyMessageRepository:
        pass

    extraction_service = UnifiedExtractionService(
        session=None,
        entity_service=DummyEntityService(),
        message_repository=DummyMessageRepository(),
    )

    bridge = OpenWebIdentifierExtractionBridge(extraction_service)

    result = bridge.extract_document(
        OpenWebDocument(
            url="https://example.org/contact",
            provider="fixture",
            text=(
                "Public contact: test@example.org "
                "phone +380501234567"
            ),
            confidence=1.0,
            reliability=1.0,
        )
    )

    finding_types = {
        finding.category
        for finding in result.findings
    }

    assert EntityType.EMAIL.value in finding_types
    assert EntityType.PHONE.value in finding_types
    assert EntityType.URL.value not in finding_types


def test_document_confidence_caps_candidate_confidence():
    extraction = StubExtractionService(
        [
            candidate(
                EntityType.EMAIL,
                "a@example.com",
                "a@example.com",
                confidence=0.99,
            )
        ]
    )

    result = OpenWebIdentifierExtractionBridge(
        extraction
    ).extract_document(
        document(confidence=0.55)
    )

    assert result.findings[0].confidence == 0.55

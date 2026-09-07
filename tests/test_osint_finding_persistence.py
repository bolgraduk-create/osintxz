from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

from app.models.entity import EntityType
from app.models.evidence import EvidenceType
from app.models.source import SourceType
from app.osint.capabilities import DiscoveryGoal, OSINT_CAPABILITY_CATALOG
from app.osint.enrichment_execution import (
    ConnectorExecutionRecord,
    EnrichmentExecutionResult,
    EnrichmentExecutionStatus,
)
from app.osint.finding_persistence import OsintFindingPersistenceService
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import (
    PivotDecision,
    PivotDecisionCode,
)
from app.osint.pivot_router import PivotRoute
from app.osint.result import OsintFinding, OsintResult, ResultStatus


class SourceRepositoryStub:
    def __init__(self):
        self.items = []

    def get_by_case(self, case_id):
        return [item for item in self.items if item.case_id == case_id]


class SourceServiceStub:
    def __init__(self):
        self.repository = SourceRepositoryStub()

    def create_source(
        self,
        case_id,
        name,
        source_type,
        path=None,
        description=None,
    ):
        item = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            name=name,
            source_type=source_type,
            path=path,
            original_path=path,
            description=description,
        )
        self.repository.items.append(item)
        return item


class EvidenceRepositoryStub:
    def __init__(self):
        self.items = []
        self.session = SimpleNamespace(flush=lambda: None)

    def get_by_source(self, source_id):
        return [item for item in self.items if item.source_id == source_id]


class EvidenceServiceStub:
    def __init__(self):
        self.repository = EvidenceRepositoryStub()

    def create_evidence(
        self,
        case_id,
        source_id,
        evidence_type,
        title,
        value=None,
        file_path=None,
        mime_type=None,
        description=None,
    ):
        item = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            source_id=source_id,
            evidence_type=evidence_type,
            title=title,
            value=value,
            file_path=file_path,
            mime_type=mime_type,
            description=description,
            metadata_json=None,
        )
        self.repository.items.append(item)
        return item


class NormalizerStub:
    def normalize(self, entity_type, value):
        value = str(value).strip()
        if entity_type is EntityType.USERNAME:
            return value.lstrip("@").casefold()
        return value.casefold()


class EntityRepositoryStub:
    def __init__(self):
        self.items = []

    def find_in_case(self, case_id, entity_type, normalized_value):
        for item in self.items:
            if (
                item.case_id == case_id
                and item.entity_type is entity_type
                and item.normalized_value == normalized_value
            ):
                return item
        return None


class EntityServiceStub:
    def __init__(self):
        self.repository = EntityRepositoryStub()
        self.normalizer = NormalizerStub()

    def resolve_or_create_entity(
        self,
        case_id,
        entity_type,
        value,
        confidence=1.0,
        metadata_json=None,
        description=None,
        **kwargs,
    ):
        normalized = self.normalizer.normalize(entity_type, value)
        existing = self.repository.find_in_case(
            case_id,
            entity_type,
            normalized,
        )
        if existing is not None:
            return existing, False

        item = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            entity_type=entity_type,
            value=value,
            normalized_value=normalized,
            confidence=confidence,
            metadata_json=metadata_json,
            description=description,
        )
        self.repository.items.append(item)
        return item, True

    create_entity = resolve_or_create_entity


class EvidenceLinkServiceStub:
    def __init__(self):
        self.links = set()

    def ensure_link(self, evidence_id, entity_id):
        key = (evidence_id, entity_id)
        created = key not in self.links
        self.links.add(key)
        return SimpleNamespace(
            evidence_id=evidence_id,
            entity_id=entity_id,
        ), created


def make_service():
    return (
        OsintFindingPersistenceService(
            source_service=SourceServiceStub(),
            evidence_service=EvidenceServiceStub(),
            entity_service=EntityServiceStub(),
            evidence_link_service=EvidenceLinkServiceStub(),
        )
    )


def make_execution(*results):
    route = PivotRoute(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        decision=PivotDecision(
            allowed=True,
            code=PivotDecisionCode.ALLOWED,
            reason="test",
        ),
        connectors=tuple(
            OSINT_CAPABILITY_CATALOG[
                "maigret_connector"
                if index == 0
                else "sherlock_connector"
            ]
            for index, _ in enumerate(results)
        ),
    )

    records = [
        ConnectorExecutionRecord(
            capability=route.connectors[index],
            runtime_connector_name=result.connector,
            result=result,
        )
        for index, result in enumerate(results)
    ]
    return EnrichmentExecutionResult(
        route=route,
        status=EnrichmentExecutionStatus.SUCCESS,
        records=records,
    )


def test_account_finding_persists_source_evidence_account_and_url_entities():
    service = make_service()
    case_id = uuid4()

    execution = make_execution(
        OsintResult(
            connector="Maigret",
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="account",
                    value="example_user",
                    url="https://social.example/example_user",
                    source="social.example",
                    confidence=0.9,
                    metadata={"site_name": "Example"},
                )
            ],
        )
    )

    result = service.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.USERNAME,
        target_value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        execution=execution,
    )

    assert result.persisted_findings == 1
    assert result.sources_created == 1
    assert result.evidences_created == 1
    assert result.entities_created == 1

    item = result.persisted[0]
    assert item.source.source_type is SourceType.OSINT
    assert item.evidence.evidence_type is EvidenceType.LINK
    assert {entity.entity_type for entity in item.entities} == {
        EntityType.URL,
    }


def test_same_execution_is_idempotent_for_source_evidence_entity_and_link():
    service = make_service()
    case_id = uuid4()

    execution = make_execution(
        OsintResult(
            connector="Maigret",
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="account",
                    value="example_user",
                    url="https://social.example/example_user",
                    source="social.example",
                    metadata={"stable": True},
                )
            ],
        )
    )

    first = service.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.USERNAME,
        target_value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        execution=execution,
    )
    second = service.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.USERNAME,
        target_value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        execution=execution,
    )

    assert first.sources_created == 1
    assert first.evidences_created == 1
    assert first.entities_created == 1
    assert second.sources_created == 0
    assert second.evidences_created == 0
    assert second.entities_created == 0
    assert second.links_created == 0


def test_two_connectors_get_distinct_sources_and_evidences():
    service = make_service()
    case_id = uuid4()

    execution = make_execution(
        OsintResult(
            connector="Maigret",
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="account",
                    value="example_user",
                    url="https://one.example/example_user",
                    source="one.example",
                )
            ],
        ),
        OsintResult(
            connector="Sherlock",
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="account",
                    value="example_user",
                    url="https://two.example/example_user",
                    source="two.example",
                )
            ],
        ),
    )

    result = service.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.USERNAME,
        target_value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        execution=execution,
    )

    assert result.persisted_findings == 2
    assert result.sources_created == 2
    assert result.evidences_created == 2
    assert len({item.source.id for item in result.persisted}) == 2


def test_failed_and_unavailable_connector_results_are_not_persisted():
    service = make_service()
    case_id = uuid4()

    execution = make_execution(
        OsintResult(
            connector="Maigret",
            status=ResultStatus.FAILED,
            error="failed",
        ),
        OsintResult(
            connector="Sherlock",
            status=ResultStatus.NOT_AVAILABLE,
            error="missing",
        ),
    )

    result = service.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.USERNAME,
        target_value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        execution=execution,
    )

    assert result.persisted_findings == 0
    assert result.skipped_results == 2
    assert service.source_service.repository.items == []


def test_partial_connector_findings_are_persisted():
    service = make_service()
    case_id = uuid4()

    execution = make_execution(
        OsintResult(
            connector="Maigret",
            status=ResultStatus.PARTIAL,
            error="one site failed",
            findings=[
                OsintFinding(
                    category="account",
                    value="example_user",
                    url="https://working.example/example_user",
                )
            ],
        )
    )

    result = service.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.USERNAME,
        target_value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        execution=execution,
    )

    assert result.persisted_findings == 1


def test_parent_entity_is_linked_to_discovered_evidence_without_ownership_relationship():
    service = make_service()
    case_id = uuid4()
    parent_id = uuid4()

    execution = make_execution(
        OsintResult(
            connector="Maigret",
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="account",
                    value="example_user",
                    url="https://social.example/example_user",
                )
            ],
        )
    )

    result = service.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.USERNAME,
        target_value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        execution=execution,
        parent_entity_id=parent_id,
    )

    evidence_id = result.persisted[0].evidence.id
    assert (evidence_id, parent_id) in service.evidence_link_service.links
    assert not hasattr(service, "relationship_service")


def test_phone_finding_maps_to_phone_evidence_and_entity():
    service = make_service()
    case_id = uuid4()

    route = PivotRoute(
        target_type=OsintTargetType.PHONE,
        value="+380671234567",
        goal=DiscoveryGoal.PHONE_ENRICHMENT,
        depth=0,
        decision=PivotDecision(
            allowed=True,
            code=PivotDecisionCode.ALLOWED,
            reason="test",
        ),
        connectors=(OSINT_CAPABILITY_CATALOG["phoneinfoga_connector"],),
    )
    execution = EnrichmentExecutionResult(
        route=route,
        status=EnrichmentExecutionStatus.SUCCESS,
        records=[
            ConnectorExecutionRecord(
                capability=route.connectors[0],
                runtime_connector_name="PhoneInfoga",
                result=OsintResult(
                    connector="PhoneInfoga",
                    status=ResultStatus.SUCCESS,
                    findings=[
                        OsintFinding(
                            category="phone",
                            value="+380671234567",
                            metadata={"country": "UA"},
                        )
                    ],
                ),
            )
        ],
    )

    result = service.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.PHONE,
        target_value="+380671234567",
        goal=DiscoveryGoal.PHONE_ENRICHMENT,
        execution=execution,
    )

    item = result.persisted[0]
    assert item.evidence.evidence_type is EvidenceType.PHONE
    assert [entity.entity_type for entity in item.entities] == [
        EntityType.PHONE
    ]


def test_evidence_metadata_contains_full_provenance_payload():
    service = make_service()
    case_id = uuid4()
    parent_id = uuid4()

    execution = make_execution(
        OsintResult(
            connector="Maigret",
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="account",
                    value="example_user",
                    url="https://social.example/example_user",
                    source="social.example",
                    confidence=0.82,
                    reliability=0.76,
                    metadata={"site": "social.example"},
                )
            ],
        )
    )

    result = service.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.USERNAME,
        target_value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        execution=execution,
        parent_entity_id=parent_id,
    )

    import json
    metadata = json.loads(result.persisted[0].evidence.metadata_json)

    assert metadata["workflow"] == "osint_enrichment"
    assert metadata["connector"] == "Maigret"
    assert metadata["finding"]["url"] == "https://social.example/example_user"
    assert metadata["finding"]["confidence"] == 0.82
    assert metadata["origin"]["target_type"] == "username"
    assert metadata["origin"]["target_value"] == "example_user"
    assert metadata["origin"]["goal"] == "account_discovery"
    assert metadata["origin"]["parent_entity_id"] == str(parent_id)


def test_empty_finding_is_skipped_without_creating_source():
    service = make_service()
    case_id = uuid4()

    execution = make_execution(
        OsintResult(
            connector="Maigret",
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="account",
                    value="",
                    metadata={},
                )
            ],
        )
    )

    result = service.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.USERNAME,
        target_value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        execution=execution,
    )

    assert result.persisted_findings == 0
    assert result.skipped_findings == 1
    assert service.source_service.repository.items == []

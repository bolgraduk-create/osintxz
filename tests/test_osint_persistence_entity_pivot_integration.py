from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from app.application.osint_enrichment_service import (
    OsintEnrichmentService,
)
from app.models.entity import EntityType
from app.models.evidence import EvidenceType
from app.models.source import SourceType
from app.osint.capabilities import DiscoveryGoal
from app.osint.enrichment_execution import (
    ConnectorExecutionRecord,
    EnrichmentExecutionResult,
    EnrichmentExecutionStatus,
    NewEntityBudget,
)
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)
from app.osint.models import OsintTargetType
from app.osint.pivot_candidates import (
    OsintPivotCandidatePolicy,
)
from app.osint.pivot_policy import PivotTraversalState
from app.osint.result import (
    OsintFinding,
    OsintResult,
    ResultStatus,
)


class FakeSourceRepository:
    def __init__(self) -> None:
        self.items = []

    def get_by_case(self, case_id):
        return [
            item
            for item in self.items
            if item.case_id == case_id
        ]


class FakeSourceService:
    def __init__(self) -> None:
        self.repository = FakeSourceRepository()

    def create_source(
        self,
        *,
        case_id,
        name,
        source_type,
        path,
        description,
        **kwargs,
    ):
        item = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            name=name,
            source_type=source_type,
            original_path=path,
            description=description,
            metadata_json=None,
        )
        self.repository.items.append(item)
        return item


class FakeEvidenceRepository:
    def __init__(self) -> None:
        self.items = []
        self.session = None

    def get_by_source(self, source_id):
        return [
            item
            for item in self.items
            if item.source_id == source_id
        ]


class FakeEvidenceService:
    def __init__(self) -> None:
        self.repository = FakeEvidenceRepository()

    def create_evidence(
        self,
        *,
        case_id,
        source_id,
        evidence_type,
        title,
        value,
        description,
        **kwargs,
    ):
        item = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            source_id=source_id,
            evidence_type=evidence_type,
            title=title,
            value=value,
            description=description,
            metadata_json=None,
        )
        self.repository.items.append(item)
        return item


class FakeNormalizer:
    def normalize(self, entity_type, value):
        text = str(value).strip()

        if entity_type in {
            EntityType.DOMAIN,
            EntityType.EMAIL,
            EntityType.USERNAME,
        }:
            return text.casefold().rstrip(".")

        return text


class FakeEntityRepository:
    def __init__(self) -> None:
        self.items = []

    def find_in_case(
        self,
        *,
        case_id,
        entity_type,
        normalized_value,
    ):
        for item in self.items:
            if (
                item.case_id == case_id
                and item.entity_type is entity_type
                and item.normalized_value == normalized_value
            ):
                return item
        return None


class FakeEntityService:
    def __init__(self) -> None:
        self.repository = FakeEntityRepository()
        self.normalizer = FakeNormalizer()

    def resolve_or_create_entity(
        self,
        *,
        case_id,
        entity_type,
        value,
        confidence,
        metadata_json,
        description,
        **kwargs,
    ):
        normalized = self.normalizer.normalize(
            entity_type,
            value,
        )

        existing = self.repository.find_in_case(
            case_id=case_id,
            entity_type=entity_type,
            normalized_value=normalized,
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

    def update_confidence(
        self,
        entity_id,
        confidence,
    ):
        for item in self.repository.items:
            if item.id == entity_id:
                item.confidence = confidence
                return item
        return None


class FakeEvidenceLinkService:
    def __init__(self) -> None:
        self.links: set[
            tuple[UUID, UUID]
        ] = set()

    def ensure_link(
        self,
        *,
        evidence_id,
        entity_id,
    ):
        key = (
            evidence_id,
            entity_id,
        )

        created = (
            key not in self.links
        )

        self.links.add(key)

        return (
            SimpleNamespace(
                id=uuid4(),
                evidence_id=evidence_id,
                entity_id=entity_id,
            ),
            created,
        )


def build_persistence():
    source_service = FakeSourceService()
    evidence_service = FakeEvidenceService()
    entity_service = FakeEntityService()
    link_service = FakeEvidenceLinkService()

    service = OsintFindingPersistenceService(
        source_service=source_service,
        evidence_service=evidence_service,
        entity_service=entity_service,
        evidence_link_service=link_service,
    )

    return (
        service,
        source_service,
        evidence_service,
        entity_service,
        link_service,
    )


def capability(module: str = "test.discovery"):
    return SimpleNamespace(
        module=module,
        connector_class="SyntheticConnector",
        goals=frozenset(
            {
                DiscoveryGoal.DOMAIN_DISCOVERY,
            }
        ),
    )


def execution_for(
    findings,
    *,
    connector="SyntheticDiscovery",
    budget=20,
):
    record = ConnectorExecutionRecord(
        capability=capability(),
        runtime_connector_name=connector,
        result=OsintResult(
            connector=connector,
            status=ResultStatus.SUCCESS,
            findings=list(findings),
        ),
    )

    return EnrichmentExecutionResult(
        route=SimpleNamespace(
            goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        ),
        status=EnrichmentExecutionStatus.SUCCESS,
        records=[
            record,
        ],
        entity_budget=NewEntityBudget(
            budget,
        ),
    )


def discovery_chain_findings():
    return [
        OsintFinding(
            category="subdomain",
            value="dev.example.com",
            source="Assetfinder",
        ),
        OsintFinding(
            category="dns",
            value="dev.example.com",
            source="DNSX",
            metadata={
                "host": "dev.example.com",
                "a": [
                    "203.0.113.10",
                ],
                "aaaa": [
                    "2001:db8::10",
                ],
            },
        ),
        OsintFinding(
            category="http",
            value="https://dev.example.com",
            url="https://dev.example.com",
            source="HTTPX",
            metadata={
                "host": "dev.example.com",
                "host_ip": "203.0.113.10",
                "a": [
                    "203.0.113.10",
                ],
                "aaaa": [
                    "2001:db8::10",
                ],
                "status_code": 200,
            },
        ),
        OsintFinding(
            category="endpoint",
            value="https://dev.example.com/api",
            source="Katana",
        ),
        OsintFinding(
            category="historical_url",
            value="https://dev.example.com/old",
            url="https://dev.example.com/old",
            source="GAU",
        ),
    ]


def test_discovery_categories_produce_pivotable_domain_ip_and_url_entities():
    (
        persistence,
        _,
        _,
        _,
        _,
    ) = build_persistence()

    result = persistence.persist_execution(
        case_id=uuid4(),
        target_type=OsintTargetType.DOMAIN,
        target_value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        execution=execution_for(
            discovery_chain_findings(),
            budget=20,
        ),
    )

    pairs = {
        (
            entity.entity_type,
            entity.normalized_value,
        )
        for persisted in result.persisted
        for entity in persisted.entities
    }

    assert (
        EntityType.DOMAIN,
        "dev.example.com",
    ) in pairs

    assert (
        EntityType.IP,
        "203.0.113.10",
    ) in pairs

    assert (
        EntityType.IP,
        "2001:db8::10",
    ) in pairs

    assert (
        EntityType.URL,
        "https://dev.example.com",
    ) in pairs

    assert (
        EntityType.URL,
        "https://dev.example.com/api",
    ) in pairs

    assert (
        EntityType.URL,
        "https://dev.example.com/old",
    ) in pairs

    candidates = (
        OsintPivotCandidatePolicy()
        .from_persistence_results(
            [
                result,
            ],
            next_depth=1,
        )
    )

    target_types = {
        candidate.target_type
        for candidate in candidates
    }

    assert OsintTargetType.DOMAIN in target_types
    assert OsintTargetType.IP in target_types
    assert OsintTargetType.URL in target_types


def test_dns_and_http_evidence_types_match_discovery_semantics():
    assert (
        OsintFindingPersistenceService._evidence_type(
            OsintFinding(
                category="dns",
                value="example.com",
            )
        )
        is EvidenceType.METADATA
    )

    assert (
        OsintFindingPersistenceService._evidence_type(
            OsintFinding(
                category="http",
                value="https://example.com",
            )
        )
        is EvidenceType.LINK
    )

    assert (
        OsintFindingPersistenceService._evidence_type(
            OsintFinding(
                category="endpoint",
                value="https://example.com/api",
            )
        )
        is EvidenceType.LINK
    )


def test_structured_metadata_accepts_only_valid_ip_addresses():
    candidates = (
        OsintFindingPersistenceService
        ._entity_candidates(
            OsintFinding(
                category="dns",
                value="dev.example.com",
                metadata={
                    "a": [
                        "203.0.113.5",
                        "not-an-ip",
                    ],
                    "aaaa": [
                        "2001:db8::5",
                    ],
                    "host_ip": "also-not-an-ip",
                },
            )
        )
    )

    ips = {
        value
        for entity_type, value, _
        in candidates
        if entity_type is EntityType.IP
    }

    assert ips == {
        "203.0.113.5",
        "2001:db8::5",
    }


def test_persistence_is_idempotent_for_same_discovery_execution():
    (
        persistence,
        _,
        _,
        _,
        _,
    ) = build_persistence()

    case_id = uuid4()

    execution_one = execution_for(
        discovery_chain_findings(),
        budget=20,
    )

    first = persistence.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.DOMAIN,
        target_value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        execution=execution_one,
    )

    execution_two = execution_for(
        discovery_chain_findings(),
        budget=20,
    )

    second = persistence.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.DOMAIN,
        target_value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        execution=execution_two,
    )

    assert first.sources_created == 1
    assert first.evidences_created == 5
    assert first.entities_created >= 6

    assert second.sources_created == 0
    assert second.evidences_created == 0
    assert second.entities_created == 0
    assert second.links_created == 0


def test_new_entity_budget_cannot_be_overshot_by_multi_entity_findings():
    (
        persistence,
        _,
        _,
        _,
        _,
    ) = build_persistence()

    execution = execution_for(
        discovery_chain_findings(),
        budget=2,
    )

    result = persistence.persist_execution(
        case_id=uuid4(),
        target_type=OsintTargetType.DOMAIN,
        target_value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        execution=execution,
    )

    assert execution.entity_budget is not None
    assert execution.entity_budget.consumed == 2
    assert execution.entity_budget.remaining == 0
    assert result.entities_created == 2

    candidates = (
        OsintPivotCandidatePolicy()
        .from_persistence_results(
            [
                result,
            ],
            next_depth=1,
        )
    )

    assert len(candidates) <= 2


def test_exhausted_budget_still_links_new_evidence_to_existing_entity():
    (
        persistence,
        _,
        _,
        _,
        link_service,
    ) = build_persistence()

    case_id = uuid4()

    first_execution = execution_for(
        [
            OsintFinding(
                category="subdomain",
                value="dev.example.com",
                source="Assetfinder",
            ),
        ],
        budget=1,
    )

    first = persistence.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.DOMAIN,
        target_value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        execution=first_execution,
    )

    entity = first.persisted[0].entities[0]

    exhausted = NewEntityBudget(
        limit=1,
        consumed=1,
    )

    second_execution = execution_for(
        [
            OsintFinding(
                category="dns",
                value="dev.example.com",
                source="DNSX",
                metadata={
                    "a": [
                        "198.51.100.77",
                    ],
                },
            ),
        ],
        budget=1,
    )
    second_execution.entity_budget = exhausted

    second = persistence.persist_execution(
        case_id=case_id,
        target_type=OsintTargetType.DOMAIN,
        target_value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        execution=second_execution,
    )

    assert second.entities_created == 0
    assert second.evidences_created == 1

    persisted = second.persisted[0]

    assert entity in persisted.entities
    assert (
        persisted.evidence.id,
        entity.id,
    ) in link_service.links

    # The previously unseen IP must not bypass the exhausted entity budget.
    assert all(
        candidate.entity_type is not EntityType.IP
        for candidate in (
            OsintPivotCandidatePolicy()
            .from_persistence_results(
                [
                    second,
                ],
                next_depth=1,
            )
        )
    )


class FakeExecutionService:
    def __init__(self) -> None:
        self.calls = []

    def execute_defaults(self, **kwargs):
        self.calls.append(kwargs)

        execution = execution_for(
            [
                OsintFinding(
                    category="subdomain",
                    value="api.example.com",
                    source="Assetfinder",
                ),
            ],
            budget=50,
        )

        return (
            execution,
        )


def test_application_enrichment_updates_traversal_state_and_exposes_pivots():
    (
        persistence,
        _,
        _,
        _,
        _,
    ) = build_persistence()

    execution_service = FakeExecutionService()

    service = OsintEnrichmentService(
        execution_service=execution_service,
        persistence_service=persistence,
    )

    state = PivotTraversalState()

    result = service.enrich_target(
        case_id=uuid4(),
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
        state=state,
        depth=0,
    )

    assert result.persisted_findings == 1
    assert result.entities_created == 1
    assert state.new_entities_count == 1

    candidates = (
        OsintPivotCandidatePolicy()
        .from_enrichment_result(
            result,
            next_depth=1,
        )
    )

    assert len(candidates) == 1
    assert candidates[0].target_type is OsintTargetType.DOMAIN
    assert candidates[0].value == "api.example.com"
    assert candidates[0].depth == 1


def test_parent_pivot_provenance_is_linked_to_created_evidence():
    (
        persistence,
        _,
        _,
        _,
        link_service,
    ) = build_persistence()

    parent_entity_id = uuid4()

    result = persistence.persist_execution(
        case_id=uuid4(),
        target_type=OsintTargetType.DOMAIN,
        target_value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        execution=execution_for(
            [
                OsintFinding(
                    category="subdomain",
                    value="api.example.com",
                    source="Assetfinder",
                ),
            ],
            budget=5,
        ),
        parent_entity_id=parent_entity_id,
    )

    persisted = result.persisted[0]

    assert (
        persisted.evidence.id,
        parent_entity_id,
    ) in link_service.links

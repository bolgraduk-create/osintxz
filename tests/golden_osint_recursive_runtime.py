"""
M021.6 deterministic recursive OSINT golden runtime.

Uses the real M021.1-M021.5 orchestration stack with:
- deterministic connector doubles
- in-memory domain-service doubles

No network, external CLI, database, Ollama or API key is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid5, NAMESPACE_URL
import json

from app.application.osint_enrichment_service import OsintEnrichmentService
from app.application.osint_recursive_enrichment_service import (
    OsintRecursiveEnrichmentService,
    RecursiveEnrichmentSeed,
)
from app.models.entity import EntityType
from app.osint.enrichment_execution import OsintEnrichmentExecutionService
from app.osint.finding_persistence import OsintFindingPersistenceService
from app.osint.models import OsintTargetType
from app.osint.pipeline import OsintPipeline
from app.osint.pivot_policy import OsintPivotPolicy, PivotPolicyLimits
from app.osint.pivot_router import OsintCapabilityRouter
from app.osint.result import OsintFinding, OsintResult, ResultStatus


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "golden_osint_recursive"


def stable_uuid(kind: str, value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"osintxz:m021.6:{kind}:{value}")


class DeterministicConnector:
    name = "deterministic"
    supported_targets = set()

    def execute(self, request):
        return OsintResult(
            connector=self.name,
            status=ResultStatus.SUCCESS,
        )


def connector_class(class_name: str, runtime_name: str, target_types, handler):
    cls = type(class_name, (DeterministicConnector,), {})
    instance = cls()
    instance.name = runtime_name
    instance.supported_targets = set(target_types)
    instance.execute = handler
    return instance


class GoldenRegistry:
    def __init__(self, connectors):
        self._items = {
            connector.name.lower(): connector
            for connector in connectors
        }

    def all(self):
        return list(self._items.values())

    def get(self, connector_name):
        return self._items.get(connector_name.lower())

    def supported(self, target_type):
        return [
            item
            for item in self._items.values()
            if target_type in item.supported_targets
        ]

    def names(self):
        return sorted(self._items)


class GoldenManager:
    def __init__(self, connectors):
        self.registry = GoldenRegistry(connectors)


class GoldenSourceRepository:
    def __init__(self):
        self.items = []

    def get_by_case(self, case_id):
        return [
            item
            for item in self.items
            if item.case_id == case_id
        ]


class GoldenSourceService:
    def __init__(self):
        self.repository = GoldenSourceRepository()

    def create_source(
        self,
        case_id,
        name,
        source_type,
        path=None,
        description=None,
    ):
        item = SimpleNamespace(
            id=stable_uuid("source", path or name),
            case_id=case_id,
            name=name,
            source_type=source_type,
            path=path,
            original_path=path,
            description=description,
        )
        self.repository.items.append(item)
        return item


class GoldenEvidenceRepository:
    def __init__(self):
        self.items = []
        self.session = SimpleNamespace(flush=lambda: None)

    def get_by_source(self, source_id):
        return [
            item
            for item in self.items
            if item.source_id == source_id
        ]


class GoldenEvidenceService:
    def __init__(self):
        self.repository = GoldenEvidenceRepository()

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
        stable_key = "|".join(
            (
                str(source_id),
                str(evidence_type.value),
                str(value or ""),
                str(description or ""),
            )
        )
        item = SimpleNamespace(
            id=stable_uuid("evidence", stable_key),
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


class GoldenNormalizer:
    def normalize(self, entity_type, value):
        text = str(value or "").strip()

        if entity_type is EntityType.USERNAME:
            return text.lstrip("@").casefold()

        if entity_type is EntityType.EMAIL:
            return text.casefold()

        if entity_type is EntityType.DOMAIN:
            return text.casefold().rstrip(".")

        if entity_type is EntityType.URL:
            return text

        if entity_type is EntityType.PHONE:
            prefix = "+" if text.startswith("+") else ""
            digits = "".join(ch for ch in text if ch.isdigit())
            return prefix + digits

        return text.casefold()


class GoldenEntityRepository:
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


class GoldenEntityService:
    def __init__(self):
        self.repository = GoldenEntityRepository()
        self.normalizer = GoldenNormalizer()

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
        normalized = self.normalizer.normalize(
            entity_type,
            value,
        )
        existing = self.repository.find_in_case(
            case_id,
            entity_type,
            normalized,
        )
        if existing is not None:
            return existing, False

        item = SimpleNamespace(
            id=stable_uuid(
                "entity",
                f"{case_id}|{entity_type.value}|{normalized}",
            ),
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

    def create_entity(self, **kwargs):
        return self.resolve_or_create_entity(**kwargs)


class GoldenEvidenceLinkService:
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


@dataclass
class GoldenRuntime:
    recursive_service: OsintRecursiveEnrichmentService
    source_service: GoldenSourceService
    evidence_service: GoldenEvidenceService
    entity_service: GoldenEntityService
    evidence_link_service: GoldenEvidenceLinkService
    executed_connectors: list[str]


def build_runtime() -> GoldenRuntime:
    executed: list[str] = []

    def success(name, findings_factory=None):
        def handler(request):
            executed.append(name)
            findings = (
                findings_factory(request)
                if findings_factory is not None
                else []
            )
            return OsintResult(
                connector=name,
                status=ResultStatus.SUCCESS,
                findings=findings,
            )
        return handler

    def maigret_findings(request):
        if request.target.value.casefold().lstrip("@") != "golden_alice":
            return []
        return [
            OsintFinding(
                category="account",
                value="golden_alice",
                url="https://profiles.example/golden_alice",
                source="profiles.example",
                confidence=0.94,
                reliability=0.90,
                metadata={
                    "site_name": "Golden Profiles",
                    "fixture": True,
                },
            )
        ]

    def commoncrawl_findings(request):
        value = request.target.value

        if (
            request.target.target_type is OsintTargetType.URL
            and value == "https://profiles.example/golden_alice"
        ):
            return [
                OsintFinding(
                    category="domain",
                    value="example.org",
                    source="Common Crawl",
                    confidence=0.88,
                    reliability=0.86,
                    metadata={"fixture": True, "kind": "domain-pivot"},
                ),
                OsintFinding(
                    category="public_url",
                    value="https://example.org/about",
                    url="https://example.org/about",
                    source="Common Crawl",
                    confidence=0.91,
                    reliability=0.89,
                    metadata={"fixture": True, "kind": "url-pivot"},
                ),
            ]

        return []

    connectors = [
        connector_class(
            "MaigretConnector",
            "Maigret",
            {OsintTargetType.USERNAME},
            success("Maigret", maigret_findings),
        ),
        connector_class(
            "SherlockConnector",
            "Sherlock",
            {OsintTargetType.USERNAME},
            success("Sherlock"),
        ),
        connector_class(
            "CommonCrawlConnector",
            "commoncrawl",
            {OsintTargetType.URL, OsintTargetType.DOMAIN},
            success("commoncrawl", commoncrawl_findings),
        ),
        connector_class(
            "GauConnector",
            "GAU",
            {OsintTargetType.URL, OsintTargetType.DOMAIN},
            success("GAU"),
        ),
        connector_class(
            "WaybackurlsConnector",
            "Waybackurls",
            {OsintTargetType.URL, OsintTargetType.DOMAIN},
            success("Waybackurls"),
        ),
        connector_class(
            "ArchiveTodayConnector",
            "archivetoday",
            {OsintTargetType.URL, OsintTargetType.DOMAIN},
            success("archivetoday"),
        ),
        connector_class(
            "CrtShConnector",
            "crtsh",
            {OsintTargetType.DOMAIN},
            success("crtsh"),
        ),
        connector_class(
            "SubfinderConnector",
            "Subfinder",
            {OsintTargetType.DOMAIN},
            success("Subfinder"),
        ),
        # Deliberately present in runtime but must never be selected by
        # automatic M021 policy.
        connector_class(
            "NmapConnector",
            "Nmap",
            {
                OsintTargetType.DOMAIN,
                OsintTargetType.URL,
                OsintTargetType.IP,
            },
            success("Nmap"),
        ),
        connector_class(
            "GHuntConnector",
            "GHunt",
            {OsintTargetType.EMAIL},
            success("GHunt"),
        ),
    ]

    pipeline = OsintPipeline(
        GoldenManager(connectors)
    )
    router = OsintCapabilityRouter(
        policy=OsintPivotPolicy(
            PivotPolicyLimits(
                max_depth=2,
                max_pivots_per_entity=8,
                max_new_entities=25,
            )
        )
    )
    execution_service = OsintEnrichmentExecutionService(
        pipeline=pipeline,
        router=router,
    )

    source_service = GoldenSourceService()
    evidence_service = GoldenEvidenceService()
    entity_service = GoldenEntityService()
    evidence_link_service = GoldenEvidenceLinkService()

    persistence_service = OsintFindingPersistenceService(
        source_service=source_service,
        evidence_service=evidence_service,
        entity_service=entity_service,
        evidence_link_service=evidence_link_service,
    )
    enrichment_service = OsintEnrichmentService(
        execution_service=execution_service,
        persistence_service=persistence_service,
    )
    recursive_service = OsintRecursiveEnrichmentService(
        enrichment_service=enrichment_service,
    )

    return GoldenRuntime(
        recursive_service=recursive_service,
        source_service=source_service,
        evidence_service=evidence_service,
        entity_service=entity_service,
        evidence_link_service=evidence_link_service,
        executed_connectors=executed,
    )


def load_scenario() -> dict:
    return json.loads(
        (FIXTURE_DIR / "scenario.json").read_text(
            encoding="utf-8"
        )
    )


def load_expected() -> dict:
    return json.loads(
        (FIXTURE_DIR / "expected.json").read_text(
            encoding="utf-8"
        )
    )


def run_once(runtime: GoldenRuntime):
    scenario = load_scenario()

    return runtime.recursive_service.enrich(
        case_id=UUID(scenario["case_id"]),
        seeds=tuple(
            RecursiveEnrichmentSeed(
                target_type=OsintTargetType(
                    seed["target_type"]
                ),
                value=seed["value"],
                parent_entity_id=(
                    UUID(seed["parent_entity_id"])
                    if seed.get("parent_entity_id")
                    else None
                ),
            )
            for seed in scenario["seeds"]
        ),
        timeout=scenario["timeout"],
        use_cache=scenario["use_cache"],
        save_raw_output=False,
        include_metadata=True,
        include_related=True,
    )


def snapshot(runtime: GoldenRuntime, recursive_result) -> dict:
    entities = sorted(
        (
            item.entity_type.value,
            item.normalized_value,
        )
        for item in runtime.entity_service.repository.items
    )

    sources = sorted(
        item.name
        for item in runtime.source_service.repository.items
    )

    evidences = sorted(
        (
            item.evidence_type.value,
            item.value,
        )
        for item in runtime.evidence_service.repository.items
    )

    return {
        "targets_processed": recursive_result.targets_processed,
        "persisted_findings": recursive_result.persisted_findings,
        "sources_created": recursive_result.sources_created,
        "evidences_created": recursive_result.evidences_created,
        "entities_created": recursive_result.entities_created,
        "stop_reason": recursive_result.stop_reason.value,
        "candidate_stats": {
            "discovered": recursive_result.candidates_discovered,
            "enqueued": recursive_result.candidates_enqueued,
            "deduplicated": recursive_result.candidates_deduplicated,
        },
        "executed_connectors": list(
            runtime.executed_connectors
        ),
        "entities": [
            {"type": kind, "value": value}
            for kind, value in entities
        ],
        "sources": list(sources),
        "evidences": [
            {"type": kind, "value": value}
            for kind, value in evidences
        ],
        "evidence_entity_links": len(
            runtime.evidence_link_service.links
        ),
    }

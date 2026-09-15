"""Registry adapter to existing case services; the caller owns the transaction.

Registry records remain distinct from OSINT targets. No name-only organization
fusion, relationship inference, new tables, network calls or implicit commits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from uuid import UUID

from app.models.entity import Entity, EntityType
from app.models.evidence import Evidence, EvidenceType
from app.models.source import Source, SourceType
from app.registry_intelligence.contracts import RegistryDomain, RegistrySearchResult


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


@dataclass(slots=True)
class PersistedRegistryRecord:
    source: Source
    evidence: Evidence
    entities: list[Entity]
    resolution_method: str | None


@dataclass(slots=True)
class RegistryPersistenceResult:
    records: list[PersistedRegistryRecord] = field(default_factory=list)
    sources_created: int = 0
    evidences_created: int = 0
    entities_created: int = 0
    links_created: int = 0
    skipped_records: int = 0
    errors: list[str] = field(default_factory=list)


class RegistryPersistenceService:
    def __init__(self, *, source_service, evidence_service, entity_service,
                 evidence_link_service, search_indexing_service=None) -> None:
        self.source_service = source_service
        self.evidence_service = evidence_service
        self.entity_service = entity_service
        self.evidence_link_service = evidence_link_service
        self.search_indexing_service = search_indexing_service

    def persist(self, *, case_id: UUID, result: RegistrySearchResult) -> RegistryPersistenceResult:
        case_id = UUID(str(case_id))
        out = RegistryPersistenceResult()
        sources = {s.original_path: s for s in self.source_service.repository.get_by_case(case_id)
                   if s.source_type is SourceType.API and not s.is_deleted}
        organizations = [e for e in self.entity_service.repository.get_case_entities_by_type(
            case_id, EntityType.ORGANIZATION) if not e.is_deleted]
        seen = set()
        # Admit only records returned by usable provider results. Aggregated candidates
        # alone cannot be injected into persistence as verified registry records.
        admitted = {r.identity_key for p in result.provider_results if p.usable for r in p.records}
        for record in result.records:
            if record.identity_key not in admitted or record.identity_key in seen:
                out.skipped_records += 1
                continue
            seen.add(record.identity_key)
            try:
                provider, record_id = record.identity_key
                if not provider or not record_id or not record.display_name.strip():
                    raise ValueError("Registry provider, record ID and name are required.")
                if record.metadata.get("candidate_only") or record.metadata.get("lead_only"):
                    raise ValueError("Unverified registry candidate is not evidence.")
                if not all(math.isfinite(float(v)) and 0 <= float(v) <= 1
                           for v in (record.confidence, record.reliability)):
                    raise ValueError("Registry confidence/reliability must be within 0..1.")
                data = asdict(record)
                snapshot_key = _digest(data)
                lei = (record.lei or "").strip().upper()
                if lei and not re.fullmatch(r"[A-Z0-9]{18}[0-9]{2}", lei):
                    raise ValueError("Malformed registry LEI.")
            except (ValueError, TypeError) as exc:
                out.skipped_records += 1
                out.errors.append(str(exc))
                continue

            source_path = "registry://" + _digest([provider, record.domain.value])
            source = sources.get(source_path)
            if source is None:
                source = self.source_service.create_source(
                    case_id=case_id, name=f"Registry · {provider}"[:255],
                    source_type=SourceType.API, path=source_path,
                    description=f"Public registry provider={provider}; domain={record.domain.value}",
                )
                sources[source_path] = source
                out.sources_created += 1
            evidence_key = "registry_record_snapshot=" + snapshot_key
            evidence = next((e for e in self.evidence_service.repository.get_by_source(source.id)
                             if not e.is_deleted and (e.description or "").startswith(evidence_key + "\n")), None)
            if evidence is None:
                evidence = self.evidence_service.create_evidence(
                    case_id=case_id, source_id=source.id, evidence_type=EvidenceType.METADATA,
                    title=record.display_name[:255], value=(record.source_url or record.record_id)[:1024],
                    description=evidence_key + "\n" + "\n".join(filter(None, [
                        record.display_name, record.lei, record.registration_id,
                        record.legal_address, record.headquarters_address,
                    ])),
                    metadata_json=_json({
                        "workflow": "registry_intelligence", "provenance_version": 1,
                        "provider": provider, "record": data,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "query": asdict(result.query), "snapshot_key": snapshot_key,
                        "verification_method": "public_registry_record",
                        "ownership_inferred": False,
                    }),
                )
                out.evidences_created += 1

            entities, method = [], None
            if record.domain is RegistryDomain.BUSINESS:
                record_key = _digest([provider, record.domain.value, record_id])
                identity = "registry:lei:" + lei if lei else "registry:record:" + record_key
                # LEI is global; provider record IDs are namespaced. Names and
                # unscoped registration IDs are never identity keys.
                organization = None
                for candidate in organizations:
                    metadata = self._metadata(candidate)
                    known = metadata.get("registry_identity", {})
                    known_lei = known.get("lei")
                    if lei and known_lei and lei != known_lei:
                        continue
                    if (lei and known_lei == lei) or record_key in known.get("record_keys", []):
                        organization = candidate
                        break
                method = "exact_lei" if lei else "exact_provider_record_id"
                if organization is None:
                    organization, created = self.entity_service.resolve_or_create_entity(
                        case_id=case_id, entity_type=EntityType.ORGANIZATION,
                        value=record.display_name[:512], normalized_value=identity,
                        confidence=min(record.confidence, record.reliability),
                        description="Organization observed in a public registry; no ownership inference.",
                    )
                    out.entities_created += int(created)
                    organizations.append(organization)
                metadata = self._metadata(organization)
                known = metadata.setdefault("registry_identity", {})
                keys = known.setdefault("record_keys", [])
                if record_key not in keys:
                    keys.append(record_key)
                if lei:
                    known["lei"] = lei
                metadata["resolution_method"] = method
                self.entity_service.update_metadata(organization.id, _json(metadata))
                entities.append(organization)
                for address in dict.fromkeys(filter(None, [record.legal_address, record.headquarters_address])):
                    address_key = "registry:address:" + _digest([
                        (record.country or "").strip().upper(),
                        self.entity_service.normalizer.normalize(EntityType.ADDRESS, address),
                    ])
                    entity, created = self.entity_service.resolve_or_create_entity(
                        case_id=case_id, entity_type=EntityType.ADDRESS, value=address[:512],
                        normalized_value=address_key, confidence=min(record.confidence, record.reliability),
                    )
                    entities.append(entity)
                    out.entities_created += int(created)
                for entity in entities:
                    _, created = self.evidence_link_service.ensure_link(evidence.id, entity.id)
                    out.links_created += int(created)
                    if self.search_indexing_service is not None:
                        self.search_indexing_service.index_object_text_only(entity)
            out.records.append(PersistedRegistryRecord(source, evidence, entities, method))
        return out

    @staticmethod
    def _metadata(entity) -> dict:
        try:
            value = json.loads(entity.metadata_json or "{}")
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

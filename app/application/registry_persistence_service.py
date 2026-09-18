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

from app.intelligence_sources.policy import IntelligenceDataSanitizer
from app.models.entity import Entity, EntityType
from app.models.evidence import Evidence, EvidenceType
from app.models.source import Source, SourceType
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistrySearchResult,
)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _registry_snapshot_payload(record) -> dict:
    """Return the stable content identity for one registry record.

    ``retrieved_at`` describes the observation event, not the registry record
    content. Including it in the evidence snapshot digest would create a new
    Evidence row every time the same unchanged record is fetched.

    All substantive registry fields (including provenance, identifiers,
    source type, trust and provider metadata) remain part of the digest so a
    real upstream record change still creates a new immutable snapshot.
    """
    payload = asdict(record)
    payload.pop("retrieved_at", None)
    return payload


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
                 evidence_link_service, search_indexing_service=None,
                 data_sanitizer: IntelligenceDataSanitizer | None = None) -> None:
        self.data_sanitizer = data_sanitizer or IntelligenceDataSanitizer()
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
        persons = [e for e in self.entity_service.repository.get_case_entities_by_type(
            case_id, EntityType.PERSON) if not e.is_deleted]
        seen = set()
        # Admit only records returned by usable provider results. Aggregated candidates
        # alone cannot be injected into persistence as verified registry records.
        admitted = {r.identity_key for p in result.provider_results if p.usable for r in p.records}
        for record in result.records:
            # Defense in depth: sanitize again at the persistence boundary so
            # direct RegistryPersistenceService callers cannot store raw secrets.
            record = self.data_sanitizer.sanitize(record).value
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
                if record.domain is RegistryDomain.COURT:
                    if record.entity_kind not in {
                        RegistryEntityKind.COURT_CASE,
                        RegistryEntityKind.COURT_DECISION,
                    }:
                        raise ValueError("Court registry records must use a court entity kind.")
                    if not record.sensitive_legal_data:
                        raise ValueError("Court registry records must be marked as sensitive legal data.")
                    if record.metadata.get("person_identity_inference_prohibited") is not True:
                        raise ValueError(
                            "Court registry record is missing the person-identity inference guardrail."
                        )
                    if record.metadata.get("legal_outcome_inference_prohibited") is not True:
                        raise ValueError(
                            "Court registry record is missing the legal-outcome inference guardrail."
                        )
                data = asdict(record)
                snapshot_key = _digest(_registry_snapshot_payload(record))
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
                evidence_metadata = {
                    "workflow": "registry_intelligence", "provenance_version": 1,
                    "provider": provider, "record": data,
                    "retrieved_at": record.retrieved_at or datetime.now(timezone.utc).isoformat(),
                    "raw_reference": record.raw_reference or record.record_id,
                    "source_type": record.source_type.value,
                    "trust_score": record.trust_score,
                    "sensitive_legal_data": record.sensitive_legal_data,
                    "query": asdict(result.query), "snapshot_key": snapshot_key,
                    "verification_method": "public_registry_record",
                    "ownership_inferred": False,
                }
                if record.domain is RegistryDomain.COURT:
                    evidence_metadata["legal_safety"] = {
                        "legal_outcome": record.metadata.get("legal_outcome", "unknown"),
                        "legal_outcome_inference_prohibited": True,
                        "person_identity_inference_prohibited": True,
                        "guilt_or_conviction_inference_prohibited": True,
                        "identity_resolution": "not_attempted",
                    }
                evidence = self.evidence_service.create_evidence(
                    case_id=case_id, source_id=source.id, evidence_type=EvidenceType.METADATA,
                    title=record.display_name[:255], value=(record.source_url or record.record_id)[:1024],
                    description=evidence_key + "\n" + "\n".join(filter(None, [
                        record.display_name,
                        record.identifiers.get("CASE_NUMBER"),
                        record.identifiers.get("EDRSR_DOC_ID"),
                        record.lei, record.registration_id,
                        record.legal_address, record.headquarters_address,
                    ])),
                    metadata_json=_json(evidence_metadata),
                )
                out.evidences_created += 1

            entities, method = [], None
            if record.domain is RegistryDomain.COURT:
                # A court record is evidence about a document/case, not proof that a
                # named person is the same investigation Entity and not proof of guilt.
                # Identity linking remains an explicit later analyst/resolution step.
                method = "no_identity_resolution"
            elif record.domain is RegistryDomain.BUSINESS:
                record_key = _digest([provider, record.domain.value, record_id])
                is_person_record = record.entity_kind is RegistryEntityKind.SOLE_TRADER
                entity_type = EntityType.PERSON if is_person_record else EntityType.ORGANIZATION
                pool = persons if is_person_record else organizations

                # LEI is global; provider record IDs are namespaced. Names and
                # unscoped registration IDs are never cross-provider identity keys.
                identity = (
                    "registry:lei:" + lei
                    if lei and not is_person_record
                    else "registry:record:" + record_key
                )
                matched = None
                for candidate in pool:
                    metadata = self._metadata(candidate)
                    known = metadata.get("registry_identity", {})
                    known_lei = known.get("lei")
                    if lei and not is_person_record and known_lei and lei != known_lei:
                        continue
                    if (
                        (lei and not is_person_record and known_lei == lei)
                        or record_key in known.get("record_keys", [])
                    ):
                        matched = candidate
                        break

                method = "exact_lei" if lei and not is_person_record else "exact_provider_record_id"
                if matched is None:
                    matched, created = self.entity_service.resolve_or_create_entity(
                        case_id=case_id,
                        entity_type=entity_type,
                        value=record.display_name[:512],
                        normalized_value=identity,
                        confidence=min(record.confidence, record.reliability, record.trust_score),
                        description=(
                            "Sole trader observed in a public registry; identity confirmed by provider record, "
                            "not by name alone."
                            if is_person_record
                            else "Organization observed in a public registry; no ownership inference."
                        ),
                    )
                    out.entities_created += int(created)
                    pool.append(matched)

                metadata = self._metadata(matched)
                known = metadata.setdefault("registry_identity", {})
                keys = known.setdefault("record_keys", [])
                if record_key not in keys:
                    keys.append(record_key)
                if lei and not is_person_record:
                    known["lei"] = lei
                if record.registration_id:
                    registrations = known.setdefault("registration_ids", {})
                    registrations[provider] = record.registration_id
                metadata["resolution_method"] = method
                metadata["registry_entity_kind"] = record.entity_kind.value
                self.entity_service.update_metadata(matched.id, _json(metadata))
                entities.append(matched)

                for address in dict.fromkeys(filter(None, [record.legal_address, record.headquarters_address])):
                    address_key = "registry:address:" + _digest([
                        (record.country or "").strip().upper(),
                        self.entity_service.normalizer.normalize(EntityType.ADDRESS, address),
                    ])
                    entity, created = self.entity_service.resolve_or_create_entity(
                        case_id=case_id, entity_type=EntityType.ADDRESS, value=address[:512],
                        normalized_value=address_key, confidence=min(record.confidence, record.reliability, record.trust_score),
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

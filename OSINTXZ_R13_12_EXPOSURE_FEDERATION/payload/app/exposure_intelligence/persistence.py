from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from uuid import UUID

from app.intelligence_sources.policy import IntelligenceDataSanitizer
from app.models.evidence import EvidenceType
from app.models.source import SourceType


def _json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ExposurePersistenceResult:
    sources_created: int = 0
    evidences_created: int = 0
    records_persisted: int = 0
    records_skipped: int = 0
    errors: list[str] = field(default_factory=list)


class ExposurePersistenceService:
    """Persist safe exposure observations without identity auto-linking.

    Exposure records are investigative leads/evidence about a queried selector.
    They are not proof that a named person owns an account or secret. Therefore
    this service intentionally creates no Person entity and no relationship.
    """

    def __init__(
        self,
        *,
        source_service,
        evidence_service,
        data_sanitizer: IntelligenceDataSanitizer | None = None,
    ) -> None:
        self.source_service = source_service
        self.evidence_service = evidence_service
        self.data_sanitizer = data_sanitizer or IntelligenceDataSanitizer()

    def persist(self, *, case_id: UUID, result) -> ExposurePersistenceResult:
        case_id = UUID(str(case_id))
        out = ExposurePersistenceResult()
        federated = result.federated_result

        admitted = {
            (record.source, record.record_id)
            for provider in federated.provider_results
            if provider.usable
            for record in provider.records
        }

        existing_sources = {
            source.original_path: source
            for source in self.source_service.repository.get_by_case(case_id)
            if source.source_type is SourceType.API and not source.is_deleted
        }
        seen: set[tuple[str, str]] = set()

        for original in federated.records:
            record = self.data_sanitizer.sanitize(original).value
            identity = (record.source, record.record_id)
            if identity not in admitted or identity in seen:
                out.records_skipped += 1
                continue
            seen.add(identity)

            try:
                safe_record = {
                    "source": record.source,
                    "record_id": record.record_id,
                    "record_type": record.record_type,
                    "display_name": record.display_name,
                    "source_url": record.source_url,
                    "country": record.country,
                    "identifiers": record.identifiers,
                    "attributes": record.attributes,
                }
                sanitized = self.data_sanitizer.sanitize(safe_record)
                safe_record = sanitized.value
                if self.data_sanitizer.REDACTED in _json(safe_record):
                    # Redaction is acceptable, but only the redacted snapshot may persist.
                    pass
                safe_record.setdefault("attributes", {})["raw_secret_values_stored"] = False
                snapshot = _digest(safe_record)
            except Exception as exc:
                out.records_skipped += 1
                out.errors.append(str(exc))
                continue

            source_path = f"exposure://{record.source}"
            source = existing_sources.get(source_path)
            if source is None:
                source = self.source_service.create_source(
                    case_id=case_id,
                    name=f"Exposure · {record.source}"[:255],
                    source_type=SourceType.API,
                    path=source_path,
                    description=(
                        "Exposure intelligence metadata. Raw passwords, tokens, cookies and "
                        "other secret values are not persisted by this workflow."
                    ),
                )
                existing_sources[source_path] = source
                out.sources_created += 1

            marker = f"exposure_snapshot={snapshot}"
            duplicate = next(
                (
                    evidence
                    for evidence in self.evidence_service.repository.get_by_source(source.id)
                    if not evidence.is_deleted
                    and (evidence.description or "").startswith(marker + "\n")
                ),
                None,
            )
            if duplicate is not None:
                out.records_skipped += 1
                continue

            metadata = {
                "workflow": "exposure_intelligence",
                "provenance_version": 1,
                "query": {
                    "capability": result.capability,
                    "value": result.value,
                },
                "summary": asdict(result.summary),
                "record": safe_record,
                "snapshot_key": snapshot,
                "person_identity_confirmed": False,
                "ownership_inferred": False,
                "raw_secret_values_stored": False,
                "secret_fields_redacted": sanitized.redacted_count,
                "verification_method": "exposure_source_observation",
            }
            metadata = self.data_sanitizer.sanitize(metadata).value

            self.evidence_service.create_evidence(
                case_id=case_id,
                source_id=source.id,
                evidence_type=EvidenceType.METADATA,
                title=record.display_name[:255],
                value=(record.source_url or f"{record.source}:{record.record_id}")[:1024],
                description=(
                    marker
                    + "\nExposure intelligence observation; identity/ownership is not inferred."
                ),
                metadata_json=_json(metadata),
            )
            out.evidences_created += 1
            out.records_persisted += 1

        return out

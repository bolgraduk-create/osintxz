"""Analyst-selected PERSON profile associations from existing investigation data.

The service does not claim identity ownership.  It creates a small provenance
Evidence record documenting that an analyst chose an already-persisted entity
for a PERSON card, and links that Evidence to both entities.  The original
OSINT Evidence remains untouched and can be referenced from metadata.

Transaction ownership remains with the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from uuid import uuid4

from app.models.entity import EntityType
from app.models.evidence import EvidenceType
from app.models.source import SourceType


@dataclass(slots=True)
class PersonProfileSelectionResult:
    evidence_id: str
    source_id: str
    selected_entity_id: str
    duplicate: bool = False


class PersonProfileSelectionService:
    """Persist explicit analyst selection of existing data for a PERSON card."""

    TYPE_TO_EVIDENCE: dict[EntityType, EvidenceType] = {
        EntityType.URL: EvidenceType.LINK,
        EntityType.DOMAIN: EvidenceType.LINK,
        EntityType.EMAIL: EvidenceType.EMAIL,
        EntityType.PHONE: EvidenceType.PHONE,
        EntityType.USERNAME: EvidenceType.USERNAME,
        EntityType.ACCOUNT: EvidenceType.USERNAME,
    }

    def __init__(
        self,
        *,
        source_service: Any,
        evidence_service: Any,
        evidence_link_service: Any,
    ) -> None:
        self.source_service = source_service
        self.evidence_service = evidence_service
        self.evidence_link_service = evidence_link_service

    def add(self, *, person: Any, candidate: Any) -> PersonProfileSelectionResult:
        self._validate(person=person, candidate=candidate)

        person_id = getattr(person, "id")
        candidate_id = getattr(candidate, "id")
        case_id = getattr(person, "case_id")

        if self._already_selected(person_id=person_id, candidate_id=candidate_id):
            return PersonProfileSelectionResult(
                evidence_id="",
                source_id="",
                selected_entity_id=str(candidate_id),
                duplicate=True,
            )

        candidate_metadata = self._metadata_dict(getattr(candidate, "metadata_json", None))
        candidate_type = getattr(candidate, "entity_type", EntityType.OTHER)
        if not isinstance(candidate_type, EntityType):
            try:
                candidate_type = EntityType(str(getattr(candidate_type, "value", candidate_type)))
            except (TypeError, ValueError):
                candidate_type = EntityType.OTHER

        original_evidence_id = str(candidate_metadata.get("evidence_id") or "")
        original_source_id = str(candidate_metadata.get("source_id") or "")
        connector = str(candidate_metadata.get("connector") or candidate_metadata.get("finding_source") or "")
        finding_url = str(candidate_metadata.get("finding_url") or candidate_metadata.get("url") or "")
        candidate_value = str(getattr(candidate, "value", "") or "")
        type_label = candidate_type.value.replace("_", " ").title()

        selection_token = uuid4().hex
        source = self.source_service.create_source(
            case_id=case_id,
            name=f"Analyst selection · {type_label} · {candidate_value}"[:255],
            source_type=SourceType.OTHER,
            path=f"manual://person-profile/{person_id}/{selection_token}",
            description=(
                "Analyst selected an already-persisted investigation entity for a PERSON card. "
                "This records relevance only and does not independently verify account ownership "
                "or identity."
            ),
        )

        evidence = self.evidence_service.create_evidence(
            case_id=case_id,
            source_id=source.id,
            evidence_type=self.TYPE_TO_EVIDENCE.get(candidate_type, EvidenceType.OTHER),
            title=f"Profile selection · {type_label} · {candidate_value}"[:255],
            value=candidate_value[:1024],
            description=(
                "Analyst-selected existing OSINT/investigation data for this person profile. "
                "Association is explicit but remains unverified unless corroborated separately."
            ),
        )
        evidence.metadata_json = json.dumps(
            {
                "workflow": "person_profile_selection",
                "association_basis": "analyst_selected_existing_intelligence",
                "identity_verified": False,
                "person_entity_id": str(person_id),
                "selected_entity_id": str(candidate_id),
                "selected_entity_type": candidate_type.value,
                "selected_entity_value": candidate_value,
                "supporting_evidence_id": original_evidence_id,
                "supporting_source_id": original_source_id,
                "connector": connector,
                "finding_url": finding_url,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        self._flush_evidence()

        self.evidence_link_service.ensure_link(
            evidence_id=evidence.id,
            entity_id=person_id,
        )
        self.evidence_link_service.ensure_link(
            evidence_id=evidence.id,
            entity_id=candidate_id,
        )

        return PersonProfileSelectionResult(
            evidence_id=str(evidence.id),
            source_id=str(source.id),
            selected_entity_id=str(candidate_id),
        )

    def _already_selected(self, *, person_id: Any, candidate_id: Any) -> bool:
        try:
            evidence_rows = list(
                self.evidence_link_service.get_evidence_objects_for_entity(person_id) or []
            )
        except Exception:
            return False

        wanted = str(candidate_id)
        for evidence in evidence_rows:
            metadata = self._metadata_dict(getattr(evidence, "metadata_json", None))
            if (
                metadata.get("workflow") == "person_profile_selection"
                and str(metadata.get("selected_entity_id") or "") == wanted
            ):
                return True
        return False

    @staticmethod
    def _validate(*, person: Any, candidate: Any) -> None:
        if person is None or candidate is None:
            raise ValueError("Person and candidate entities are required.")
        person_type = getattr(getattr(person, "entity_type", None), "value", getattr(person, "entity_type", ""))
        if str(person_type) != EntityType.PERSON.value:
            raise ValueError("Profile selections can only be attached to PERSON entities.")
        if getattr(person, "id", None) == getattr(candidate, "id", None):
            raise ValueError("A person cannot be selected as profile data for itself.")
        if getattr(person, "case_id", None) != getattr(candidate, "case_id", None):
            raise ValueError("Profile data must belong to the same investigation.")

    def _flush_evidence(self) -> None:
        repository = getattr(self.evidence_service, "repository", None)
        session = getattr(repository, "session", None)
        if session is not None:
            session.flush()

    @staticmethod
    def _metadata_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

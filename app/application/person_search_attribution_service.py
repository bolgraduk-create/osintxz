"""R14.3e — analyst-scoped search attribution to one PERSON.

A search can persist many technical Entity rows (email, phone, username, URL,
domain, IP, etc.) because those objects are required by provenance, graph,
pivoting and identity resolution.  This service creates one explicit
append-only attribution Evidence record that groups the persisted result
entities under the PERSON selected by the analyst for that search run.

The attribution means "this result was collected in the context of this
person".  It does NOT mean account ownership or identity verification.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable
from uuid import uuid4

from app.models.entity import EntityType
from app.models.evidence import EvidenceType
from app.models.source import SourceType


@dataclass(slots=True)
class PersonSearchAttributionResult:
    evidence_id: str
    source_id: str
    person_entity_id: str
    attributed_entity_ids: tuple[str, ...]
    links_created: int


class PersonSearchAttributionService:
    WORKFLOW = "person_search_attribution"

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

    def attribute(
        self,
        *,
        person: Any,
        entities: Iterable[Any],
        search_summary: dict[str, Any] | None = None,
    ) -> PersonSearchAttributionResult | None:
        self._validate_person(person)

        person_id = getattr(person, "id")
        case_id = getattr(person, "case_id")
        unique_entities: dict[str, Any] = {}

        for entity in entities:
            entity_id = str(getattr(entity, "id", "") or "").strip()
            if not entity_id or entity_id == str(person_id):
                continue
            if getattr(entity, "case_id", None) != case_id:
                continue
            unique_entities[entity_id] = entity

        if not unique_entities:
            return None

        summary = dict(search_summary or {})
        run_token = uuid4().hex

        source = self.source_service.create_source(
            case_id=case_id,
            name=(
                "Person-scoped investigation search · "
                f"{getattr(person, 'value', 'Person')}"
            )[:255],
            source_type=SourceType.OTHER,
            path=(
                "manual://person-search-attribution/"
                f"{person_id}/{run_token}"
            ),
            description=(
                "Analyst selected this PERSON as the target context for an "
                "investigation search. The association records relevance and "
                "does not independently verify ownership or identity."
            ),
        )

        evidence = self.evidence_service.create_evidence(
            case_id=case_id,
            source_id=source.id,
            evidence_type=EvidenceType.OTHER,
            title=(
                "Search attribution · "
                f"{getattr(person, 'value', 'Person')}"
            )[:255],
            value=(
                f"{len(unique_entities)} persisted result "
                f"{'entity' if len(unique_entities) == 1 else 'entities'}"
            ),
            description=(
                "Persisted technical entities from one analyst-scoped search "
                "are associated with the selected PERSON for investigation "
                "context only. Identity confirmation remains a separate review."
            ),
        )

        evidence.metadata_json = json.dumps(
            {
                "workflow": self.WORKFLOW,
                "association_basis": "analyst_selected_search_target",
                "identity_verified": False,
                "person_entity_id": str(person_id),
                "attributed_entity_ids": sorted(unique_entities),
                "attributed_entity_count": len(unique_entities),
                "search_summary": summary,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

        self._flush_evidence()

        links_created = 0
        _, created = self.evidence_link_service.ensure_link(
            evidence_id=evidence.id,
            entity_id=person_id,
        )
        links_created += int(created)

        for entity_id in sorted(unique_entities):
            entity = unique_entities[entity_id]
            _, created = self.evidence_link_service.ensure_link(
                evidence_id=evidence.id,
                entity_id=getattr(entity, "id"),
            )
            links_created += int(created)

        return PersonSearchAttributionResult(
            evidence_id=str(evidence.id),
            source_id=str(source.id),
            person_entity_id=str(person_id),
            attributed_entity_ids=tuple(sorted(unique_entities)),
            links_created=links_created,
        )

    @staticmethod
    def _validate_person(person: Any) -> None:
        if person is None:
            raise ValueError("A PERSON search target is required.")

        raw_type = getattr(person, "entity_type", None)
        value = str(
            getattr(raw_type, "value", raw_type)
            or ""
        ).strip().lower()

        if value != EntityType.PERSON.value:
            raise ValueError("Search attribution target must be a PERSON entity.")

    def _flush_evidence(self) -> None:
        repository = getattr(
            self.evidence_service,
            "repository",
            None,
        )
        session = getattr(
            repository,
            "session",
            None,
        )
        if session is not None:
            session.flush()


__all__ = [
    "PersonSearchAttributionResult",
    "PersonSearchAttributionService",
]

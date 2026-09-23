"""Append-only analyst identity decisions for PERSON profile candidates.

R14.3a records human review separately from machine confidence.  A manual
CONFIRMED decision is authoritative for the investigation workflow, but it does
not rewrite the candidate's machine confidence score.

Transactions remain owned by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any
from uuid import uuid4

from app.models.entity import EntityType
from app.models.evidence import EvidenceType
from app.models.source import SourceType


class IdentityReviewDecision(str, Enum):
    CONFIRMED = "confirmed"
    REVIEW = "review"
    REJECTED = "rejected"
    UNREVIEWED = "unreviewed"


@dataclass(slots=True)
class PersonIdentityReviewResult:
    evidence_id: str
    source_id: str
    candidate_entity_id: str
    decision: str
    previous_decision: str
    duplicate: bool = False


class PersonIdentityReviewService:
    """Persist and read analyst identity decisions without deleting history."""

    WORKFLOW = "person_identity_review"

    REVIEWABLE_TYPES = {
        EntityType.USERNAME,
        EntityType.ACCOUNT,
        EntityType.URL,
        EntityType.DOMAIN,
    }

    TYPE_TO_EVIDENCE = {
        EntityType.USERNAME: EvidenceType.USERNAME,
        EntityType.ACCOUNT: EvidenceType.USERNAME,
        EntityType.URL: EvidenceType.LINK,
        EntityType.DOMAIN: EvidenceType.LINK,
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

    def record(
        self,
        *,
        person: Any,
        candidate: Any,
        decision: str | IdentityReviewDecision,
        note: str = "",
    ) -> PersonIdentityReviewResult:
        normalized_decision = self._normalize_decision(decision)
        self._validate(person=person, candidate=candidate)

        person_id = getattr(person, "id")
        candidate_id = getattr(candidate, "id")
        case_id = getattr(person, "case_id")
        note_text = self._clean_note(note)

        latest = self.latest_decisions(person_id).get(str(candidate_id), {})
        previous_decision = str(
            latest.get("decision")
            or IdentityReviewDecision.UNREVIEWED.value
        )

        if (
            previous_decision == normalized_decision.value
            and str(latest.get("note") or "") == note_text
        ):
            return PersonIdentityReviewResult(
                evidence_id=str(latest.get("evidenceId") or ""),
                source_id=str(latest.get("sourceId") or ""),
                candidate_entity_id=str(candidate_id),
                decision=normalized_decision.value,
                previous_decision=previous_decision,
                duplicate=True,
            )

        candidate_type = self._entity_type(candidate)
        candidate_metadata = self._metadata_dict(
            getattr(candidate, "metadata_json", None)
        )
        candidate_value = str(
            getattr(candidate, "value", "")
            or ""
        )
        machine_confidence = self._optional_float(
            getattr(candidate, "confidence", None)
        )

        source = self.source_service.create_source(
            case_id=case_id,
            name=(
                "Identity review · "
                f"{normalized_decision.value.upper()} · "
                f"{candidate_value}"
            )[:255],
            source_type=SourceType.OTHER,
            path=(
                "manual://identity-review/"
                f"{person_id}/{candidate_id}/{uuid4().hex}"
            ),
            description=(
                "Append-only analyst identity review decision. "
                "Human review is stored separately from machine confidence."
            ),
        )

        evidence = self.evidence_service.create_evidence(
            case_id=case_id,
            source_id=source.id,
            evidence_type=self.TYPE_TO_EVIDENCE.get(
                candidate_type,
                EvidenceType.OTHER,
            ),
            title=(
                "Identity decision · "
                f"{normalized_decision.value.upper()} · "
                f"{candidate_value}"
            )[:255],
            value=candidate_value[:1024],
            description=(
                "Analyst identity decision for an existing investigation "
                "candidate. This record preserves the review audit trail."
            ),
        )

        evidence.metadata_json = json.dumps(
            {
                "workflow": self.WORKFLOW,
                "association_basis": "analyst_identity_decision",
                "decision": normalized_decision.value,
                "previous_decision": previous_decision,
                "identity_verified": (
                    normalized_decision
                    is IdentityReviewDecision.CONFIRMED
                ),
                "person_entity_id": str(person_id),
                "candidate_entity_id": str(candidate_id),
                "candidate_entity_type": candidate_type.value,
                "candidate_entity_value": candidate_value,
                "machine_confidence": machine_confidence,
                "analyst_note": note_text,
                "supporting_evidence_id": str(
                    candidate_metadata.get("evidence_id")
                    or ""
                ),
                "supporting_source_id": str(
                    candidate_metadata.get("source_id")
                    or ""
                ),
                "connector": str(
                    candidate_metadata.get("connector")
                    or candidate_metadata.get("finding_source")
                    or ""
                ),
                "finding_url": str(
                    candidate_metadata.get("finding_url")
                    or candidate_metadata.get("url")
                    or ""
                ),
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

        return PersonIdentityReviewResult(
            evidence_id=str(evidence.id),
            source_id=str(source.id),
            candidate_entity_id=str(candidate_id),
            decision=normalized_decision.value,
            previous_decision=previous_decision,
            duplicate=False,
        )

    def latest_decisions(
        self,
        person_id: Any,
    ) -> dict[str, dict[str, Any]]:
        try:
            evidence_rows = list(
                self.evidence_link_service
                .get_evidence_objects_for_entity(
                    person_id
                )
                or []
            )
        except Exception:
            return {}

        return self.latest_decisions_from_evidence(
            evidence_rows
        )

    @classmethod
    def latest_decisions_from_evidence(
        cls,
        evidence_rows: list[Any],
    ) -> dict[str, dict[str, Any]]:
        """Return the newest decision per candidate while preserving history count."""

        output: dict[str, dict[str, Any]] = {}

        for evidence in evidence_rows:
            metadata = cls._metadata_dict(
                getattr(evidence, "metadata_json", None)
            )

            if metadata.get("workflow") != cls.WORKFLOW:
                continue

            candidate_id = str(
                metadata.get("candidate_entity_id")
                or ""
            ).strip()

            if not candidate_id:
                continue

            decision = str(
                metadata.get("decision")
                or ""
            ).strip().lower()

            if decision not in {
                IdentityReviewDecision.CONFIRMED.value,
                IdentityReviewDecision.REVIEW.value,
                IdentityReviewDecision.REJECTED.value,
            }:
                continue

            created_at = getattr(
                evidence,
                "created_at",
                None,
            )
            sort_key = (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at or "")
            )

            existing = output.get(candidate_id)
            history_count = int(
                existing.get("historyCount", 0)
                if existing
                else 0
            ) + 1

            payload = {
                "decision": decision,
                "label": cls._decision_label(decision),
                "note": str(
                    metadata.get("analyst_note")
                    or ""
                ),
                "identityVerified": bool(
                    metadata.get("identity_verified")
                ),
                "machineConfidence": metadata.get(
                    "machine_confidence"
                ),
                "evidenceId": str(
                    getattr(evidence, "id", "")
                    or ""
                ),
                "sourceId": str(
                    getattr(evidence, "source_id", "")
                    or ""
                ),
                "reviewedAt": sort_key,
                "historyCount": history_count,
                "_sortKey": sort_key,
            }

            if (
                existing is None
                or sort_key >= str(
                    existing.get("_sortKey")
                    or ""
                )
            ):
                output[candidate_id] = payload
            else:
                existing["historyCount"] = history_count

        for payload in output.values():
            payload.pop("_sortKey", None)

        return output

    @staticmethod
    def _decision_label(
        decision: str,
    ) -> str:
        return {
            IdentityReviewDecision.CONFIRMED.value: "Confirmed",
            IdentityReviewDecision.REVIEW.value: "Needs review",
            IdentityReviewDecision.REJECTED.value: "Rejected",
        }.get(decision, "Unreviewed")

    @classmethod
    def _normalize_decision(
        cls,
        value: str | IdentityReviewDecision,
    ) -> IdentityReviewDecision:
        if isinstance(value, IdentityReviewDecision):
            decision = value
        else:
            try:
                decision = IdentityReviewDecision(
                    str(value or "").strip().lower()
                )
            except ValueError as exc:
                raise ValueError(
                    "Identity decision must be confirmed, review, or rejected."
                ) from exc

        if decision is IdentityReviewDecision.UNREVIEWED:
            raise ValueError(
                "UNREVIEWED is derived state and is not persisted."
            )

        return decision

    @classmethod
    def _validate(
        cls,
        *,
        person: Any,
        candidate: Any,
    ) -> None:
        if person is None or candidate is None:
            raise ValueError(
                "Person and candidate entities are required."
            )

        if cls._entity_type(person) is not EntityType.PERSON:
            raise ValueError(
                "Identity review requires a PERSON entity."
            )

        candidate_type = cls._entity_type(candidate)

        if candidate_type not in cls.REVIEWABLE_TYPES:
            raise ValueError(
                "Identity review currently supports username/account/profile candidates."
            )

        if getattr(person, "id", None) == getattr(candidate, "id", None):
            raise ValueError(
                "A person cannot be reviewed against itself."
            )

        if getattr(person, "case_id", None) != getattr(candidate, "case_id", None):
            raise ValueError(
                "Identity candidates must belong to the same investigation."
            )

    @staticmethod
    def _entity_type(value: Any) -> EntityType:
        raw = getattr(value, "entity_type", EntityType.OTHER)

        if isinstance(raw, EntityType):
            return raw

        try:
            return EntityType(
                str(getattr(raw, "value", raw))
            )
        except (TypeError, ValueError):
            return EntityType.OTHER

    @staticmethod
    def _clean_note(
        value: Any,
    ) -> str:
        return " ".join(
            str(value or "")
            .strip()
            .split()
        )[:1000]

    @staticmethod
    def _optional_float(
        value: Any,
    ) -> float | None:
        try:
            return round(float(value), 6)
        except (TypeError, ValueError):
            return None

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

    @staticmethod
    def _metadata_dict(
        value: Any,
    ) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)

        if not value:
            return {}

        try:
            parsed = json.loads(str(value))
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return {}

        return parsed if isinstance(parsed, dict) else {}


__all__ = [
    "IdentityReviewDecision",
    "PersonIdentityReviewResult",
    "PersonIdentityReviewService",
]

"""Thread-owned Registry Intelligence worker for the QML desktop interface.

The desktop never reads central registry mirror tables directly.  Each run owns
its SQLAlchemy session and canonical ServiceContainer inside the worker thread,
then calls RegistryIntelligenceService which reaches remote registry providers.
Only plain dictionaries/lists cross the Qt thread boundary.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
)


REGISTRY_UI_QUERY_MODES = (
    "EDRPOU",
    "Company name",
    "FOP name",
    "Court case number",
)


def build_registry_ui_query(mode: str, value: str) -> RegistryQuery:
    """Translate one explicit desktop query mode into the stable registry contract."""
    normalized_mode = str(mode or "").strip().casefold()
    normalized_value = str(value or "").strip()
    if not normalized_value:
        raise ValueError("Registry search requires a value.")

    if normalized_mode == "edrpou":
        return RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.REGISTRATION_ID,
            value=normalized_value,
            country="UA",
            limit=20,
            timeout=30,
            sources=("ua_edr_business",),
            entity_kind=RegistryEntityKind.COMPANY,
        )

    if normalized_mode == "company name":
        return RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.NAME,
            value=normalized_value,
            country="UA",
            limit=20,
            timeout=30,
            sources=("ua_edr_business",),
            entity_kind=RegistryEntityKind.COMPANY,
        )

    if normalized_mode == "fop name":
        return RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.PERSON_NAME,
            value=normalized_value,
            country="UA",
            limit=20,
            timeout=30,
            sources=("ua_edr_business",),
            entity_kind=RegistryEntityKind.SOLE_TRADER,
        )

    if normalized_mode == "court case number":
        return RegistryQuery(
            domain=RegistryDomain.COURT,
            kind=RegistryQueryKind.CASE_NUMBER,
            value=normalized_value,
            country="UA",
            limit=20,
            timeout=30,
            sources=("ua_edrsr",),
            entity_kind=RegistryEntityKind.COURT_CASE,
        )

    raise ValueError("Unsupported Registry Intelligence query mode.")


class RegistrySearchWorker(QObject):
    """Execute one bounded registry search or search+persist operation."""

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        mode: str,
        value: str,
        persist: bool = False,
        case_id: str | None = None,
    ) -> None:
        super().__init__()
        self.mode = str(mode or "").strip()
        self.value = str(value or "").strip()
        self.persist = bool(persist)
        self.case_id = str(case_id or "").strip()

    @Slot()
    def run(self) -> None:
        from app.core.service_container import ServiceContainer
        from app.database.session import create_session

        started = perf_counter()
        session = None
        container = None

        try:
            query = build_registry_ui_query(self.mode, self.value)
            if self.persist and not self.case_id:
                raise ValueError(
                    "Select an investigation before saving registry intelligence."
                )

            session = create_session()
            container = ServiceContainer(session)
            service = container.registry_intelligence_service

            if self.persist:
                enrichment = service.enrich(
                    query,
                    case_id=UUID(self.case_id),
                )
                search_result = enrichment.search
                persistence = enrichment.persistence
            else:
                search_result = service.search(query)
                persistence = None

            snapshot = self._snapshot_result(
                query=query,
                search_result=search_result,
                persistence=persistence,
                mode=self.mode,
                persist=self.persist,
            )

            if self.persist:
                container.commit()
            else:
                # Explicitly close any transaction opened while constructing
                # services. Search itself is remote-only on the desktop.
                container.rollback()

            self.succeeded.emit(
                {
                    "snapshot": snapshot,
                    "duration": perf_counter() - started,
                }
            )
        except Exception as exc:
            try:
                if container is not None:
                    container.rollback()
                elif session is not None:
                    session.rollback()
            except Exception:
                pass

            self.failed.emit(
                {
                    "error": str(exc),
                    "duration": perf_counter() - started,
                    "operation": "save" if self.persist else "search",
                    "mode": self.mode,
                    "value": self.value,
                }
            )
        finally:
            try:
                if container is not None:
                    container.close()
                elif session is not None:
                    session.close()
            except Exception:
                pass

    @classmethod
    def _snapshot_result(
        cls,
        *,
        query: RegistryQuery,
        search_result: Any,
        persistence: Any,
        mode: str,
        persist: bool,
    ) -> dict[str, Any]:
        records = [
            cls._snapshot_record(record)
            for record in list(getattr(search_result, "records", ()) or ())
        ]
        providers = [
            cls._snapshot_provider_result(item)
            for item in list(
                getattr(search_result, "provider_results", ()) or ()
            )
        ]
        metadata = dict(getattr(search_result, "metadata", {}) or {})
        route = dict(metadata.get("route") or {})
        provider_errors = [
            item
            for item in providers
            if item["status"] in {"failed", "not_supported"}
            and item["error"]
        ]
        persistable_count = sum(
            1 for record in records if record["persistable"]
        )
        candidate_count = sum(
            1 for record in records if record["candidateOnly"]
        )
        sensitive_count = sum(
            1 for record in records if record["sensitiveLegalData"]
        )

        return {
            "hasRun": True,
            "operation": "save" if persist else "search",
            "mode": str(mode),
            "value": query.value,
            "query": {
                "domain": query.domain.value,
                "kind": query.kind.value,
                "country": query.country or "",
                "sources": list(query.sources),
                "entityKind": (
                    query.entity_kind.value if query.entity_kind else ""
                ),
                "limit": query.limit,
            },
            "records": records,
            "providers": providers,
            "route": route,
            "summary": {
                "records": len(records),
                "persistable": persistable_count,
                "candidates": candidate_count,
                "sensitiveLegal": sensitive_count,
                "providerErrors": len(provider_errors),
            },
            "persistence": cls._snapshot_persistence(persistence),
        }

    @classmethod
    def _snapshot_record(cls, record: Any) -> dict[str, Any]:
        metadata = dict(getattr(record, "metadata", {}) or {})
        identifiers = {
            str(key): str(value)
            for key, value in dict(
                getattr(record, "identifiers", {}) or {}
            ).items()
            if value is not None and str(value).strip()
        }
        candidate_only = bool(
            metadata.get("candidate_only") or metadata.get("lead_only")
        )
        domain = cls._enum_value(getattr(record, "domain", None))
        entity_kind = cls._enum_value(
            getattr(record, "entity_kind", None)
        )
        sensitive = bool(
            getattr(record, "sensitive_legal_data", False)
        )

        detail_parts: list[str] = []
        if domain == RegistryDomain.COURT.value:
            for value in (
                metadata.get("court_name"),
                metadata.get("adjudication_date"),
                metadata.get("judge"),
            ):
                text = str(value or "").strip()
                if text:
                    detail_parts.append(text)
        else:
            for value in (
                getattr(record, "legal_form", None),
                getattr(record, "status", None),
                getattr(record, "legal_address", None),
            ):
                text = str(value or "").strip()
                if text:
                    detail_parts.append(text)

        identifier_text = " · ".join(
            f"{key}: {value}"
            for key, value in identifiers.items()
        )
        if not identifier_text:
            registration_id = str(
                getattr(record, "registration_id", None) or ""
            ).strip()
            if registration_id:
                identifier_text = registration_id

        return {
            "id": (
                f"{getattr(record, 'provider', '')}:"
                f"{getattr(record, 'record_id', '')}"
            ),
            "recordId": str(getattr(record, "record_id", "") or ""),
            "title": str(getattr(record, "display_name", "") or ""),
            "detail": " · ".join(detail_parts) or "Official registry record",
            "provider": str(getattr(record, "provider", "") or ""),
            "domain": domain,
            "entityKind": entity_kind,
            "country": str(getattr(record, "country", "") or ""),
            "jurisdiction": str(
                getattr(record, "jurisdiction", "") or ""
            ),
            "status": str(getattr(record, "status", "") or ""),
            "registrationId": str(
                getattr(record, "registration_id", "") or ""
            ),
            "lei": str(getattr(record, "lei", "") or ""),
            "legalForm": str(
                getattr(record, "legal_form", "") or ""
            ),
            "legalAddress": str(
                getattr(record, "legal_address", "") or ""
            ),
            "sourceUrl": str(
                getattr(record, "source_url", "") or ""
            ),
            "confidence": cls._safe_float(
                getattr(record, "confidence", 0.0)
            ),
            "reliability": cls._safe_float(
                getattr(record, "reliability", 0.0)
            ),
            "trustScore": cls._safe_float(
                getattr(record, "trust_score", 0.0)
            ),
            "retrievedAt": str(
                getattr(record, "retrieved_at", "") or ""
            ),
            "rawReference": str(
                getattr(record, "raw_reference", "") or ""
            ),
            "identifiers": identifiers,
            "identifiersText": identifier_text,
            "metadata": metadata,
            "candidateOnly": candidate_only,
            "persistable": not candidate_only,
            "sensitiveLegalData": sensitive,
            "courtName": str(metadata.get("court_name") or ""),
            "courtInstance": str(metadata.get("court_instance") or ""),
            "courtRegion": str(metadata.get("court_region") or ""),
            "judge": str(metadata.get("judge") or ""),
            "adjudicationDate": str(
                metadata.get("adjudication_date") or ""
            ),
            "categoryName": str(
                metadata.get("category_name") or ""
            ),
            "judgmentName": str(
                metadata.get("judgment_name") or ""
            ),
            "caseNumber": str(metadata.get("case_number") or ""),
            "legalOutcome": str(
                metadata.get("legal_outcome") or "unknown"
            ),
            "personIdentityInferenceProhibited": bool(
                metadata.get("person_identity_inference_prohibited")
            ),
            "legalOutcomeInferenceProhibited": bool(
                metadata.get("legal_outcome_inference_prohibited")
            ),
        }

    @classmethod
    def _snapshot_provider_result(cls, result: Any) -> dict[str, Any]:
        metadata = dict(getattr(result, "metadata", {}) or {})
        records = list(getattr(result, "records", ()) or ())
        return {
            "provider": str(getattr(result, "provider", "") or ""),
            "status": cls._enum_value(getattr(result, "status", None)),
            "error": str(getattr(result, "error", "") or ""),
            "records": len(records),
            "transport": str(metadata.get("transport") or ""),
            "accessMode": str(metadata.get("access_mode") or ""),
            "sourceType": str(metadata.get("source_type") or ""),
            "trustScore": cls._safe_float(metadata.get("trust_score")),
            "identityWarning": str(
                metadata.get("identity_warning") or ""
            ),
            "metadata": metadata,
        }

    @classmethod
    def _snapshot_persistence(cls, persistence: Any) -> dict[str, Any]:
        if persistence is None:
            return {
                "attempted": False,
                "sourcesCreated": 0,
                "evidencesCreated": 0,
                "entitiesCreated": 0,
                "linksCreated": 0,
                "skippedRecords": 0,
                "errors": [],
                "records": [],
            }

        persisted_records: list[dict[str, Any]] = []
        for item in list(getattr(persistence, "records", ()) or ()):
            source = getattr(item, "source", None)
            evidence = getattr(item, "evidence", None)
            entities = list(getattr(item, "entities", ()) or ())
            persisted_records.append(
                {
                    "sourceId": str(getattr(source, "id", "") or ""),
                    "evidenceId": str(
                        getattr(evidence, "id", "") or ""
                    ),
                    "entityIds": [
                        str(getattr(entity, "id", "") or "")
                        for entity in entities
                    ],
                    "resolutionMethod": str(
                        getattr(item, "resolution_method", "") or ""
                    ),
                }
            )

        return {
            "attempted": True,
            "sourcesCreated": int(
                getattr(persistence, "sources_created", 0) or 0
            ),
            "evidencesCreated": int(
                getattr(persistence, "evidences_created", 0) or 0
            ),
            "entitiesCreated": int(
                getattr(persistence, "entities_created", 0) or 0
            ),
            "linksCreated": int(
                getattr(persistence, "links_created", 0) or 0
            ),
            "skippedRecords": int(
                getattr(persistence, "skipped_records", 0) or 0
            ),
            "errors": [
                str(item)
                for item in list(getattr(persistence, "errors", ()) or ())
            ],
            "records": persisted_records,
        }

    @staticmethod
    def _enum_value(value: Any) -> str:
        return str(getattr(value, "value", None) or value or "")

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

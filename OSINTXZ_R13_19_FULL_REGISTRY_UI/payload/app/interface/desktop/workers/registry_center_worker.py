from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.interface.desktop.workers.registry_search_worker import RegistrySearchWorker
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
)


def build_registry_center_query(
    *,
    domain: str,
    query_kind: str,
    value: str,
    country: str = "",
    source_code: str = "",
    limit: int = 20,
    timeout: int = 30,
) -> RegistryQuery:
    normalized_value = str(value or "").strip()
    if not normalized_value:
        raise ValueError("Registry search requires a value.")

    try:
        domain_enum = RegistryDomain(str(domain or "").strip().casefold())
    except ValueError as exc:
        raise ValueError("Choose a valid registry domain.") from exc

    try:
        kind_enum = RegistryQueryKind(str(query_kind or "").strip().casefold())
    except ValueError as exc:
        raise ValueError("Choose a valid registry query kind.") from exc

    normalized_country = str(country or "").strip().upper()
    if normalized_country and (
        len(normalized_country) != 2 or not normalized_country.isalpha()
    ):
        raise ValueError("Country must be a two-letter ISO code or blank.")

    normalized_source = str(source_code or "").strip().casefold()
    entity_kind = _infer_entity_kind(domain_enum, kind_enum)

    return RegistryQuery(
        domain=domain_enum,
        kind=kind_enum,
        value=normalized_value,
        country=normalized_country or None,
        limit=max(1, min(int(limit), 100)),
        timeout=max(1, int(timeout)),
        sources=(normalized_source,) if normalized_source else (),
        entity_kind=entity_kind,
    )


def _infer_entity_kind(
    domain: RegistryDomain,
    kind: RegistryQueryKind,
) -> RegistryEntityKind | None:
    if domain is RegistryDomain.BUSINESS:
        if kind is RegistryQueryKind.PERSON_NAME:
            return RegistryEntityKind.PERSON
        if kind in {
            RegistryQueryKind.NAME,
            RegistryQueryKind.REGISTRATION_ID,
            RegistryQueryKind.LEI,
            RegistryQueryKind.TAX_ID,
            RegistryQueryKind.VAT_ID,
        }:
            return RegistryEntityKind.COMPANY
    if domain in {RegistryDomain.COURT, RegistryDomain.LEGAL}:
        if kind is RegistryQueryKind.CASE_NUMBER:
            return RegistryEntityKind.COURT_CASE
    if domain is RegistryDomain.INSOLVENCY:
        return RegistryEntityKind.INSOLVENCY
    if domain is RegistryDomain.PROPERTY:
        return RegistryEntityKind.PROPERTY_RECORD
    if domain is RegistryDomain.ENFORCEMENT:
        return RegistryEntityKind.ENFORCEMENT_RECORD
    if domain is RegistryDomain.PUBLIC_OFFICIAL:
        return RegistryEntityKind.PUBLIC_OFFICIAL
    if domain is RegistryDomain.WANTED:
        return RegistryEntityKind.WANTED_PERSON
    return None


class RegistryCenterWorker(QObject):
    """Run one advanced Registry search/enrichment in a thread-owned session."""

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        domain: str,
        query_kind: str,
        value: str,
        country: str = "",
        source_code: str = "",
        persist: bool = False,
        case_id: str = "",
        limit: int = 20,
        timeout: int = 30,
    ) -> None:
        super().__init__()
        self.domain = str(domain or "")
        self.query_kind = str(query_kind or "")
        self.value = str(value or "")
        self.country = str(country or "")
        self.source_code = str(source_code or "")
        self.persist = bool(persist)
        self.case_id = str(case_id or "")
        self.limit = int(limit)
        self.timeout = int(timeout)

    @Slot()
    def run(self) -> None:
        from app.core.service_container import ServiceContainer
        from app.database.session import create_session

        started = perf_counter()
        session = None
        container = None

        try:
            query = build_registry_center_query(
                domain=self.domain,
                query_kind=self.query_kind,
                value=self.value,
                country=self.country,
                source_code=self.source_code,
                limit=self.limit,
                timeout=self.timeout,
            )
            if self.persist and not self.case_id:
                raise ValueError(
                    "Select an investigation before saving registry intelligence."
                )

            session = create_session()
            container = ServiceContainer(session)
            service = container.registry_intelligence_service

            if self.persist:
                enrichment = service.enrich(query, case_id=UUID(self.case_id))
                search_result = enrichment.search
                persistence = enrichment.persistence
            else:
                search_result = service.search(query)
                persistence = None

            snapshot = self._snapshot_result(
                query=query,
                search_result=search_result,
                persistence=persistence,
                persist=self.persist,
            )

            if self.persist:
                container.commit()
            else:
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
        persist: bool,
    ) -> dict[str, Any]:
        records = [
            RegistrySearchWorker._snapshot_record(record)
            for record in list(getattr(search_result, "records", ()) or ())
        ]
        providers = [
            RegistrySearchWorker._snapshot_provider_result(item)
            for item in list(
                getattr(search_result, "provider_results", ()) or ()
            )
        ]
        metadata = dict(getattr(search_result, "metadata", {}) or {})
        route = dict(metadata.get("route") or {})
        blocked = list(route.get("blocked") or [])
        missing_sources = list(route.get("missing_sources") or [])

        provider_errors = [
            item
            for item in providers
            if item["status"] in {"failed", "not_supported"}
            and item["error"]
        ]
        persistable_count = sum(1 for record in records if record["persistable"])
        candidate_count = sum(1 for record in records if record["candidateOnly"])
        sensitive_count = sum(1 for record in records if record["sensitiveLegalData"])

        return {
            "hasRun": True,
            "operation": "save" if persist else "search",
            "status": (
                "completed_with_errors"
                if provider_errors or blocked or missing_sources
                else "completed"
            ),
            "value": query.value,
            "query": {
                "domain": query.domain.value,
                "kind": query.kind.value,
                "country": query.country or "",
                "sources": list(query.sources),
                "entityKind": query.entity_kind.value if query.entity_kind else "",
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
                "providerExecutions": len(providers),
                "providerErrors": len(provider_errors),
                "blocked": len(blocked),
                "missingSources": len(missing_sources),
            },
            "persistence": RegistrySearchWorker._snapshot_persistence(persistence),
        }

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.application.osint_recursive_enrichment_service import RecursiveEnrichmentSeed
from app.application.investigation_result_consolidation import consolidate_result_rows
from app.application.person_name_relevance import match_person_name_record
from app.application.unified_investigation_search import (
    UnifiedSeed,
    UnifiedSeedKind,
    build_initial_seeds,
    build_search_plan,
    dedupe_seeds,
    extract_remote_pivots,
    is_exact_recursive_seed,
    osint_target_for_seed,
    registry_queries_for_seed,
)
from app.intelligence_sources.adapters.contracts import RemoteSourceQuery
from app.interface.desktop.workers.federated_source_search_worker import (
    FederatedSourceSearchWorker,
)
from app.interface.desktop.workers.osint_collection_worker import OsintCollectionWorker
from app.interface.desktop.workers.registry_search_worker import RegistrySearchWorker
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.pivot_policy import PivotTraversalState


class UnifiedInvestigationSearchWorker(QObject):
    """One thread-owned, bounded search across every safe runtime layer."""

    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)

    ROOT_CLASSIC_LIMIT = 12
    CLASSIC_MAX_TARGETS = 28
    CLASSIC_TIME_BUDGET = 210.0
    CLASSIC_TIMEOUT = 15
    OPEN_WEB_ROOT_LIMIT = 8
    OPEN_WEB_TIMEOUT = 18
    FEDERATION_ROUTE_LIMIT = 56
    REGISTRY_QUERY_LIMIT = 18
    DISCOVERED_PIVOT_LIMIT = 18
    SECOND_WAVE_OPEN_WEB_LIMIT = 4

    def __init__(
        self,
        *,
        case_id: str,
        profile: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.case_id = str(case_id or "").strip()
        self.profile = dict(profile or {})
        self.options = dict(options or {})

    @Slot()
    def run(self) -> None:
        from app.core.service_container import ServiceContainer
        from app.database.session import create_session

        started = perf_counter()
        container = None
        session = None
        try:
            if not self.case_id:
                raise ValueError("Select an investigation before running unified search.")
            case_uuid = UUID(self.case_id)
            seeds = build_initial_seeds(self.profile)
            if not seeds:
                raise ValueError("Enter at least one known data point before searching.")

            use_classic = bool(self.options.get("classic", True))
            use_open_web = bool(self.options.get("openWeb", True))
            use_federation = bool(self.options.get("federation", True))
            use_registry = bool(self.options.get("registry", True))
            follow_pivots = bool(self.options.get("followPivots", True))
            include_sensitive_names = bool(
                self.options.get("includeSensitiveNameRoutes", False)
            )

            session = create_session()
            container = ServiceContainer(session)
            plan = build_search_plan(
                adapter_registry=container.remote_source_adapter_registry,
                seeds=seeds,
                include_sensitive_name_routes=include_sensitive_names,
            )

            results: list[dict[str, Any]] = []
            providers: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            pivots: list[UnifiedSeed] = []
            all_federation_records: list[Any] = []
            all_registry_records: list[Any] = []
            osint_snapshots: list[dict[str, Any]] = []
            open_web_snapshots: list[dict[str, Any]] = []
            state = PivotTraversalState()

            for seed, route in plan.guarded_routes:
                providers.append(
                    self._provider_row(
                        lane="Federation",
                        source=route.source_code,
                        status="guarded",
                        records=0,
                        seed=seed,
                        detail=route.reason or "Explicit execution required.",
                    )
                )

            self._emit(
                "planned",
                f"{len(seeds)} seed(s) · {len(plan.federation_routes)} Federation route(s) · "
                f"{len(plan.registry_queries)} Registry query(s).",
                seeds=len(seeds),
                providers=len(providers),
            )

            if use_classic:
                classic_roots = self._classic_seeds(container, plan.classic_seeds)[
                    : self.ROOT_CLASSIC_LIMIT
                ]
                if classic_roots:
                    self._emit("classic", f"Classic OSINT: {len(classic_roots)} root target(s).")
                    max_targets = (
                        self.CLASSIC_MAX_TARGETS if follow_pivots else len(classic_roots)
                    )
                    recursion = container.osint_recursive_enrichment_service.enrich(
                        case_id=case_uuid,
                        seeds=tuple(
                            RecursiveEnrichmentSeed(
                                target_type=osint_target_for_seed(seed),
                                value=seed.value,
                            )
                            for seed in classic_roots
                            if osint_target_for_seed(seed) is not None
                        ),
                        state=state,
                        seed_depth=0,
                        timeout=self.CLASSIC_TIMEOUT,
                        use_cache=True,
                        save_raw_output=False,
                        include_metadata=True,
                        include_related=True,
                        progress_callback=self._classic_progress,
                        max_targets=max(1, max_targets),
                        time_budget_seconds=self.CLASSIC_TIME_BUDGET,
                        per_target_new_entity_limit=8,
                    )
                    state = recursion.state
                    snap = OsintCollectionWorker._snapshot_recursive_enrichment(recursion)
                    osint_snapshots.append(snap)
                    self._append_osint_snapshot(snap, results, providers, errors)

            if use_open_web:
                open_web_roots = self._open_web_seeds(container, plan.open_web_seeds)[
                    : self.OPEN_WEB_ROOT_LIMIT
                ]
                for index, seed in enumerate(open_web_roots, start=1):
                    target_type = osint_target_for_seed(seed)
                    if target_type is None:
                        continue
                    self._emit(
                        "open_web",
                        f"Open-Web {index}/{len(open_web_roots)} · {seed.kind.value}: {seed.value}",
                    )
                    query = OpenWebQuery(
                        target_type=target_type,
                        value=seed.value,
                        case_id=self.case_id,
                        limit=25,
                        timeout=self.OPEN_WEB_TIMEOUT,
                        depth=0,
                    )
                    enrichment = container.open_web_enrichment_service.enrich(
                        query,
                        case_id=case_uuid,
                    )
                    snap = self._snapshot_open_web(enrichment, seed)
                    open_web_snapshots.append(snap)
                    self._append_open_web_snapshot(snap, results, providers, errors)
                    if follow_pivots:
                        expanded = container.open_web_recursive_pivot_service.expand(
                            case_id=case_uuid,
                            open_web_result=enrichment,
                            state=state,
                            timeout=self.CLASSIC_TIMEOUT,
                            use_cache=True,
                            save_raw_output=False,
                            include_metadata=True,
                            include_related=True,
                            progress_callback=self._classic_progress,
                            max_targets=8,
                            time_budget_seconds=75.0,
                            per_target_new_entity_limit=6,
                        )
                        if expanded.recursion is not None:
                            state = expanded.recursion.state
                            recursion_snap = OsintCollectionWorker._snapshot_recursive_enrichment(
                                expanded.recursion
                            )
                            osint_snapshots.append(recursion_snap)
                            self._append_osint_snapshot(
                                recursion_snap, results, providers, errors
                            )

            if use_federation:
                self._emit("federation", "Searching safe automatic Federation sources…")
                routes = plan.federation_routes[: self.FEDERATION_ROUTE_LIMIT]
                federation_records = self._run_federation_routes(
                    container=container,
                    routes=routes,
                    results=results,
                    providers=providers,
                    errors=errors,
                )
                all_federation_records.extend(federation_records)

            if use_registry:
                self._emit("registry", "Searching compatible Registry providers…")
                registry_records = self._run_registry_queries(
                    container=container,
                    items=plan.registry_queries[: self.REGISTRY_QUERY_LIMIT],
                    results=results,
                    providers=providers,
                    errors=errors,
                )
                all_registry_records.extend(registry_records)

            # Exact pivots from remote normalized records. Candidate names and
            # organizations are displayed but never recursively followed here.
            if follow_pivots:
                pivots.extend(
                    self._extract_pivots(
                        all_federation_records,
                        depth=1,
                        lane="federation",
                        default_country=self._country_hint(seeds),
                    )
                )
                pivots.extend(
                    self._extract_pivots(
                        all_registry_records,
                        depth=1,
                        lane="registry",
                        default_country=self._country_hint(seeds),
                    )
                )
                initial_keys = {seed.identity_key for seed in seeds}
                pivots = [
                    seed
                    for seed in dedupe_seeds(pivots)
                    if seed.identity_key not in initial_keys
                ][: self.DISCOVERED_PIVOT_LIMIT * 2]
                queued_pivots = [
                    seed for seed in pivots if is_exact_recursive_seed(seed)
                ][: self.DISCOVERED_PIVOT_LIMIT]

                if queued_pivots:
                    self._emit(
                        "pivots",
                        f"Following {len(queued_pivots)} exact discovered pivot(s); "
                        f"{len(pivots) - len(queued_pivots)} candidate value(s) remain for review.",
                        pivots=len(pivots),
                    )

                    if use_classic:
                        classic_pivots = self._classic_seeds(container, queued_pivots)
                        if classic_pivots:
                            recursion = container.osint_recursive_enrichment_service.enrich(
                                case_id=case_uuid,
                                seeds=tuple(
                                    RecursiveEnrichmentSeed(
                                        target_type=osint_target_for_seed(seed),
                                        value=seed.value,
                                    )
                                    for seed in classic_pivots
                                    if osint_target_for_seed(seed) is not None
                                ),
                                state=state,
                                seed_depth=1,
                                timeout=self.CLASSIC_TIMEOUT,
                                use_cache=True,
                                save_raw_output=False,
                                include_metadata=True,
                                include_related=True,
                                progress_callback=self._classic_progress,
                                max_targets=12,
                                time_budget_seconds=100.0,
                                per_target_new_entity_limit=6,
                            )
                            state = recursion.state
                            snap = OsintCollectionWorker._snapshot_recursive_enrichment(recursion)
                            osint_snapshots.append(snap)
                            self._append_osint_snapshot(snap, results, providers, errors)

                    pivot_plan = build_search_plan(
                        adapter_registry=container.remote_source_adapter_registry,
                        seeds=queued_pivots,
                        include_sensitive_name_routes=False,
                    )
                    if use_federation:
                        more_records = self._run_federation_routes(
                            container=container,
                            routes=pivot_plan.federation_routes[:24],
                            results=results,
                            providers=providers,
                            errors=errors,
                        )
                        all_federation_records.extend(more_records)
                    if use_registry:
                        more_registry = self._run_registry_queries(
                            container=container,
                            items=pivot_plan.registry_queries[:10],
                            results=results,
                            providers=providers,
                            errors=errors,
                        )
                        all_registry_records.extend(more_registry)
                    if use_open_web:
                        second_web = self._open_web_seeds(container, queued_pivots)[
                            : self.SECOND_WAVE_OPEN_WEB_LIMIT
                        ]
                        for seed in second_web:
                            target_type = osint_target_for_seed(seed)
                            if target_type is None:
                                continue
                            query = OpenWebQuery(
                                target_type=target_type,
                                value=seed.value,
                                case_id=self.case_id,
                                limit=15,
                                timeout=self.OPEN_WEB_TIMEOUT,
                                depth=1,
                            )
                            enrichment = container.open_web_enrichment_service.enrich(
                                query,
                                case_id=case_uuid,
                            )
                            snap = self._snapshot_open_web(enrichment, seed)
                            open_web_snapshots.append(snap)
                            self._append_open_web_snapshot(
                                snap, results, providers, errors
                            )

            # Existing OSINT/Open-Web enrichment persists safe findings into the
            # current case. Federation/Registry remain review-first/read-only here.
            container.commit()

            raw_results = [dict(row) for row in results]
            consolidation = consolidate_result_rows(
                raw_results,
                seeds=[self._snapshot_seed(item, queued=True) for item in seeds],
                limit=300,
            )
            results = consolidation.rows
            provider_errors = sum(1 for row in providers if row.get("status") in {"failed", "partial", "not_supported", "not_configured"})
            guarded = sum(1 for row in providers if row.get("status") == "guarded")
            evidence_created, entities_created = self._persistence_counts(osint_snapshots, open_web_snapshots)
            duration = perf_counter() - started
            snapshot = {
                "hasRun": True,
                "status": "completed_with_errors" if errors or provider_errors else "completed",
                "results": results,
                "rawResults": raw_results[:500],
                "providers": providers,
                "pivots": [self._snapshot_seed(item, queued=is_exact_recursive_seed(item)) for item in pivots],
                "errors": errors,
                "seeds": [self._snapshot_seed(item, queued=True) for item in seeds],
                "summary": {
                    "seeds": len(seeds),
                    "results": len(results),
                    "rawResults": consolidation.raw_count,
                    "duplicatesCollapsed": consolidation.duplicates_collapsed,
                    "lowValueSuppressed": consolidation.low_value_suppressed,
                    "corroborated": consolidation.corroborated_count,
                    "providers": len(providers),
                    "pivots": len(pivots),
                    "queuedPivots": sum(is_exact_recursive_seed(item) for item in pivots),
                    "errors": len(errors),
                    "guarded": guarded,
                    "evidenceCreated": evidence_created,
                    "entitiesCreated": entities_created,
                    "classicRuns": len(osint_snapshots),
                    "openWebRuns": len(open_web_snapshots),
                    "federationRecords": len(all_federation_records),
                    "registryRecords": len(all_registry_records),
                },
                "options": {
                    "classic": use_classic,
                    "openWeb": use_open_web,
                    "federation": use_federation,
                    "registry": use_registry,
                    "followPivots": follow_pivots,
                    "includeSensitiveNameRoutes": include_sensitive_names,
                },
                "rawSecretValuesStored": False,
            }
            self.succeeded.emit({"snapshot": snapshot, "duration": duration})
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
                    "error": f"{type(exc).__name__}: {exc}",
                    "duration": perf_counter() - started,
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

    def _classic_seeds(self, container: Any, seeds: list[UnifiedSeed]) -> list[UnifiedSeed]:
        policy = container.osint_enrichment_service.execution_service.router.policy
        out: list[UnifiedSeed] = []
        for seed in seeds:
            target = osint_target_for_seed(seed)
            if target is None:
                continue
            if policy.default_goals(target):
                out.append(seed)
        return out

    def _open_web_seeds(self, container: Any, seeds: list[UnifiedSeed]) -> list[UnifiedSeed]:
        out: list[UnifiedSeed] = []
        for seed in dedupe_seeds(seeds):
            target = osint_target_for_seed(seed)
            if target is None:
                continue
            query = OpenWebQuery(
                target_type=target,
                value=seed.value,
                case_id=self.case_id,
                limit=1,
                timeout=5,
                depth=seed.depth,
            )
            try:
                if container.open_web_provider_registry.automatic_for(query):
                    out.append(seed)
            except Exception:
                continue
        return out

    def _run_federation_routes(
        self,
        *,
        container: Any,
        routes: list[tuple[UnifiedSeed, Any]],
        results: list[dict[str, Any]],
        providers: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> list[Any]:
        records: list[Any] = []
        for index, (seed, route) in enumerate(routes, start=1):
            self._emit(
                "federation",
                f"Federation {index}/{len(routes)} · {route.source_code} · {seed.value}",
            )
            query = RemoteSourceQuery(
                capability=route.capability,
                value=seed.value,
                country=seed.country,
                limit=20,
                timeout=18,
                sources=(route.source_code,),
                verified_scope=False,
            )
            federated = container.remote_source_adapter_service.search(query)
            snap = FederatedSourceSearchWorker._snapshot_result(federated)
            raw_records = list(getattr(federated, "records", ()) or ())
            identity_matches: dict[str, Any] = {}
            accepted_records = raw_records
            if seed.kind is UnifiedSeedKind.PERSON_NAME:
                accepted_records = []
                for record in raw_records:
                    match = match_person_name_record(seed.value, record)
                    record_id = str(getattr(record, "record_id", "") or "")
                    identity_matches[record_id] = match
                    if match.accepted:
                        accepted_records.append(record)
            # Only identity-relevant name records are eligible to become pivots.
            # Raw UI output is still built from every upstream row below.
            records.extend(accepted_records)
            for provider in snap.get("providers", []):
                providers.append(
                    self._provider_row(
                        lane="Federation",
                        source=str(provider.get("source") or route.source_code),
                        status=str(provider.get("status") or "unknown"),
                        records=(
                            len(accepted_records)
                            if seed.kind is UnifiedSeedKind.PERSON_NAME
                            else int(provider.get("records") or 0)
                        ),
                        seed=seed,
                        detail=(
                            str(provider.get("error") or "")
                            or (
                                f"{route.capability} · {len(accepted_records)}/{len(raw_records)} full-name relevant"
                                if seed.kind is UnifiedSeedKind.PERSON_NAME
                                else route.capability
                            )
                        ),
                    )
                )
                if provider.get("error") and provider.get("status") == "failed":
                    errors.append(
                        self._error_row(
                            "Federation",
                            str(provider.get("source") or route.source_code),
                            str(provider.get("error")),
                            seed,
                        )
                    )
            for row in snap.get("records", []):
                match = identity_matches.get(str(row.get("recordId") or ""))
                identity_rejected = bool(
                    seed.kind is UnifiedSeedKind.PERSON_NAME
                    and (match is None or not match.accepted)
                )
                results.append(
                    {
                        "lane": "Federation",
                        "source": str(row.get("source") or route.source_code),
                        "title": str(row.get("title") or "Remote record"),
                        "detail": str(row.get("detail") or row.get("identifiersText") or ""),
                        "type": str(row.get("type") or seed.kind.value),
                        "status": "Remote",
                        "url": str(row.get("sourceUrl") or ""),
                        "meta": str(row.get("country") or seed.country or ""),
                        "depth": seed.depth,
                        "seed": seed.value,
                        "seedType": seed.kind.value,
                        "identifiers": dict(row.get("identifiers") or {}),
                        "candidateOnly": seed.kind in {UnifiedSeedKind.PERSON_NAME, UnifiedSeedKind.ORGANIZATION},
                        "sensitive": False,
                        "identityRejected": identity_rejected,
                        "identityMatchScore": (match.score if match is not None else None),
                        "identityMatchReason": (match.reason if match is not None else ""),
                        "identityMatchedName": (match.matched_text if match is not None else ""),
                    }
                )
        return records

    def _run_registry_queries(
        self,
        *,
        container: Any,
        items: list[tuple[UnifiedSeed, Any]],
        results: list[dict[str, Any]],
        providers: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> list[Any]:
        records: list[Any] = []
        seen_queries: set[tuple[str, str, str, str]] = set()
        for index, (seed, query) in enumerate(items, start=1):
            key = (query.domain.value, query.kind.value, query.value.casefold(), query.country or "")
            if key in seen_queries:
                continue
            seen_queries.add(key)
            self._emit(
                "registry",
                f"Registry {index}/{len(items)} · {query.kind.value} · {query.value}",
            )
            search = container.registry_intelligence_service.search(query)
            raw_records = list(getattr(search, "records", ()) or ())
            identity_matches: dict[str, Any] = {}
            accepted_records = raw_records
            if seed.kind is UnifiedSeedKind.PERSON_NAME:
                accepted_records = []
                for record in raw_records:
                    match = match_person_name_record(seed.value, record)
                    record_id = str(getattr(record, "record_id", "") or "")
                    identity_matches[record_id] = match
                    if match.accepted:
                        accepted_records.append(record)
            # As with Federation, irrelevant same-name/same-surname rows remain
            # inspectable in Raw results but cannot generate automatic pivots.
            records.extend(accepted_records)
            route = dict(getattr(search, "metadata", {}) or {}).get("route", {}) or {}
            for blocked in list(route.get("blocked") or []):
                providers.append(
                    self._provider_row(
                        lane="Registry",
                        source=str(blocked.get("provider") or "registry"),
                        status="guarded",
                        records=0,
                        seed=seed,
                        detail=str(blocked.get("reason") or "Blocked by access policy."),
                    )
                )
            accepted_by_provider: dict[str, int] = {}
            if seed.kind is UnifiedSeedKind.PERSON_NAME:
                for record in accepted_records:
                    provider_name = str(getattr(record, "provider", "") or "registry")
                    accepted_by_provider[provider_name] = accepted_by_provider.get(provider_name, 0) + 1

            for provider in list(getattr(search, "provider_results", ()) or ()):
                snap = RegistrySearchWorker._snapshot_provider_result(provider)
                providers.append(
                    self._provider_row(
                        lane="Registry",
                        source=str(snap.get("provider") or "registry"),
                        status=str(snap.get("status") or "unknown"),
                        records=(
                            accepted_by_provider.get(str(snap.get("provider") or "registry"), 0)
                            if seed.kind is UnifiedSeedKind.PERSON_NAME
                            else int(snap.get("records") or 0)
                        ),
                        seed=seed,
                        detail=(
                            str(snap.get("error") or "")
                            or (
                                f"{query.kind.value} · full-name relevance enforced"
                                if seed.kind is UnifiedSeedKind.PERSON_NAME
                                else query.kind.value
                            )
                        ),
                    )
                )
                if snap.get("error") and snap.get("status") == "failed":
                    errors.append(
                        self._error_row(
                            "Registry",
                            str(snap.get("provider") or "registry"),
                            str(snap.get("error")),
                            seed,
                        )
                    )
            for record in raw_records:
                row = RegistrySearchWorker._snapshot_record(record)
                match = identity_matches.get(str(row.get("recordId") or ""))
                identity_rejected = bool(
                    seed.kind is UnifiedSeedKind.PERSON_NAME
                    and (match is None or not match.accepted)
                )
                results.append(
                    {
                        "lane": "Registry",
                        "source": str(row.get("provider") or "registry"),
                        "title": str(row.get("title") or "Registry record"),
                        "detail": str(row.get("detail") or row.get("identifiersText") or ""),
                        "type": str(row.get("entityKind") or row.get("domain") or "registry"),
                        "status": "Candidate" if row.get("candidateOnly") else "Registry",
                        "url": str(row.get("sourceUrl") or ""),
                        "meta": str(row.get("identifiersText") or row.get("country") or ""),
                        "depth": seed.depth,
                        "seed": seed.value,
                        "seedType": seed.kind.value,
                        "identifiers": dict(row.get("identifiers") or {}),
                        "candidateOnly": bool(row.get("candidateOnly")) or seed.kind is UnifiedSeedKind.PERSON_NAME,
                        "sensitive": bool(row.get("sensitiveLegalData")),
                        "identityRejected": identity_rejected,
                        "identityMatchScore": (match.score if match is not None else None),
                        "identityMatchReason": (match.reason if match is not None else ""),
                        "identityMatchedName": (match.matched_text if match is not None else ""),
                    }
                )
        return records

    def _extract_pivots(
        self,
        records: list[Any],
        *,
        depth: int,
        lane: str,
        default_country: str | None,
    ) -> list[UnifiedSeed]:
        out: list[UnifiedSeed] = []
        for index, record in enumerate(records):
            source = str(
                getattr(record, "source", "")
                or getattr(record, "provider", "")
                or lane
            )
            record_id = str(getattr(record, "record_id", "") or index)
            out.extend(
                extract_remote_pivots(
                    record,
                    depth=depth,
                    parent_ref=f"{source}:{record_id}",
                    default_country=default_country,
                )
            )
        return dedupe_seeds(out)

    @classmethod
    def _snapshot_open_web(cls, enrichment: Any, seed: UnifiedSeed) -> dict[str, Any]:
        discovery = getattr(enrichment, "discovery", None)
        documents = []
        for item in list(getattr(discovery, "documents", ()) or ())[:50]:
            documents.append(
                {
                    "provider": str(getattr(item, "provider", "") or "open_web"),
                    "title": str(getattr(item, "title", "") or getattr(item, "url", "") or "Public document"),
                    "url": str(getattr(item, "url", "") or ""),
                    "capturedAt": str(getattr(item, "captured_at", "") or ""),
                    "contentType": str(getattr(item, "content_type", "") or ""),
                }
            )
        findings = []
        extraction = getattr(enrichment, "extraction", None)
        for item in list(getattr(extraction, "findings", ()) or ())[:100]:
            findings.append(
                {
                    "category": str(getattr(item, "category", "") or "finding"),
                    "value": str(getattr(item, "value", "") or ""),
                    "source": str(getattr(item, "source", "") or "open_web"),
                    "url": str(getattr(item, "url", "") or ""),
                    "confidence": cls._safe_float(getattr(item, "confidence", 0.0)),
                }
            )
        provider_rows = []
        for item in list(getattr(discovery, "results", ()) or ()):
            provider_rows.append(
                {
                    "source": str(getattr(item, "provider", "") or "open_web"),
                    "status": str(getattr(getattr(item, "status", None), "value", None) or getattr(item, "status", "") or "unknown"),
                    "error": str(getattr(item, "error", "") or ""),
                    "records": len(list(getattr(item, "documents", ()) or ())),
                }
            )
        return {
            "seed": cls._snapshot_seed(seed, queued=True),
            "documents": documents,
            "findings": findings,
            "providers": provider_rows,
            "counts": {
                "documents": int(getattr(enrichment, "documents_found", 0) or 0),
                "findings": int(getattr(enrichment, "findings_extracted", 0) or 0),
                "evidenceCreated": int(getattr(enrichment, "evidences_created", 0) or 0),
                "entitiesCreated": int(getattr(enrichment, "entities_created", 0) or 0),
            },
        }

    @classmethod
    def _append_open_web_snapshot(cls, snap, results, providers, errors) -> None:
        seed = snap.get("seed") or {}
        for provider in snap.get("providers", []):
            providers.append(
                {
                    "lane": "Open-Web",
                    "source": str(provider.get("source") or "open_web"),
                    "status": str(provider.get("status") or "unknown"),
                    "records": int(provider.get("records") or 0),
                    "seed": str(seed.get("value") or ""),
                    "seedType": str(seed.get("kind") or ""),
                    "depth": int(seed.get("depth") or 0),
                    "detail": str(provider.get("error") or "Public web discovery"),
                }
            )
            if provider.get("error") and provider.get("status") == "failed":
                errors.append(
                    {
                        "lane": "Open-Web",
                        "source": str(provider.get("source") or "open_web"),
                        "error": str(provider.get("error")),
                        "seed": str(seed.get("value") or ""),
                    }
                )
        for row in snap.get("findings", []):
            results.append(
                {
                    "lane": "Open-Web",
                    "source": str(row.get("source") or "open_web"),
                    "title": str(row.get("value") or "Extracted finding"),
                    "detail": str(row.get("category") or "finding").replace("_", " ").title(),
                    "type": str(row.get("category") or "finding"),
                    "status": "Extracted",
                    "url": str(row.get("url") or ""),
                    "meta": "Public web",
                    "depth": int(seed.get("depth") or 0),
                    "seed": str(seed.get("value") or ""),
                    "seedType": str(seed.get("kind") or ""),
                    "candidateOnly": False,
                    "sensitive": False,
                }
            )
        for row in snap.get("documents", []):
            results.append(
                {
                    "lane": "Open-Web",
                    "source": str(row.get("provider") or "open_web"),
                    "title": str(row.get("title") or "Public document"),
                    "detail": str(row.get("url") or ""),
                    "type": "document",
                    "status": "Document",
                    "url": str(row.get("url") or ""),
                    "meta": str(row.get("capturedAt") or row.get("contentType") or ""),
                    "depth": int(seed.get("depth") or 0),
                    "seed": str(seed.get("value") or ""),
                    "seedType": str(seed.get("kind") or ""),
                    "candidateOnly": True,
                    "sensitive": False,
                }
            )

    @classmethod
    def _append_osint_snapshot(cls, snap, results, providers, errors) -> None:
        for run in snap.get("runs", []):
            depth = int(run.get("depth") or 0)
            target = str(run.get("targetValue") or "")
            target_type = str(run.get("targetType") or "")
            for execution in run.get("executions", []):
                for record in execution.get("records", []):
                    connector = str(record.get("connector") or record.get("runtimeConnectorName") or record.get("title") or "OSINT")
                    status = str(record.get("status") or execution.get("status") or "unknown")
                    findings = list(record.get("findings") or [])
                    providers.append(
                        {
                            "lane": "Classic OSINT",
                            "source": connector,
                            "status": status,
                            "records": len(findings),
                            "seed": target,
                            "seedType": target_type,
                            "depth": depth,
                            "detail": str(record.get("error") or execution.get("goal") or "OSINT connector"),
                        }
                    )
                    if record.get("error") and status == "failed":
                        errors.append(
                            {
                                "lane": "Classic OSINT",
                                "source": connector,
                                "error": str(record.get("error")),
                                "seed": target,
                            }
                        )
                    for finding in findings:
                        results.append(
                            {
                                "lane": "Classic OSINT",
                                "source": connector,
                                "title": str(finding.get("value") or "OSINT finding"),
                                "detail": str(finding.get("category") or "finding").replace("_", " ").title(),
                                "type": str(finding.get("category") or "finding"),
                                "status": "Finding",
                                "url": str(finding.get("url") or ""),
                                "meta": f"D{depth} · {target}",
                                "depth": depth,
                                "seed": target,
                                "seedType": target_type,
                                "candidateOnly": False,
                                "sensitive": False,
                            }
                        )

    @classmethod
    def _persistence_counts(cls, osint_snapshots, open_web_snapshots) -> tuple[int, int]:
        evidence = 0
        entities = 0
        for snap in osint_snapshots:
            counts = dict(snap.get("counts") or {})
            evidence += int(counts.get("evidenceCreated") or 0)
            entities += int(counts.get("entitiesCreated") or 0)
        for snap in open_web_snapshots:
            counts = dict(snap.get("counts") or {})
            evidence += int(counts.get("evidenceCreated") or 0)
            entities += int(counts.get("entitiesCreated") or 0)
        return evidence, entities

    @staticmethod
    def _dedupe_result_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Compatibility helper retained for older tests/callers. R13.20.1 uses
        # the richer consolidation layer at the end of each live search.
        return consolidate_result_rows(rows).rows

    @staticmethod
    def _snapshot_seed(seed: UnifiedSeed, *, queued: bool) -> dict[str, Any]:
        return {
            "kind": seed.kind.value,
            "value": seed.value,
            "origin": seed.origin,
            "depth": seed.depth,
            "country": seed.country or "",
            "parentRef": seed.parent_ref or "",
            "candidateOnly": seed.candidate_only,
            "queued": bool(queued),
        }

    @staticmethod
    def _provider_row(*, lane, source, status, records, seed, detail) -> dict[str, Any]:
        return {
            "lane": str(lane),
            "source": str(source),
            "status": str(status),
            "records": int(records or 0),
            "seed": seed.value,
            "seedType": seed.kind.value,
            "depth": seed.depth,
            "detail": str(detail or ""),
        }

    @staticmethod
    def _error_row(lane: str, source: str, error: str, seed: UnifiedSeed) -> dict[str, Any]:
        return {
            "lane": lane,
            "source": source,
            "error": error,
            "seed": seed.value,
        }

    @staticmethod
    def _country_hint(seeds: list[UnifiedSeed]) -> str | None:
        return next((seed.country for seed in seeds if seed.country), None)

    def _classic_progress(self, progress: Any) -> None:
        target_type = getattr(progress, "target_type", None)
        self.progress.emit(
            {
                "phase": "classic",
                "detail": (
                    f"{getattr(progress, 'phase', '')} · "
                    f"{getattr(target_type, 'value', target_type) or ''} · "
                    f"{getattr(progress, 'value', '') or ''}"
                ).strip(" ·"),
                "targetsProcessed": int(getattr(progress, "targets_processed", 0) or 0),
                "queuedTargets": int(getattr(progress, "queued_targets", 0) or 0),
                "elapsedSeconds": self._safe_float(getattr(progress, "elapsed_seconds", 0.0)),
            }
        )

    def _emit(self, phase: str, detail: str, **extra: Any) -> None:
        self.progress.emit({"phase": phase, "detail": detail, **extra})

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

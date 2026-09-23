from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.application.osint_recursive_enrichment_service import RecursiveEnrichmentSeed
from app.application.investigation_result_consolidation import consolidate_result_rows
from app.application.connector_health import annotate_provider_health
from app.application.identity_resolution import (
    build_known_identity_profile,
    extract_identity_signals,
    resolve_identity_record,
    is_identity_candidate_record,
    is_account_candidate_record,
)
from app.application.person_name_relevance import match_person_name_record
from app.application.person_search_attribution_service import (
    PersonSearchAttributionService,
)
from app.application.contextual_relevance import assess_record_against_seed
from app.application.unified_persistence_relevance import build_unified_finding_gate
from app.application.search_quality_engine import (
    annotate_search_quality_rows,
    quality_trace_rows,
)
from app.application.account_profile_validation import (
    annotate_account_profile_validation,
)
from app.application.browser_account_verification import (
    annotate_browser_account_validation,
)
from app.application.exploration_graph import (
    ExplorationGraph,
    build_exploration_graph,
)
from app.application.search_retrieval_scheduler import (
    AdaptiveRetrievalFeedback,
    RetrievalScheduleBook,
    schedule_seed_routes,
    schedule_seeds,
)
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
    CLASSIC_TIME_BUDGET = 250.0
    CLASSIC_TIMEOUT = 15
    USERNAME_CLASSIC_TIMEOUT = 20
    OPEN_WEB_ROOT_LIMIT = 8
    OPEN_WEB_TIMEOUT = 18
    FEDERATION_ROUTE_LIMIT = 56
    REGISTRY_QUERY_LIMIT = 18
    FEDERATION_TIME_BUDGET = 224.0
    REGISTRY_TIME_BUDGET = 90.0
    PIVOT_FEDERATION_TIME_BUDGET = 96.0
    PIVOT_REGISTRY_TIME_BUDGET = 50.0
    DISCOVERED_PIVOT_LIMIT = 18
    SECOND_WAVE_OPEN_WEB_LIMIT = 4
    EXPLORATION_MAX_SEEDS = 8
    EXPLORATION_MAX_DEPTH = 2
    EXPLORATION_TIMEOUT = 12
    EXPLORATION_FINDING_LIMIT = 6

    def __init__(
        self,
        *,
        case_id: str,
        profile: dict[str, Any],
        options: dict[str, Any] | None = None,
        person_entity_id: str = "",
    ) -> None:
        super().__init__()
        self.case_id = str(case_id or "").strip()
        self.person_entity_id = str(person_entity_id or "").strip()
        self.profile = dict(profile or {})
        self.options = dict(options or {})
        self._identity_profile = build_known_identity_profile(self.profile)

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
            if not self.person_entity_id:
                raise ValueError(
                    "Select the PERSON this search belongs to before running unified search."
                )
            person_uuid = UUID(self.person_entity_id)
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

            person = container.entity_service.get_entity(
                person_uuid
            )
            if person is None:
                raise ValueError(
                    "The selected PERSON no longer exists."
                )
            person_type = str(
                getattr(
                    getattr(person, "entity_type", None),
                    "value",
                    getattr(person, "entity_type", ""),
                )
                or ""
            ).strip().lower()
            if person_type != "person":
                raise ValueError(
                    "The selected search target must be a PERSON entity."
                )
            if getattr(person, "case_id", None) != case_uuid:
                raise ValueError(
                    "The selected PERSON belongs to a different investigation."
                )

            persistence_service = getattr(container, "osint_finding_persistence_service", None)
            if persistence_service is not None:
                persistence_service.finding_gate = build_unified_finding_gate(self.profile)
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
            attributed_entity_ids: set[UUID] = set()
            attribution_result = None
            state = PivotTraversalState()
            retrieval_schedule = RetrievalScheduleBook()
            retrieval_feedback = AdaptiveRetrievalFeedback()

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
                classic_candidates = self._classic_seeds(
                    container, plan.classic_seeds
                )
                classic_roots, classic_schedule = schedule_seeds(
                    classic_candidates,
                    limit=self.ROOT_CLASSIC_LIMIT,
                    lane="classic_roots",
                )
                retrieval_schedule.add(classic_schedule)
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
                                parent_entity_id=person_uuid,
                            )
                            for seed in classic_roots
                            if osint_target_for_seed(seed) is not None
                        ),
                        state=state,
                        seed_depth=0,
                        timeout=(
                            self.USERNAME_CLASSIC_TIMEOUT
                            if classic_roots and all(seed.kind is UnifiedSeedKind.USERNAME for seed in classic_roots)
                            else self.CLASSIC_TIMEOUT
                        ),
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
                    attributed_entity_ids.update(
                        self._persistence_entity_ids(
                            recursion
                        )
                    )
                    snap = OsintCollectionWorker._snapshot_recursive_enrichment(recursion)
                    osint_snapshots.append(snap)
                    self._append_osint_snapshot(snap, results, providers, errors)

            if use_open_web:
                open_web_candidates = self._open_web_seeds(
                    container, plan.open_web_seeds
                )
                open_web_roots, open_web_schedule = schedule_seeds(
                    open_web_candidates,
                    limit=self.OPEN_WEB_ROOT_LIMIT,
                    lane="open_web_roots",
                )
                retrieval_schedule.add(open_web_schedule)
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
                        parent_entity_id=person_uuid,
                    )
                    attributed_entity_ids.update(
                        self._persistence_entity_ids(
                            enrichment
                        )
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
                            attributed_entity_ids.update(
                                self._persistence_entity_ids(
                                    expanded.recursion
                                )
                            )
                            recursion_snap = OsintCollectionWorker._snapshot_recursive_enrichment(
                                expanded.recursion
                            )
                            osint_snapshots.append(recursion_snap)
                            self._append_osint_snapshot(
                                recursion_snap, results, providers, errors
                            )

            if use_federation:
                self._emit("federation", "Searching safe automatic Federation sources…")
                routes, federation_schedule = schedule_seed_routes(
                    plan.federation_routes,
                    limit=self.FEDERATION_ROUTE_LIMIT,
                    lane="federation_roots",
                    feedback=retrieval_feedback,
                    time_budget_seconds=self.FEDERATION_TIME_BUDGET,
                )
                retrieval_schedule.add(federation_schedule)
                federation_records = self._run_federation_routes(
                    container=container,
                    routes=routes,
                    results=results,
                    providers=providers,
                    errors=errors,
                    feedback=retrieval_feedback,
                )
                all_federation_records.extend(federation_records)

            if use_registry:
                self._emit("registry", "Searching compatible Registry providers…")
                registry_items, registry_schedule = schedule_seed_routes(
                    plan.registry_queries,
                    limit=self.REGISTRY_QUERY_LIMIT,
                    lane="registry_roots",
                    feedback=retrieval_feedback,
                    time_budget_seconds=self.REGISTRY_TIME_BUDGET,
                )
                retrieval_schedule.add(registry_schedule)
                registry_records = self._run_registry_queries(
                    container=container,
                    items=registry_items,
                    results=results,
                    providers=providers,
                    errors=errors,
                    feedback=retrieval_feedback,
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
                pivot_candidates = [
                    seed
                    for seed in dedupe_seeds(pivots)
                    if seed.identity_key not in initial_keys
                ]
                pivots, pivot_review_schedule = schedule_seeds(
                    pivot_candidates,
                    limit=self.DISCOVERED_PIVOT_LIMIT * 2,
                    lane="pivot_review",
                )
                retrieval_schedule.add(pivot_review_schedule)
                queued_candidates = [
                    seed for seed in pivots if is_exact_recursive_seed(seed)
                ]
                queued_pivots, pivot_queue_schedule = schedule_seeds(
                    queued_candidates,
                    limit=self.DISCOVERED_PIVOT_LIMIT,
                    lane="pivot_execution",
                )
                retrieval_schedule.add(pivot_queue_schedule)

                if queued_pivots:
                    self._emit(
                        "pivots",
                        f"Following {len(queued_pivots)} identity-supported pivot(s) / exact discovered pivot(s); "
                        f"{len(pivots) - len(queued_pivots)} candidate value(s) remain for review.",
                        pivots=len(pivots),
                    )

                    if use_classic:
                        classic_pivot_candidates = self._classic_seeds(
                            container, queued_pivots
                        )
                        classic_pivots, classic_pivot_schedule = schedule_seeds(
                            classic_pivot_candidates,
                            limit=12,
                            lane="classic_pivots",
                        )
                        retrieval_schedule.add(classic_pivot_schedule)
                        if classic_pivots:
                            recursion = container.osint_recursive_enrichment_service.enrich(
                                case_id=case_uuid,
                                seeds=tuple(
                                    RecursiveEnrichmentSeed(
                                        target_type=osint_target_for_seed(seed),
                                        value=seed.value,
                                        parent_entity_id=person_uuid,
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
                            attributed_entity_ids.update(
                                self._persistence_entity_ids(
                                    recursion
                                )
                            )
                            snap = OsintCollectionWorker._snapshot_recursive_enrichment(recursion)
                            osint_snapshots.append(snap)
                            self._append_osint_snapshot(snap, results, providers, errors)

                    pivot_plan = build_search_plan(
                        adapter_registry=container.remote_source_adapter_registry,
                        seeds=queued_pivots,
                        include_sensitive_name_routes=False,
                    )
                    if use_federation:
                        pivot_federation_routes, pivot_federation_schedule = (
                            schedule_seed_routes(
                                pivot_plan.federation_routes,
                                limit=24,
                                lane="federation_pivots",
                                feedback=retrieval_feedback,
                                time_budget_seconds=(
                                    self.PIVOT_FEDERATION_TIME_BUDGET
                                ),
                            )
                        )
                        retrieval_schedule.add(pivot_federation_schedule)
                        more_records = self._run_federation_routes(
                            container=container,
                            routes=pivot_federation_routes,
                            results=results,
                            providers=providers,
                            errors=errors,
                            feedback=retrieval_feedback,
                        )
                        all_federation_records.extend(more_records)
                    if use_registry:
                        pivot_registry_items, pivot_registry_schedule = (
                            schedule_seed_routes(
                                pivot_plan.registry_queries,
                                limit=10,
                                lane="registry_pivots",
                                feedback=retrieval_feedback,
                                time_budget_seconds=(
                                    self.PIVOT_REGISTRY_TIME_BUDGET
                                ),
                            )
                        )
                        retrieval_schedule.add(pivot_registry_schedule)
                        more_registry = self._run_registry_queries(
                            container=container,
                            items=pivot_registry_items,
                            results=results,
                            providers=providers,
                            errors=errors,
                            feedback=retrieval_feedback,
                        )
                        all_registry_records.extend(more_registry)
                    if use_open_web:
                        second_web_candidates = self._open_web_seeds(
                            container, queued_pivots
                        )
                        second_web, second_web_schedule = schedule_seeds(
                            second_web_candidates,
                            limit=self.SECOND_WAVE_OPEN_WEB_LIMIT,
                            lane="open_web_pivots",
                        )
                        retrieval_schedule.add(second_web_schedule)
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
                                parent_entity_id=person_uuid,
                            )
                            attributed_entity_ids.update(
                                self._persistence_entity_ids(
                                    enrichment
                                )
                            )
                            snap = self._snapshot_open_web(enrichment, seed)
                            open_web_snapshots.append(snap)
                            self._append_open_web_snapshot(
                                snap, results, providers, errors
                            )

            # Existing OSINT/Open-Web enrichment persists safe findings into the
            # current case. Federation/Registry remain review-first/read-only here.
            attributed_entities = []
            for entity_id in sorted(
                attributed_entity_ids,
                key=str,
            ):
                try:
                    entity = container.entity_service.get_entity(
                        entity_id
                    )
                except Exception:
                    entity = None
                if entity is not None:
                    attributed_entities.append(entity)

            attribution_result = (
                PersonSearchAttributionService(
                    source_service=container.source_service,
                    evidence_service=container.evidence_service,
                    evidence_link_service=container.evidence_link_service,
                )
                .attribute(
                    person=person,
                    entities=attributed_entities,
                    search_summary={
                        "seed_count": len(seeds),
                        "classic_runs": len(osint_snapshots),
                        "open_web_runs": len(open_web_snapshots),
                    },
                )
            )

            container.commit()

            # Attach safe, bounded identity signals to rows from Classic/Open-Web
            # too. Federation/Registry rows already carry richer extracted hints.
            for row in results:
                if not row.get("_identitySignals"):
                    row["_identitySignals"] = extract_identity_signals(row).to_payload()

            # R13.26a.1 — bounded independent validation of username
            # account URLs.  Invalid profiles remain in Raw/Quality but no
            # longer qualify for the normal Accounts/Clean presentation.
            self._emit(
                "account_validation",
                "Validating provider-reported account URLs…",
            )
            results, account_validation_summary = annotate_account_profile_validation(
                results,
                max_live_checks=48,
                timeout=4.0,
                workers=8,
            )

            self._emit(
                "browser_account_validation",
                "Rendering ambiguous account pages in Chromium…",
            )
            results, browser_validation_summary = annotate_browser_account_validation(
                results,
                max_browser_checks=14,
                navigation_timeout=10.0,
                max_concurrency=3,
            )

            # R13.26a shadow quality assessment becomes the admission signal
            # for the R13.26c in-memory Exploration Graph.  Persistence remains
            # unchanged: exploratory execution uses the raw execution boundary
            # and therefore creates no Entity/Evidence on its own.
            preliminary_quality_rows, _preliminary_quality_summary = (
                annotate_search_quality_rows(
                    results,
                    search_profile=self.profile,
                )
            )
            results = preliminary_quality_rows

            exploration_graph = ExplorationGraph()
            exploration_executed_keys: set[tuple[str, str, str]] = set()
            exploration_rows: list[dict[str, Any]] = []
            exploration_validation_summary: dict[str, Any] = {}
            exploration_browser_summary: dict[str, Any] = {}

            if follow_pivots:
                exploration_graph = build_exploration_graph(
                    results,
                    initial_seeds=seeds,
                    existing_seeds=pivots,
                    max_nodes=self.EXPLORATION_MAX_SEEDS,
                    max_depth=self.EXPLORATION_MAX_DEPTH,
                )
                if exploration_graph.nodes:
                    self._emit(
                        "exploration",
                        f"Exploring {len(exploration_graph.nodes)} quality-approved ephemeral pivot(s) without persistence…",
                        pivots=len(exploration_graph.nodes),
                    )
                    exploration_executed_keys = self._run_ephemeral_exploration(
                        container=container,
                        graph=exploration_graph,
                        results=exploration_rows,
                        providers=providers,
                        errors=errors,
                    )

                    if exploration_rows:
                        exploration_rows, exploration_account_summary = (
                            annotate_account_profile_validation(
                                exploration_rows,
                                max_live_checks=12,
                                timeout=4.0,
                                workers=4,
                            )
                        )
                        exploration_validation_summary = (
                            exploration_account_summary.to_dict()
                        )
                        exploration_rows, exploration_browser = (
                            annotate_browser_account_validation(
                                exploration_rows,
                                max_browser_checks=6,
                                navigation_timeout=8.0,
                                max_concurrency=2,
                            )
                        )
                        exploration_browser_summary = (
                            exploration_browser.to_dict()
                        )
                        results.extend(exploration_rows)

            # Re-score after the ephemeral wave so exploration observations are
            # ranked by the same quality engine as first-wave results.
            quality_rows, quality_summary = annotate_search_quality_rows(
                results,
                search_profile=self.profile,
            )
            results = quality_rows
            raw_results = [self._public_result_row(row) for row in results]
            quality_trace = quality_trace_rows(results, limit=500)

            consolidation = consolidate_result_rows(
                results,
                seeds=[self._snapshot_seed(item, queued=True) for item in seeds],
                identity_profile=self._identity_profile,
                search_profile=self.profile,
                limit=220,
            )
            results = [self._public_result_row(row) for row in consolidation.rows]
            identity_rows = [
                self._public_result_row(row)
                for row in (consolidation.identity_rows or [])
            ]
            errors = self._group_error_rows(errors)
            providers, health_summary = annotate_provider_health(providers)
            provider_errors = int(health_summary.get("issues") or 0)
            guarded = sum(1 for row in providers if row.get("status") == "guarded")
            evidence_created, entities_created = self._persistence_counts(osint_snapshots, open_web_snapshots)
            duration = perf_counter() - started
            snapshot = {
                "hasRun": True,
                "status": "completed_with_errors" if errors or provider_errors else "completed",
                "results": results,
                "rawResults": raw_results[:500],
                "identityCandidates": identity_rows,
                "candidates": [
                    self._public_result_row(row)
                    for row in (consolidation.candidate_rows or [])
                ],
                "relatedAccounts": [
                    self._public_result_row(row)
                    for row in (consolidation.related_accounts or [])
                ],
                "mentions": [
                    self._public_result_row(row)
                    for row in (consolidation.mention_rows or [])
                ],
                "possibleResults": [
                    self._public_result_row(row)
                    for row in (consolidation.possible_rows or [])
                ],
                "qualityTrace": quality_trace,
                "qualitySummary": quality_summary.to_dict(),
                "accountValidationSummary": account_validation_summary.to_dict(),
                "browserAccountValidationSummary": browser_validation_summary.to_dict(),
                "explorationGraph": exploration_graph.to_dict(
                    executed_keys=exploration_executed_keys
                ),
                "explorationValidationSummary": exploration_validation_summary,
                "explorationBrowserSummary": exploration_browser_summary,
                "retrievalSchedule": retrieval_schedule.to_dict(),
                "retrievalFeedback": retrieval_feedback.to_dict(),
                "providers": providers,
                "healthSummary": health_summary,
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
                    "identityStrong": consolidation.identity_strong,
                    "identitySupported": consolidation.identity_supported,
                    "identityPossible": consolidation.identity_possible,
                    "identityConflicting": consolidation.identity_conflicting,
                    "identityInsufficient": consolidation.identity_insufficient,
                    "identityCandidates": len(identity_rows),
                    "candidates": len(consolidation.candidate_rows or []),
                    "relatedAccounts": len(consolidation.related_accounts or []),
                    "mentions": len(consolidation.mention_rows or []),
                    "possible": len(consolidation.possible_rows or []),
                    "qualityStrong": quality_summary.strong,
                    "qualityRelevant": quality_summary.relevant,
                    "qualityPossible": quality_summary.possible,
                    "qualityNoise": quality_summary.noise,
                    "qualityDisagreements": quality_summary.disagreements,
                    "qualityWouldExplore": quality_summary.would_explore,
                    "qualityWouldPersist": quality_summary.would_persist,
                    "accountVerified": account_validation_summary.verified,
                    "accountReported": account_validation_summary.reported,
                    "accountUnreachable": account_validation_summary.unreachable,
                    "accountInvalid": account_validation_summary.invalid,
                    "accountLiveChecks": account_validation_summary.live_checks,
                    "browserVerificationAvailable": browser_validation_summary.available,
                    "browserChecked": browser_validation_summary.checked,
                    "browserVerified": browser_validation_summary.verified,
                    "browserLikely": browser_validation_summary.likely,
                    "browserUncertain": browser_validation_summary.uncertain,
                    "browserBlocked": browser_validation_summary.blocked,
                    "browserInvalid": browser_validation_summary.invalid,
                    "explorationNodes": len(exploration_graph.nodes),
                    "explorationExecuted": len(exploration_executed_keys),
                    "explorationResults": len(exploration_rows),
                    "retrievalCandidates": retrieval_schedule.candidates,
                    "retrievalSelected": retrieval_schedule.selected,
                    "missedDueToBudget": retrieval_schedule.missed_due_to_budget,
                    "skippedDueToTimeBudget": (
                        retrieval_schedule.skipped_due_to_time_budget
                    ),
                    "retrievalDeprioritized": retrieval_schedule.deprioritized,
                    "retrievalEstimatedSeconds": round(
                        retrieval_schedule.estimated_selected_seconds, 2
                    ),
                    "adaptiveSourcesObserved": len(
                        retrieval_feedback.sources
                    ),
                    "providers": len(providers),
                    "healthReady": int(health_summary.get("ready") or 0),
                    "healthIssues": int(health_summary.get("issues") or 0),
                    "healthTimeouts": int(health_summary.get("timeout") or 0),
                    "healthNotInstalled": int(health_summary.get("notInstalled") or 0),
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
                "personTarget": {
                    "id": str(person_uuid),
                    "label": str(
                        getattr(person, "value", "")
                        or "Person"
                    ),
                    "attributedEntityCount": (
                        len(attribution_result.attributed_entity_ids)
                        if attribution_result is not None
                        else 0
                    ),
                    "attributionEvidenceId": (
                        attribution_result.evidence_id
                        if attribution_result is not None
                        else ""
                    ),
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
        feedback: AdaptiveRetrievalFeedback | None = None,
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
            route_started = perf_counter()
            federated = container.remote_source_adapter_service.search(query)
            route_duration = perf_counter() - route_started
            snap = FederatedSourceSearchWorker._snapshot_result(federated)
            raw_records = list(getattr(federated, "records", ()) or ())

            states: list[tuple[Any, Any, Any, Any]] = []
            accepted_records: list[Any] = []
            relevant_count = 0
            for record in raw_records:
                identity_eligible = is_identity_candidate_record(record)
                name_match = (
                    match_person_name_record(seed.value, record)
                    if seed.kind is UnifiedSeedKind.PERSON_NAME
                    else None
                )
                resolution, signals = resolve_identity_record(
                    self._identity_profile,
                    record,
                    person_query=(
                        seed.value if seed.kind is UnifiedSeedKind.PERSON_NAME else None
                    ),
                )
                relevance = assess_record_against_seed(seed, record)
                states.append((name_match, resolution, signals, relevance))

                if relevance.keep_clean:
                    relevant_count += 1

                if seed.kind is UnifiedSeedKind.PERSON_NAME:
                    if (
                        name_match is not None
                        and identity_eligible
                        and name_match.accepted
                        and resolution.pivot_allowed
                        and relevance.keep_clean
                    ):
                        accepted_records.append(record)
                elif relevance.pivot_allowed:
                    # Exact identifiers and strongly matching organization rows
                    # may expose safe typed pivots. Weak candidates never do.
                    accepted_records.append(record)

            records.extend(accepted_records)
            for provider in snap.get("providers", []):
                provider_row = self._provider_row(
                    lane="Federation",
                    source=str(provider.get("source") or route.source_code),
                    status=str(provider.get("status") or "unknown"),
                    records=relevant_count,
                    seed=seed,
                    detail=(
                        str(provider.get("error") or "")
                        or (
                            f"{route.capability} · {relevant_count}/{len(raw_records)} relevant · "
                            f"{len(accepted_records)} pivot-safe record(s)"
                        )
                    ),
                )
                provider_row["durationSeconds"] = round(route_duration, 3)
                providers.append(provider_row)
                if feedback is not None:
                    feedback.observe_provider_row(provider_row)
                if provider.get("error") and provider.get("status") == "failed":
                    errors.append(
                        self._error_row(
                            "Federation",
                            str(provider.get("source") or route.source_code),
                            str(provider.get("error")),
                            seed,
                        )
                    )

            # Raw UI output is still built from every upstream row; only the
            # automatic pivot set is reduced by identity policy.
            for row_index, row in enumerate(snap.get("records", [])):
                name_match, resolution, signals, relevance = (
                    states[row_index]
                    if row_index < len(states)
                    else (None, None, extract_identity_signals(row), assess_record_against_seed(seed, row))
                )
                identity_rejected = bool(
                    seed.kind is UnifiedSeedKind.PERSON_NAME
                    and (name_match is None or not name_match.accepted)
                )
                output = {
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
                    "identityCandidateEligible": bool(
                        is_identity_candidate_record(raw_records[row_index])
                        if row_index < len(raw_records) else False
                    ),
                    "accountCandidateEligible": bool(
                        is_account_candidate_record(raw_records[row_index])
                        if row_index < len(raw_records) else False
                    ),
                    "identityRejected": identity_rejected,
                    "identityMatchScore": (name_match.score if name_match is not None else None),
                    "identityMatchReason": (name_match.reason if name_match is not None else ""),
                    "identityMatchedName": (name_match.matched_text if name_match is not None else ""),
                    "_identitySignals": signals.to_payload(),
                    **relevance.row_fields(),
                }
                if resolution is not None:
                    output.update(resolution.row_fields())
                results.append(output)
        return records

    def _run_registry_queries(
        self,
        *,
        container: Any,
        items: list[tuple[UnifiedSeed, Any]],
        results: list[dict[str, Any]],
        providers: list[dict[str, Any]],
        errors: list[dict[str, Any]],
        feedback: AdaptiveRetrievalFeedback | None = None,
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
            query_started = perf_counter()
            search = container.registry_intelligence_service.search(query)
            query_duration = perf_counter() - query_started
            raw_records = list(getattr(search, "records", ()) or ())

            states: list[tuple[Any, Any, Any, Any]] = []
            accepted_records: list[Any] = []
            relevant_count = 0
            for record in raw_records:
                identity_eligible = is_identity_candidate_record(record)
                name_match = (
                    match_person_name_record(seed.value, record)
                    if seed.kind is UnifiedSeedKind.PERSON_NAME
                    else None
                )
                resolution, signals = resolve_identity_record(
                    self._identity_profile,
                    record,
                    person_query=(
                        seed.value if seed.kind is UnifiedSeedKind.PERSON_NAME else None
                    ),
                )
                relevance = assess_record_against_seed(seed, record)
                states.append((name_match, resolution, signals, relevance))
                if relevance.keep_clean:
                    relevant_count += 1
                if seed.kind is UnifiedSeedKind.PERSON_NAME:
                    if (
                        identity_eligible
                        and name_match is not None
                        and name_match.accepted
                        and resolution.pivot_allowed
                        and relevance.keep_clean
                    ):
                        accepted_records.append(record)
                elif relevance.pivot_allowed:
                    accepted_records.append(record)

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

            pivot_by_provider: dict[str, int] = {}
            relevant_by_provider: dict[str, int] = {}
            for row_index, record in enumerate(raw_records):
                provider_name = str(getattr(record, "provider", "") or "registry")
                state = states[row_index] if row_index < len(states) else (None, None, None, None)
                name_match, resolution, _signals, relevance = state
                if relevance is not None and relevance.keep_clean:
                    relevant_by_provider[provider_name] = relevant_by_provider.get(provider_name, 0) + 1
                if (
                    relevance is not None
                    and relevance.pivot_allowed
                    and (seed.kind is not UnifiedSeedKind.PERSON_NAME or (resolution is not None and resolution.pivot_allowed))
                ):
                    pivot_by_provider[provider_name] = pivot_by_provider.get(provider_name, 0) + 1

            registry_feedback_rows: list[dict[str, Any]] = []
            for provider in list(getattr(search, "provider_results", ()) or ()):
                snap = RegistrySearchWorker._snapshot_provider_result(provider)
                provider_name = str(snap.get("provider") or "registry")
                provider_row = self._provider_row(
                    lane="Registry",
                    source=provider_name,
                    status=str(snap.get("status") or "unknown"),
                    records=relevant_by_provider.get(provider_name, 0),
                    seed=seed,
                    detail=(
                        str(snap.get("error") or "")
                        or (
                            f"{query.kind.value} · {relevant_by_provider.get(provider_name, 0)} relevant · "
                            f"{pivot_by_provider.get(provider_name, 0)} pivot-safe record(s)"
                        )
                    ),
                )
                provider_row["durationSeconds"] = round(query_duration, 3)
                providers.append(provider_row)
                registry_feedback_rows.append(provider_row)
                if feedback is not None:
                    feedback.observe_provider_row(provider_row)
                if snap.get("error") and snap.get("status") == "failed":
                    errors.append(
                        self._error_row(
                            "Registry", provider_name, str(snap.get("error")), seed
                        )
                    )

            if feedback is not None and registry_feedback_rows:
                statuses = {
                    str(row.get("status") or "").strip().casefold()
                    for row in registry_feedback_rows
                }
                aggregate_status = (
                    "success"
                    if "success" in statuses
                    else ("partial" if "partial" in statuses else "failed")
                )
                aggregate_detail = " | ".join(
                    str(row.get("detail") or "")
                    for row in registry_feedback_rows
                    if str(row.get("detail") or "").strip()
                )[:1200]
                feedback.observe_provider_row(
                    {
                        "source": query.domain.value,
                        "status": aggregate_status,
                        "detail": aggregate_detail,
                        "records": relevant_count,
                        "durationSeconds": round(query_duration, 3),
                    }
                )

            for row_index, record in enumerate(raw_records):
                row = RegistrySearchWorker._snapshot_record(record)
                name_match, resolution, signals, relevance = (
                    states[row_index]
                    if row_index < len(states)
                    else (None, None, extract_identity_signals(row), assess_record_against_seed(seed, row))
                )
                identity_rejected = bool(
                    seed.kind is UnifiedSeedKind.PERSON_NAME
                    and (name_match is None or not name_match.accepted)
                )
                output = {
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
                    "identityCandidateEligible": bool(
                        is_identity_candidate_record(raw_records[row_index])
                        if row_index < len(raw_records) else False
                    ),
                    "accountCandidateEligible": bool(
                        is_account_candidate_record(raw_records[row_index])
                        if row_index < len(raw_records) else False
                    ),
                    "identityRejected": identity_rejected,
                    "identityMatchScore": (name_match.score if name_match is not None else None),
                    "identityMatchReason": (name_match.reason if name_match is not None else ""),
                    "identityMatchedName": (name_match.matched_text if name_match is not None else ""),
                    "_identitySignals": signals.to_payload(),
                    **relevance.row_fields(),
                }
                if resolution is not None:
                    output.update(resolution.row_fields())
                results.append(output)
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
                        finding_value = str(finding.get("value") or "")
                        finding_type = str(finding.get("category") or "finding")
                        finding_metadata = dict(finding.get("metadata") or {})
                        identifiers = {}
                        if (
                            str(target_type).strip().casefold() == "username"
                            and finding_type.strip().casefold() in {"account", "username"}
                            and finding_value.strip().lstrip("@").casefold() == target.strip().lstrip("@").casefold()
                        ):
                            # A connector explicitly reporting an account for the
                            # exact searched handle is substantive even when the
                            # platform does not expose a canonical profile URL.
                            identifiers["username"] = target
                        service = str(
                            finding.get("source")
                            or finding_metadata.get("service")
                            or finding_metadata.get("platform")
                            or finding_metadata.get("site_name")
                            or finding_metadata.get("name")
                            or ""
                        )
                        results.append(
                            {
                                "lane": "Classic OSINT",
                                "source": connector,
                                "title": finding_value or "OSINT finding",
                                "detail": finding_type.replace("_", " ").title(),
                                "type": finding_type,
                                "status": "Finding",
                                "url": str(finding.get("url") or ""),
                                "meta": f"D{depth} · {target}" + (f" · {service}" if service else ""),
                                "depth": depth,
                                "seed": target,
                                "seedType": target_type,
                                "identifiers": identifiers,
                                "findingMetadata": finding_metadata,
                                "service": service,
                                "confidence": finding.get("confidence"),
                                "reliability": finding.get("reliability"),
                                "candidateOnly": False,
                                "sensitive": False,
                            }
                        )

    def _run_ephemeral_exploration(
        self,
        *,
        container: Any,
        graph: ExplorationGraph,
        results: list[dict[str, Any]],
        providers: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> set[tuple[str, str, str]]:
        """Execute quality-approved seeds without persistence or recursion."""
        execution_service = container.osint_enrichment_service.execution_service
        state = PivotTraversalState()
        executed: set[tuple[str, str, str]] = set()

        for node in graph.nodes[: self.EXPLORATION_MAX_SEEDS]:
            seed = node.seed
            target_type = osint_target_for_seed(seed)
            if target_type is None:
                continue

            try:
                executions = execution_service.execute_defaults(
                    target_type=target_type,
                    value=seed.value,
                    depth=seed.depth,
                    entity_identity=(
                        f"ephemeral:{seed.kind.value}:"
                        f"{seed.value.strip().casefold()}"
                    ),
                    state=state,
                    case_id=None,
                    timeout=self.EXPLORATION_TIMEOUT,
                    use_cache=True,
                    save_raw_output=False,
                    include_metadata=True,
                    include_related=True,
                    entity_budget_limit=self.EXPLORATION_FINDING_LIMIT,
                )
                executed.add(seed.identity_key)
            except Exception as exc:
                errors.append(
                    self._error_row(
                        "Exploration",
                        "execution_boundary",
                        f"{type(exc).__name__}: {exc}",
                        seed,
                    )
                )
                continue

            for execution in executions:
                route = getattr(execution, "route", None)
                goal_object = getattr(route, "goal", None)
                goal = (
                    getattr(goal_object, "value", None)
                    or str(goal_object or "exploration")
                )
                execution_status_object = getattr(execution, "status", None)
                execution_status = (
                    getattr(execution_status_object, "value", None)
                    or str(execution_status_object or "unknown")
                )

                for record in list(getattr(execution, "records", ()) or ()):
                    result = getattr(record, "result", None)
                    if result is None:
                        continue
                    connector = str(
                        getattr(result, "connector", None)
                        or getattr(record, "runtime_connector_name", None)
                        or "OSINT"
                    )
                    status_object = getattr(result, "status", None)
                    status = (
                        getattr(status_object, "value", None)
                        or str(status_object or execution_status)
                    )
                    findings = list(getattr(result, "findings", ()) or ())
                    providers.append(
                        self._provider_row(
                            lane="Exploration",
                            source=connector,
                            status=status,
                            records=len(findings),
                            seed=seed,
                            detail=(
                                str(getattr(result, "error", "") or "")
                                or f"Ephemeral · {goal} · no persistence"
                            ),
                        )
                    )
                    if getattr(result, "error", None) and status == "failed":
                        errors.append(
                            self._error_row(
                                "Exploration",
                                connector,
                                str(getattr(result, "error", "")),
                                seed,
                            )
                        )

                    for finding in findings:
                        finding_type = str(
                            getattr(finding, "category", "") or "finding"
                        )
                        finding_value = str(
                            getattr(finding, "value", "") or ""
                        )
                        metadata = dict(
                            getattr(finding, "metadata", {}) or {}
                        )
                        metadata.update(
                            {
                                "exploration_ephemeral": True,
                                "exploration_persisted": False,
                                "exploration_parent_observation": (
                                    node.observation_id
                                ),
                            }
                        )
                        service = str(
                            getattr(finding, "source", "")
                            or metadata.get("service")
                            or metadata.get("platform")
                            or metadata.get("site_name")
                            or ""
                        )
                        identifiers = self._exploration_identifiers(
                            finding_type=finding_type,
                            finding_value=finding_value,
                            seed=seed,
                        )
                        results.append(
                            {
                                "lane": "Exploration",
                                "source": connector,
                                "title": finding_value or "Exploration finding",
                                "detail": (
                                    finding_type.replace("_", " ").title()
                                    + " · ephemeral, not persisted"
                                ),
                                "type": finding_type,
                                "status": "Exploration",
                                "url": str(
                                    getattr(finding, "url", "") or ""
                                ),
                                "meta": (
                                    f"Ephemeral · D{seed.depth} · "
                                    f"{seed.kind.value}: {seed.value}"
                                ),
                                "depth": seed.depth,
                                "seed": seed.value,
                                "seedType": seed.kind.value,
                                "identifiers": identifiers,
                                "findingMetadata": metadata,
                                "service": service,
                                "confidence": getattr(
                                    finding, "confidence", None
                                ),
                                "reliability": getattr(
                                    finding, "reliability", None
                                ),
                                "candidateOnly": False,
                                "sensitive": False,
                                "explorationOnly": True,
                                "explorationPersisted": False,
                                "explorationReason": node.reason,
                                "explorationParentObservationId": (
                                    node.observation_id
                                ),
                            }
                        )

        return executed

    @staticmethod
    def _exploration_identifiers(
        *,
        finding_type: str,
        finding_value: str,
        seed: UnifiedSeed,
    ) -> dict[str, str]:
        kind = str(finding_type or "").strip().casefold().replace("-", "_")
        value = str(finding_value or "").strip()
        identifiers: dict[str, str] = {}
        if kind in {"username", "account", "profile", "social_profile"}:
            if seed.kind is UnifiedSeedKind.USERNAME:
                identifiers["username"] = seed.value
            elif value:
                identifiers["username"] = value.lstrip("@")
        elif kind in {"email", "phone", "domain", "url", "ip", "hash"} and value:
            identifiers[kind] = value
        return identifiers

    @staticmethod
    def _persistence_entity_ids(
        value: Any,
    ) -> set[UUID]:
        """Collect persisted technical Entity ids from enrichment results."""

        output: set[UUID] = set()

        def collect_persistence(rows: Any) -> None:
            for persistence in list(rows or []):
                for item in list(
                    getattr(
                        persistence,
                        "persisted",
                        [],
                    )
                    or []
                ):
                    for entity in list(
                        getattr(
                            item,
                            "entities",
                            (),
                        )
                        or ()
                    ):
                        entity_id = getattr(
                            entity,
                            "id",
                            None,
                        )
                        if isinstance(
                            entity_id,
                            UUID,
                        ):
                            output.add(
                                entity_id
                            )

        collect_persistence(
            getattr(
                value,
                "persistence",
                None,
            )
        )

        for run in list(
            getattr(
                value,
                "runs",
                [],
            )
            or []
        ):
            collect_persistence(
                getattr(
                    run,
                    "persistence",
                    None,
                )
            )

        return output

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
    def _public_result_row(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        # Internal extracted signal bags are only needed while consolidating.
        # The UI receives explanations/scores, not hidden provider metadata.
        out.pop("_identitySignals", None)
        out.pop("_identityContext", None)
        return out

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
    def _group_error_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        order: list[tuple[str, str, str]] = []
        for row in rows:
            lane = str(row.get("lane") or "Unknown")
            source = str(row.get("source") or "Unknown")
            error = " ".join(str(row.get("error") or "Unknown error").split())
            # Remove volatile request fragments while preserving the useful HTTP/error class.
            key_error = error.casefold()[:240]
            key = (lane.casefold(), source.casefold(), key_error)
            seed = str(row.get("seed") or "").strip()
            if key not in grouped:
                item = dict(row)
                item["attempts"] = 1
                item["seeds"] = [seed] if seed else []
                grouped[key] = item
                order.append(key)
            else:
                item = grouped[key]
                item["attempts"] = int(item.get("attempts") or 1) + 1
                seeds = list(item.get("seeds") or [])
                if seed and seed not in seeds:
                    seeds.append(seed)
                item["seeds"] = seeds[:8]
        for key in order:
            item = grouped[key]
            attempts = int(item.get("attempts") or 1)
            if attempts > 1:
                item["error"] = f"{item.get('error')} · {attempts} attempts grouped"
        return [grouped[key] for key in order]

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

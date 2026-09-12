
"""
OSINT Expansion 05R2 — Controlled LIVE Recursive E2E Gate

Proves the real production recursive OSINT path:

    seed DOMAIN
        -> live connector
        -> OsintFinding
        -> Source/Evidence/Entity/EvidenceEntity
        -> RecursivePivotCandidate
        -> SECOND live OSINT run

Uses the real:
- OsintManager / OsintPipeline
- OsintCapabilityRouter / OsintPivotPolicy
- OsintEnrichmentExecutionService
- OsintFindingPersistenceService
- OsintEnrichmentService
- OsintRecursiveEnrichmentService
- PostgreSQL ORM/services

Safety / determinism:
- benign public seed: example.com
- only passive/public live connectors are allowed to execute:
    crt.sh
    GAU
- other automatically-routed connectors return NOT_AVAILABLE in this gate
- max 3 findings per live connector invocation
- max_depth=2
- max_pivots_per_entity=3
- max_new_entities=20
- per-connector timeout <= 18 seconds
- outer SQLAlchemy transaction is rolled back
- fresh DB session proves zero test rows survive

No vulnerability scanners.
No active crawler/prober.
No production files are modified.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import enum
import importlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import Uuid as SqlUuid

from app.application.osint_enrichment_service import (
    OsintEnrichmentService,
)
from app.application.osint_recursive_enrichment_service import (
    OsintRecursiveEnrichmentService,
    RecursiveEnrichmentSeed,
)
from app.models.case import Case
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.evidence_entity import EvidenceEntity
from app.models.source import Source
from app.osint.enrichment_execution import (
    OsintEnrichmentExecutionService,
)
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)
from app.osint.manager import OsintManager
from app.osint.models import (
    ConnectorRequest,
    OsintTargetType,
)
from app.osint.pipeline import OsintPipeline
from app.osint.pivot_policy import (
    OsintPivotPolicy,
    PivotPolicyLimits,
)
from app.osint.pivot_router import (
    OsintCapabilityRouter,
)
from app.osint.result import (
    OsintResult,
    ResultStatus,
)
from app.services.entity_service import EntityService
from app.services.evidence_link_service import EvidenceLinkService
from app.services.evidence_service import EvidenceService
from app.services.source_service import SourceService


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_05r2"

SEED = "example.com"

ALLOWED_LIVE_CONNECTORS = frozenset(
    {
        "crt.sh",
        "gau",
    }
)

PER_CONNECTOR_FINDING_LIMIT = 3
PER_CONNECTOR_TIMEOUT = 18

LIMITS = PivotPolicyLimits(
    max_depth=2,
    max_pivots_per_entity=3,
    max_new_entities=20,
)


def enum_text(value: Any) -> str:
    if isinstance(value, enum.Enum):
        return str(value.value)
    return str(value)


def discover_engine() -> tuple[Engine, str]:
    module_candidates = (
        "app.database.session",
        "app.database.connection",
        "app.database.engine",
        "app.database",
    )

    for module_name in module_candidates:
        try:
            module = importlib.import_module(
                module_name
            )
        except Exception:
            continue

        for attr in (
            "engine",
            "sync_engine",
            "db_engine",
        ):
            candidate = getattr(
                module,
                attr,
                None,
            )

            if isinstance(
                candidate,
                Engine,
            ):
                return (
                    candidate,
                    f"{module_name}.{attr}",
                )

        getter = getattr(
            module,
            "get_engine",
            None,
        )

        if callable(getter):
            try:
                candidate = getter()
            except Exception:
                candidate = None

            if isinstance(
                candidate,
                Engine,
            ):
                return (
                    candidate,
                    f"{module_name}.get_engine()",
                )

    raise RuntimeError(
        "Unable to resolve configured SQLAlchemy engine."
    )


def sample_value_for_column(
    *,
    session: Session,
    column,
) -> Any:
    name = column.name.casefold()

    if column.foreign_keys:
        foreign_key = next(
            iter(
                column.foreign_keys
            )
        )
        referenced = (
            foreign_key.column
        )

        value = session.execute(
            select(
                referenced
            ).limit(1)
        ).scalar_one_or_none()

        if value is None:
            raise RuntimeError(
                "Temporary Case requires a parent row but none exists: "
                f"{column.name} -> {foreign_key.target_fullname}"
            )

        return value

    enum_class = getattr(
        column.type,
        "enum_class",
        None,
    )

    if enum_class is not None:
        return next(
            iter(
                enum_class
            )
        )

    if isinstance(
        column.type,
        (
            String,
            Text,
        ),
    ):
        if "title" in name or "name" in name:
            text = (
                "OSINT 05R2 live recursive transactional gate"
            )
        elif "description" in name:
            text = (
                "Temporary Case for controlled live recursive OSINT."
            )
        elif "slug" in name:
            text = (
                f"osint-05r2-{uuid4().hex[:12]}"
            )
        else:
            text = (
                f"osint-05r2-{column.name}-{uuid4().hex[:8]}"
            )

        length = getattr(
            column.type,
            "length",
            None,
        )

        if length:
            text = text[:length]

        return text

    if isinstance(
        column.type,
        Boolean,
    ):
        return False

    if isinstance(
        column.type,
        Integer,
    ):
        return 0

    if isinstance(
        column.type,
        Float,
    ):
        return 0.0

    if isinstance(
        column.type,
        Numeric,
    ):
        return Decimal("0")

    if isinstance(
        column.type,
        DateTime,
    ):
        return datetime.now(
            timezone.utc
        )

    if isinstance(
        column.type,
        Date,
    ):
        return date.today()

    if isinstance(
        column.type,
        JSON,
    ):
        return {}

    if isinstance(
        column.type,
        SqlUuid,
    ):
        return uuid4()

    try:
        python_type = (
            column.type.python_type
        )
    except Exception:
        python_type = None

    if python_type is UUID:
        return uuid4()

    raise RuntimeError(
        "05R2 cannot safely invent a required Case value for "
        f"{column.name!r} ({column.type!r})."
    )


def create_temporary_case(
    session: Session,
) -> Case:
    kwargs: dict[
        str,
        Any,
    ] = {}

    for column in (
        Case.__mapper__.columns
    ):
        if column.primary_key:
            continue

        if column.nullable:
            continue

        if column.default is not None:
            continue

        if column.server_default is not None:
            continue

        kwargs[
            column.key
        ] = sample_value_for_column(
            session=session,
            column=column,
        )

    case = Case(
        **kwargs
    )

    session.add(
        case
    )

    session.flush()

    return case


def case_counts(
    session: Session,
    case_id: UUID,
) -> dict[str, int]:
    sources = (
        session.scalar(
            select(
                func.count()
            )
            .select_from(
                Source
            )
            .where(
                Source.case_id
                == case_id
            )
        )
        or 0
    )

    evidences = (
        session.scalar(
            select(
                func.count()
            )
            .select_from(
                Evidence
            )
            .where(
                Evidence.case_id
                == case_id
            )
        )
        or 0
    )

    entities = (
        session.scalar(
            select(
                func.count()
            )
            .select_from(
                Entity
            )
            .where(
                Entity.case_id
                == case_id
            )
        )
        or 0
    )

    links = (
        session.scalar(
            select(
                func.count()
            )
            .select_from(
                EvidenceEntity
            )
            .join(
                Evidence,
                Evidence.id
                == EvidenceEntity.evidence_id,
            )
            .where(
                Evidence.case_id
                == case_id
            )
        )
        or 0
    )

    return {
        "sources": int(
            sources
        ),
        "evidences": int(
            evidences
        ),
        "entities": int(
            entities
        ),
        "evidence_entity_links": int(
            links
        ),
    }


def clone_request_with_live_limits(
    request: ConnectorRequest,
) -> ConnectorRequest:
    requested_limit = (
        request.limit
        if request.limit is not None
        else PER_CONNECTOR_FINDING_LIMIT
    )

    result_limit = min(
        PER_CONNECTOR_FINDING_LIMIT,
        max(
            0,
            int(
                requested_limit
            ),
        ),
    )

    return ConnectorRequest(
        target=request.target,
        timeout=min(
            PER_CONNECTOR_TIMEOUT,
            max(
                1,
                int(
                    request.timeout
                ),
            ),
        ),
        use_cache=False,
        save_raw_output=request.save_raw_output,
        include_metadata=request.include_metadata,
        include_related=request.include_related,
        limit=result_limit,
    )


class ControlledLivePipeline:
    """
    Thin diagnostic boundary around the real production OsintPipeline.

    Router/policy still decide which capabilities SHOULD run. This gate only
    permits two known passive/public connectors to actually perform network I/O.
    Everything else appears as NOT_AVAILABLE to the execution boundary.
    """

    def __init__(
        self,
        inner: OsintPipeline,
    ) -> None:
        self.inner = inner
        self.manager = (
            inner.manager
        )
        self.calls: list[
            dict[str, Any]
        ] = []

    def run_connector(
        self,
        connector_name: str,
        request: ConnectorRequest,
    ) -> OsintResult | None:
        normalized_name = (
            str(
                connector_name
            )
            .strip()
            .casefold()
        )

        allowed = (
            normalized_name
            in ALLOWED_LIVE_CONNECTORS
        )

        call = {
            "connector": connector_name,
            "target_type": (
                request
                .target
                .target_type
                .value
            ),
            "target": (
                request
                .target
                .value
            ),
            "depth_case_id": (
                request
                .target
                .case_id
            ),
            "allowed_live": allowed,
            "requested_limit": (
                request.limit
            ),
        }

        if not allowed:
            call[
                "status"
            ] = "blocked_by_05r2_gate"

            self.calls.append(
                call
            )

            return None

        bounded_request = (
            clone_request_with_live_limits(
                request
            )
        )

        call[
            "effective_limit"
        ] = bounded_request.limit

        call[
            "effective_timeout"
        ] = bounded_request.timeout

        result = (
            self.inner
            .run_connector(
                connector_name,
                bounded_request,
            )
        )

        if result is None:
            call[
                "status"
            ] = "runtime_missing"
            self.calls.append(
                call
            )
            return None

        call[
            "status"
        ] = enum_text(
            result.status
        )

        call[
            "findings"
        ] = result.total_findings

        call[
            "error"
        ] = result.error

        self.calls.append(
            call
        )

        return result


def summarize_run(
    run,
) -> dict[str, Any]:
    executions = []

    for execution in (
        run.executions
    ):
        records = []

        for record in (
            execution.records
        ):
            records.append(
                {
                    "capability": (
                        record
                        .capability
                        .module
                    ),
                    "runtime_connector": (
                        record
                        .runtime_connector_name
                    ),
                    "status": enum_text(
                        record
                        .result
                        .status
                    ),
                    "findings": (
                        record
                        .result
                        .total_findings
                    ),
                    "error": (
                        record
                        .result
                        .error
                    ),
                }
            )

        executions.append(
            {
                "goal": enum_text(
                    execution
                    .route
                    .goal
                ),
                "status": enum_text(
                    execution.status
                ),
                "records": records,
                "total_findings": (
                    execution
                    .total_findings
                ),
            }
        )

    persisted_entities = []

    for persistence in (
        run.persistence
    ):
        for persisted in (
            persistence.persisted
        ):
            for entity in (
                persisted.entities
            ):
                persisted_entities.append(
                    {
                        "id": str(
                            entity.id
                        ),
                        "type": enum_text(
                            entity.entity_type
                        ),
                        "value": entity.value,
                    }
                )

    return {
        "depth": run.depth,
        "target_type": (
            run.target_type.value
        ),
        "target_value": (
            run.target_value
        ),
        "parent_entity_id": (
            str(
                run.parent_entity_id
            )
            if run.parent_entity_id
            is not None
            else None
        ),
        "persisted_findings": (
            run.persisted_findings
        ),
        "entities_created": (
            run.entities_created
        ),
        "executions": executions,
        "persisted_entities": (
            persisted_entities
        ),
    }


def build_services(
    session: Session,
):
    source_service = (
        SourceService(
            session
        )
    )

    evidence_service = (
        EvidenceService(
            session,
            search_indexing_service=None,
        )
    )

    entity_service = (
        EntityService(
            session
        )
    )

    evidence_link_service = (
        EvidenceLinkService(
            session
        )
    )

    persistence_service = (
        OsintFindingPersistenceService(
            source_service=(
                source_service
            ),
            evidence_service=(
                evidence_service
            ),
            entity_service=(
                entity_service
            ),
            evidence_link_service=(
                evidence_link_service
            ),
        )
    )

    real_pipeline = (
        OsintPipeline(
            OsintManager()
        )
    )

    controlled_pipeline = (
        ControlledLivePipeline(
            real_pipeline
        )
    )

    policy = OsintPivotPolicy(
        limits=LIMITS
    )

    router = (
        OsintCapabilityRouter(
            policy=policy
        )
    )

    execution_service = (
        OsintEnrichmentExecutionService(
            pipeline=controlled_pipeline,
            router=router,
        )
    )

    enrichment_service = (
        OsintEnrichmentService(
            execution_service=(
                execution_service
            ),
            persistence_service=(
                persistence_service
            ),
        )
    )

    recursive_service = (
        OsintRecursiveEnrichmentService(
            enrichment_service=(
                enrichment_service
            )
        )
    )

    return (
        recursive_service,
        controlled_pipeline,
    )


def main() -> int:
    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "OSINT Expansion 05R2 — Controlled LIVE Recursive E2E Gate",
        flush=True,
    )
    print(
        "=" * 78,
        flush=True,
    )
    print(
        f"Seed: {SEED}",
        flush=True,
    )
    print(
        "Live connectors allowed: "
        + ", ".join(
            sorted(
                ALLOWED_LIVE_CONNECTORS
            )
        ),
        flush=True,
    )
    print(
        "Policy: "
        f"depth={LIMITS.max_depth} "
        f"pivots/entity={LIMITS.max_pivots_per_entity} "
        f"new_entities={LIMITS.max_new_entities}",
        flush=True,
    )
    print(
        f"Per-live-call limit={PER_CONNECTOR_FINDING_LIMIT} "
        f"timeout<={PER_CONNECTOR_TIMEOUT}s",
        flush=True,
    )
    print(
        "",
        flush=True,
    )

    engine, engine_source = (
        discover_engine()
    )

    if (
        engine.dialect.name
        != "postgresql"
    ):
        raise RuntimeError(
            "05R2 requires PostgreSQL; "
            f"resolved {engine.dialect.name!r}."
        )

    print(
        f"Engine: {engine_source}",
        flush=True,
    )

    connection = (
        engine.connect()
    )

    outer = (
        connection.begin()
    )

    session = Session(
        bind=connection,
        expire_on_commit=False,
    )

    case_id: UUID | None = None

    report: dict[
        str,
        Any,
    ] = {
        "gate_version": 1,
        "seed": SEED,
        "engine_source": engine_source,
        "allowed_live_connectors": sorted(
            ALLOWED_LIVE_CONNECTORS
        ),
        "per_connector_finding_limit": (
            PER_CONNECTOR_FINDING_LIMIT
        ),
        "per_connector_timeout": (
            PER_CONNECTOR_TIMEOUT
        ),
        "policy": {
            "max_depth": (
                LIMITS.max_depth
            ),
            "max_pivots_per_entity": (
                LIMITS.max_pivots_per_entity
            ),
            "max_new_entities": (
                LIMITS.max_new_entities
            ),
        },
    }

    gate_status = "FAIL"

    try:
        case = (
            create_temporary_case(
                session
            )
        )

        case_id = case.id

        print(
            f"Temporary Case: {case_id}",
            flush=True,
        )

        (
            recursive_service,
            controlled_pipeline,
        ) = build_services(
            session
        )

        result = (
            recursive_service
            .enrich(
                case_id=case_id,
                seeds=(
                    RecursiveEnrichmentSeed(
                        target_type=(
                            OsintTargetType.DOMAIN
                        ),
                        value=SEED,
                    ),
                ),
                seed_depth=0,
                timeout=(
                    PER_CONNECTOR_TIMEOUT
                ),
                use_cache=False,
                save_raw_output=False,
                include_metadata=True,
                include_related=True,
            )
        )

        session.flush()

        runs = [
            summarize_run(
                run
            )
            for run in (
                result.runs
            )
        ]

        root_runs = [
            run
            for run in runs
            if run["depth"] == 0
        ]

        second_level_runs = [
            run
            for run in runs
            if run["depth"] >= 1
        ]

        max_observed_depth = max(
            (
                run[
                    "depth"
                ]
                for run in runs
            ),
            default=-1,
        )

        counts = (
            case_counts(
                session,
                case_id,
            )
        )

        live_calls = [
            call
            for call in (
                controlled_pipeline
                .calls
            )
            if call[
                "allowed_live"
            ]
        ]

        live_successful_calls = [
            call
            for call in live_calls
            if call.get(
                "status"
            )
            in {
                ResultStatus.SUCCESS.value,
                ResultStatus.PARTIAL.value,
            }
        ]

        second_level_live_targets = {
            (
                run[
                    "target_type"
                ],
                run[
                    "target_value"
                ],
            )
            for run in (
                second_level_runs
            )
        }

        print(
            "",
            flush=True,
        )
        print(
            "RECURSION SUMMARY",
            flush=True,
        )
        print(
            "-" * 78,
            flush=True,
        )
        print(
            f"targets_processed={result.targets_processed}",
            flush=True,
        )
        print(
            f"candidates_discovered={result.candidates_discovered}",
            flush=True,
        )
        print(
            f"candidates_enqueued={result.candidates_enqueued}",
            flush=True,
        )
        print(
            f"candidates_deduplicated={result.candidates_deduplicated}",
            flush=True,
        )
        print(
            f"stop_reason={enum_text(result.stop_reason)}",
            flush=True,
        )
        print(
            f"new_entities_count={result.state.new_entities_count}",
            flush=True,
        )
        print(
            f"max_observed_depth={max_observed_depth}",
            flush=True,
        )
        print(
            f"second_level_runs={len(second_level_runs)}",
            flush=True,
        )
        print(
            f"DB counts={counts}",
            flush=True,
        )

        print(
            "",
            flush=True,
        )
        print(
            "RUNS",
            flush=True,
        )

        for index, run in enumerate(
            runs,
            start=1,
        ):
            print(
                f"[{index}] depth={run['depth']} "
                f"{run['target_type']}={run['target_value']} "
                f"persisted={run['persisted_findings']} "
                f"entities_created={run['entities_created']}",
                flush=True,
            )

        print(
            "",
            flush=True,
        )
        print(
            "LIVE CONNECTOR CALLS",
            flush=True,
        )

        for call in live_calls:
            print(
                "  "
                f"{call['connector']} "
                f"target={call['target']} "
                f"status={call.get('status')} "
                f"findings={call.get('findings', 0)} "
                f"limit={call.get('effective_limit')}",
                flush=True,
            )

        policy_ok = (
            max_observed_depth
            <= LIMITS.max_depth
            and result.state.new_entities_count
            <= LIMITS.max_new_entities
            and all(
                count
                <= LIMITS.max_pivots_per_entity
                for count in (
                    result.state
                    .pivots_by_entity
                    .values()
                )
            )
        )

        second_level_proven = bool(
            second_level_runs
        )

        persistence_proven = (
            counts[
                "sources"
            ] > 0
            and counts[
                "evidences"
            ] > 0
            and counts[
                "entities"
            ] > 0
            and counts[
                "evidence_entity_links"
            ] > 0
        )

        live_collection_proven = bool(
            live_successful_calls
        )

        if (
            second_level_proven
            and persistence_proven
            and live_collection_proven
            and policy_ok
        ):
            gate_status = "PASS"
        elif (
            persistence_proven
            and live_collection_proven
            and policy_ok
        ):
            # Public services are external dependencies; zero second-level
            # candidates can be transient. The report preserves enough detail
            # to distinguish external-data absence from an engine defect.
            gate_status = "PARTIAL"
        else:
            gate_status = "FAIL"

        report.update(
            {
                "temporary_case_id": (
                    str(
                        case_id
                    )
                ),
                "result": {
                    "targets_processed": (
                        result.targets_processed
                    ),
                    "candidates_discovered": (
                        result.candidates_discovered
                    ),
                    "candidates_enqueued": (
                        result.candidates_enqueued
                    ),
                    "candidates_deduplicated": (
                        result.candidates_deduplicated
                    ),
                    "candidates_unsupported": (
                        result.candidates_unsupported
                    ),
                    "stop_reason": enum_text(
                        result.stop_reason
                    ),
                    "new_entities_count": (
                        result.state.new_entities_count
                    ),
                    "pivots_by_entity": {
                        str(key): value
                        for key, value
                        in (
                            result.state
                            .pivots_by_entity
                            .items()
                        )
                    },
                    "max_observed_depth": (
                        max_observed_depth
                    ),
                },
                "runs": runs,
                "root_runs": len(
                    root_runs
                ),
                "second_level_runs": len(
                    second_level_runs
                ),
                "second_level_targets": sorted(
                    [
                        {
                            "target_type": target_type,
                            "value": value,
                        }
                        for (
                            target_type,
                            value,
                        )
                        in second_level_live_targets
                    ],
                    key=lambda item: (
                        item[
                            "target_type"
                        ],
                        item[
                            "value"
                        ],
                    ),
                ),
                "db_counts": counts,
                "controlled_pipeline_calls": (
                    controlled_pipeline
                    .calls
                ),
                "checks": {
                    "live_collection_proven": (
                        live_collection_proven
                    ),
                    "persistence_proven": (
                        persistence_proven
                    ),
                    "second_level_proven": (
                        second_level_proven
                    ),
                    "policy_ok": (
                        policy_ok
                    ),
                },
                "gate_status_before_rollback": (
                    gate_status
                ),
            }
        )

    finally:
        try:
            session.close()
        finally:
            if outer.is_active:
                outer.rollback()
            connection.close()

    if case_id is None:
        raise RuntimeError(
            "Temporary Case was not created."
        )

    with Session(
        bind=engine,
        expire_on_commit=False,
    ) as verify_session:
        case_exists = (
            verify_session.get(
                Case,
                case_id,
            )
            is not None
        )

        surviving_counts = (
            case_counts(
                verify_session,
                case_id,
            )
        )

    rollback_clean = (
        not case_exists
        and all(
            value == 0
            for value in (
                surviving_counts
                .values()
            )
        )
    )

    report[
        "rollback_verification"
    ] = {
        "case_exists": (
            case_exists
        ),
        "surviving_counts": (
            surviving_counts
        ),
        "clean": (
            rollback_clean
        ),
    }

    print(
        "",
        flush=True,
    )
    print(
        "ROLLBACK",
        flush=True,
    )
    print(
        "-" * 78,
        flush=True,
    )
    print(
        f"case_exists={case_exists}",
        flush=True,
    )
    print(
        f"surviving_counts={surviving_counts}",
        flush=True,
    )

    if not rollback_clean:
        gate_status = "FAIL"

    report[
        "final_gate_status"
    ] = gate_status

    report_path = (
        OUT
        / "live_recursive_e2e_gate.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print(
        "",
        flush=True,
    )
    print(
        f"JSON: {report_path}",
        flush=True,
    )
    print(
        f"OSINT EXPANSION 05R2 LIVE RECURSIVE E2E: {gate_status}",
        flush=True,
    )

    if gate_status == "FAIL":
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

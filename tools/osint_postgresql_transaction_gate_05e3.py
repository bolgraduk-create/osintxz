
"""
OSINT Expansion 05E3b — Transactional PostgreSQL Persistence/Pivot Gate

Proves against the real PostgreSQL schema:

    OsintFinding
        -> Source
        -> Evidence
        -> Entity
        -> EvidenceEntity
        -> RecursivePivotCandidate

The script:
- uses current production services and ORM models;
- creates a temporary Case inside an outer SQLAlchemy transaction;
- persists synthetic discovery-chain findings;
- verifies DB rows and pivot candidates;
- repeats persistence to verify idempotency;
- rolls the OUTER transaction back;
- opens a fresh connection and proves the temporary Case does not exist.

No external OSINT/network calls are made.
No test data should remain in PostgreSQL.
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
    Enum as SqlEnum,
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

from app.models.case import Case
from app.models.entity import Entity, EntityType
from app.models.evidence import Evidence
from app.models.evidence_entity import EvidenceEntity
from app.models.source import Source
from app.osint.capabilities import (
    DiscoveryGoal,
    OsintConnectorCapability,
    get_capability,
)
from app.osint.enrichment_execution import (
    ConnectorExecutionRecord,
    EnrichmentExecutionResult,
    EnrichmentExecutionStatus,
    NewEntityBudget,
)
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)
from app.osint.models import OsintTargetType
from app.osint.pivot_candidates import (
    OsintPivotCandidatePolicy,
)
from app.osint.result import (
    OsintFinding,
    OsintResult,
    ResultStatus,
)
from app.services.entity_service import EntityService
from app.services.evidence_link_service import EvidenceLinkService
from app.services.evidence_service import EvidenceService
from app.services.source_service import SourceService


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_05e3"

CASE_TITLE = "OSINT 05E3 transactional gate"


def enum_text(value: Any) -> str:
    if isinstance(value, enum.Enum):
        return str(value.value)
    return str(value)


def discover_engine() -> tuple[Engine, str]:
    """
    Resolve the project's already-configured SQLAlchemy engine without
    rebuilding database configuration in the diagnostic script.
    """

    module_candidates = (
        "app.database.session",
        "app.database.connection",
        "app.database.engine",
        "app.database",
    )

    engine_attributes = (
        "engine",
        "sync_engine",
        "db_engine",
    )

    session_factories = (
        "SessionLocal",
        "session_factory",
        "SessionFactory",
    )

    errors: list[str] = []

    for module_name in module_candidates:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            errors.append(
                f"{module_name}: import {type(exc).__name__}: {exc}"
            )
            continue

        for attr in engine_attributes:
            candidate = getattr(module, attr, None)

            if isinstance(candidate, Engine):
                return candidate, f"{module_name}.{attr}"

        get_engine = getattr(module, "get_engine", None)

        if callable(get_engine):
            try:
                candidate = get_engine()
            except Exception as exc:
                errors.append(
                    f"{module_name}.get_engine(): {type(exc).__name__}: {exc}"
                )
            else:
                if isinstance(candidate, Engine):
                    return candidate, f"{module_name}.get_engine()"

        for attr in session_factories:
            factory = getattr(module, attr, None)

            if factory is None or not callable(factory):
                continue

            session = None
            try:
                session = factory()
                bind = session.get_bind()

                if isinstance(bind, Engine):
                    return bind, f"{module_name}.{attr}().get_bind()"

                engine = getattr(bind, "engine", None)

                if isinstance(engine, Engine):
                    return engine, f"{module_name}.{attr}().get_bind().engine"

            except Exception as exc:
                errors.append(
                    f"{module_name}.{attr}(): {type(exc).__name__}: {exc}"
                )
            finally:
                if session is not None:
                    try:
                        session.close()
                    except Exception:
                        pass

    raise RuntimeError(
        "Unable to resolve the configured SQLAlchemy engine.\n"
        + "\n".join(errors[-20:])
    )


def sample_value_for_column(
    *,
    session: Session,
    column,
) -> Any:
    """
    Produce a value only for a required Case column that has no default.

    Foreign keys are satisfied by an existing referenced row if the current
    Case schema requires one. Most Case schemas need no such parent row.
    """

    name = column.name.casefold()

    if column.foreign_keys:
        foreign_key = next(iter(column.foreign_keys))
        referenced = foreign_key.column

        value = session.execute(
            select(referenced).limit(1)
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
        return next(iter(enum_class))

    if isinstance(column.type, (String, Text)):
        if "title" in name:
            text = CASE_TITLE
        elif "name" in name:
            text = CASE_TITLE
        elif "description" in name:
            text = (
                "Temporary transactional Case created by OSINT Expansion 05E3."
            )
        elif "slug" in name:
            text = f"osint-05e3-{uuid4().hex[:12]}"
        else:
            text = f"osint-05e3-{column.name}-{uuid4().hex[:8]}"

        length = getattr(column.type, "length", None)

        if length:
            text = text[:length]

        return text

    if isinstance(column.type, Boolean):
        return False

    if isinstance(column.type, Integer):
        return 0

    if isinstance(column.type, Float):
        return 0.0

    if isinstance(column.type, Numeric):
        return Decimal("0")

    if isinstance(column.type, DateTime):
        return datetime.now(timezone.utc)

    if isinstance(column.type, Date):
        return date.today()

    if isinstance(column.type, JSON):
        return {}

    if isinstance(column.type, SqlUuid):
        return uuid4()

    try:
        python_type = column.type.python_type
    except Exception:
        python_type = None

    if python_type is UUID:
        return uuid4()

    raise RuntimeError(
        "05E3 cannot safely invent a value for required Case column "
        f"{column.name!r} ({column.type!r})."
    )


def create_temporary_case(
    session: Session,
) -> Case:
    mapper = Case.__mapper__

    kwargs: dict[str, Any] = {}

    for column in mapper.columns:
        if column.primary_key:
            continue

        if column.nullable:
            continue

        if column.default is not None:
            continue

        if column.server_default is not None:
            continue

        kwargs[column.key] = sample_value_for_column(
            session=session,
            column=column,
        )

    case = Case(**kwargs)

    session.add(case)
    session.flush()

    return case


def capability(
    *,
    module: str,
    connector_class: str,
    goal: DiscoveryGoal,
) -> OsintConnectorCapability:
    """
    Resolve the connector's REAL production capability catalog entry.

    05E3 must validate persistence/provenance using the same immutable
    capability metadata that the router uses in production. Reconstructing
    OsintConnectorCapability dynamically is both unnecessary and brittle:
    required policy enums such as ConnectorDisposition and NetworkMode belong
    to the central catalog, not to this diagnostic.
    """

    module_stem = (
        str(module)
        .strip()
        .rsplit(".", 1)[-1]
    )

    resolved = get_capability(
        module_stem
    )

    if resolved is None:
        raise RuntimeError(
            "No production OSINT capability exists for "
            f"{module_stem!r}."
        )

    # The production capability catalog is authoritative for connector class
    # naming. Diagnostic code must not reconstruct or validate class names from
    # display names (for example "GAU" -> "GAUConnector" is wrong because the
    # real class is "GauConnector").
    _ = connector_class

    # Do not require the outer synthetic persistence goal to be one of the
    # connector's own routing goals. The production persistence layer stores
    # record.capability.module for provenance, while `goal` describes the
    # enrichment operation being persisted. For example HTTPX is catalogued
    # under WEB_METADATA even when its finding is part of this controlled
    # DOMAIN discovery integration fixture.
    _ = goal

    return resolved


def record(
    *,
    connector: str,
    module: str,
    findings: list[OsintFinding],
    goal: DiscoveryGoal,
) -> ConnectorExecutionRecord:
    return ConnectorExecutionRecord(
        capability=capability(
            module=module,
            connector_class=f"{connector}Connector",
            goal=goal,
        ),
        runtime_connector_name=connector,
        result=OsintResult(
            connector=connector,
            status=ResultStatus.SUCCESS,
            findings=findings,
        ),
    )


def build_execution(
    *,
    entity_budget: int,
) -> EnrichmentExecutionResult:
    goal = DiscoveryGoal.DOMAIN_DISCOVERY

    records = [
        record(
            connector="Assetfinder",
            module="app.osint.connectors.assetfinder_connector",
            goal=goal,
            findings=[
                OsintFinding(
                    category="subdomain",
                    value="dev.example.com",
                    source="Assetfinder",
                )
            ],
        ),
        record(
            connector="DNSX",
            module="app.osint.connectors.dnsx_connector",
            goal=goal,
            findings=[
                OsintFinding(
                    category="dns",
                    value="dev.example.com",
                    source="DNSX",
                    metadata={
                        "host": "dev.example.com",
                        "a": [
                            "203.0.113.10",
                        ],
                        "aaaa": [
                            "2001:db8::10",
                        ],
                    },
                )
            ],
        ),
        record(
            connector="HTTPX",
            module="app.osint.connectors.httpx_connector",
            goal=goal,
            findings=[
                OsintFinding(
                    category="http",
                    value="https://dev.example.com",
                    url="https://dev.example.com",
                    source="HTTPX",
                    metadata={
                        "host": "dev.example.com",
                        "host_ip": "203.0.113.10",
                        "a": [
                            "203.0.113.10",
                        ],
                        "aaaa": [
                            "2001:db8::10",
                        ],
                        "status_code": 200,
                    },
                )
            ],
        ),
        record(
            connector="Katana",
            module="app.osint.connectors.katana_connector",
            goal=goal,
            findings=[
                OsintFinding(
                    category="endpoint",
                    value="https://dev.example.com/api",
                    url="https://dev.example.com/api",
                    source="Katana",
                )
            ],
        ),
        record(
            connector="GAU",
            module="app.osint.connectors.gau_connector",
            goal=goal,
            findings=[
                OsintFinding(
                    category="historical_url",
                    value="https://dev.example.com/old",
                    url="https://dev.example.com/old",
                    source="GAU",
                )
            ],
        ),
    ]

    # The persistence layer uses route.goal only.
    route = type(
        "05E3Route",
        (),
        {"goal": goal},
    )()

    return EnrichmentExecutionResult(
        route=route,
        status=EnrichmentExecutionStatus.SUCCESS,
        records=records,
        entity_budget=NewEntityBudget(
            limit=entity_budget,
        ),
    )


def case_counts(
    session: Session,
    case_id: UUID,
) -> dict[str, int]:
    source_count = session.scalar(
        select(func.count())
        .select_from(Source)
        .where(Source.case_id == case_id)
    ) or 0

    evidence_count = session.scalar(
        select(func.count())
        .select_from(Evidence)
        .where(Evidence.case_id == case_id)
    ) or 0

    entity_count = session.scalar(
        select(func.count())
        .select_from(Entity)
        .where(Entity.case_id == case_id)
    ) or 0

    link_count = session.scalar(
        select(func.count())
        .select_from(EvidenceEntity)
        .join(
            Evidence,
            Evidence.id == EvidenceEntity.evidence_id,
        )
        .where(Evidence.case_id == case_id)
    ) or 0

    return {
        "sources": int(source_count),
        "evidences": int(evidence_count),
        "entities": int(entity_count),
        "evidence_entity_links": int(link_count),
    }


def main() -> int:
    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "OSINT Expansion 05E3b — Transactional PostgreSQL Persistence/Pivot Gate",
        flush=True,
    )
    print("=" * 78, flush=True)

    engine, engine_source = discover_engine()

    print(
        f"Engine resolved via: {engine_source}",
        flush=True,
    )
    print(
        f"Dialect: {engine.dialect.name}",
        flush=True,
    )

    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            "05E3 requires the real PostgreSQL database; "
            f"resolved dialect is {engine.dialect.name!r}."
        )

    connection = engine.connect()
    outer = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
    )

    case_id: UUID | None = None
    report: dict[str, Any] = {
        "gate_version": "05E3b",
        "engine_source": engine_source,
        "dialect": engine.dialect.name,
    }

    try:
        case = create_temporary_case(
            session,
        )

        case_id = case.id

        print(
            f"Temporary Case: {case_id}",
            flush=True,
        )

        source_service = SourceService(
            session
        )
        evidence_service = EvidenceService(
            session,
            search_indexing_service=None,
        )
        entity_service = EntityService(
            session
        )
        evidence_link_service = (
            EvidenceLinkService(
                session
            )
        )

        persistence = (
            OsintFindingPersistenceService(
                source_service=source_service,
                evidence_service=evidence_service,
                entity_service=entity_service,
                evidence_link_service=evidence_link_service,
            )
        )

        execution = build_execution(
            entity_budget=12,
        )

        first = persistence.persist_execution(
            case_id=case_id,
            target_type=OsintTargetType.DOMAIN,
            target_value="example.com",
            goal=DiscoveryGoal.DOMAIN_DISCOVERY,
            execution=execution,
        )

        session.flush()

        first_counts = case_counts(
            session,
            case_id,
        )

        candidates = (
            OsintPivotCandidatePolicy()
            .from_persistence_results(
                [
                    first,
                ],
                next_depth=1,
            )
        )

        candidate_types = sorted(
            {
                enum_text(
                    item.target_type
                )
                for item in candidates
            }
        )

        candidate_values = sorted(
            {
                item.value
                for item in candidates
            }
        )

        print(
            "First persistence:",
            flush=True,
        )
        print(
            "  "
            f"sources_created={first.sources_created} "
            f"evidences_created={first.evidences_created} "
            f"entities_created={first.entities_created} "
            f"links_created={first.links_created}",
            flush=True,
        )
        print(
            f"  DB counts={first_counts}",
            flush=True,
        )
        print(
            f"  pivot_types={candidate_types}",
            flush=True,
        )

        if first.persisted_findings != 5:
            raise AssertionError(
                "Expected 5 persisted discovery findings; "
                f"got {first.persisted_findings}."
            )

        if first_counts["sources"] < 5:
            raise AssertionError(
                "Expected one OSINT Source per connector/capability path."
            )

        if first_counts["evidences"] != 5:
            raise AssertionError(
                "Expected exactly 5 Evidence rows."
            )

        if first_counts["entities"] < 6:
            raise AssertionError(
                "Expected persisted DOMAIN/IP/URL entities from the "
                "verified discovery-chain categories."
            )

        if first_counts["evidence_entity_links"] < 5:
            raise AssertionError(
                "Expected EvidenceEntity provenance links."
            )

        required_types = {
            OsintTargetType.DOMAIN.value,
            OsintTargetType.IP.value,
            OsintTargetType.URL.value,
        }

        if not required_types.issubset(
            set(candidate_types)
        ):
            raise AssertionError(
                "Persisted entities did not expose DOMAIN/IP/URL pivots. "
                f"Got {candidate_types}."
            )

        if (
            execution.entity_budget is None
            or execution.entity_budget.consumed
            != first.entities_created
        ):
            raise AssertionError(
                "NewEntityBudget consumption does not match physical "
                "Entity creation."
            )

        # Repeat the exact execution with a fresh budget. Source/evidence/entity
        # provenance should be idempotent inside the same Case.
        second_execution = build_execution(
            entity_budget=12,
        )

        second = persistence.persist_execution(
            case_id=case_id,
            target_type=OsintTargetType.DOMAIN,
            target_value="example.com",
            goal=DiscoveryGoal.DOMAIN_DISCOVERY,
            execution=second_execution,
        )

        session.flush()

        second_counts = case_counts(
            session,
            case_id,
        )

        print(
            "Second identical persistence:",
            flush=True,
        )
        print(
            "  "
            f"sources_created={second.sources_created} "
            f"evidences_created={second.evidences_created} "
            f"entities_created={second.entities_created} "
            f"links_created={second.links_created}",
            flush=True,
        )
        print(
            f"  DB counts={second_counts}",
            flush=True,
        )

        if second_counts != first_counts:
            raise AssertionError(
                "Idempotency failure: physical DB counts changed after "
                "identical persistence."
            )

        if any(
            (
                second.sources_created,
                second.evidences_created,
                second.entities_created,
                second.links_created,
            )
        ):
            raise AssertionError(
                "Idempotency failure: duplicate DB objects/links were reported."
            )

        report.update(
            {
                "temporary_case_id": str(case_id),
                "first_persistence": {
                    "persisted_findings": first.persisted_findings,
                    "sources_created": first.sources_created,
                    "evidences_created": first.evidences_created,
                    "entities_created": first.entities_created,
                    "links_created": first.links_created,
                    "db_counts": first_counts,
                    "entity_budget_consumed": (
                        execution.entity_budget.consumed
                        if execution.entity_budget is not None
                        else None
                    ),
                },
                "pivot_candidates": {
                    "count": len(candidates),
                    "target_types": candidate_types,
                    "values": candidate_values,
                },
                "second_identical_persistence": {
                    "sources_created": second.sources_created,
                    "evidences_created": second.evidences_created,
                    "entities_created": second.entities_created,
                    "links_created": second.links_created,
                    "db_counts": second_counts,
                },
            }
        )

        print("", flush=True)
        print(
            "IN-TRANSACTION CONTRACT: PASS",
            flush=True,
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
            "Temporary Case was never created."
        )

    # Verify rollback from a fresh connection/session.
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
            for value in surviving_counts.values()
        )
    )

    report["rollback_verification"] = {
        "case_exists": case_exists,
        "surviving_counts": surviving_counts,
        "clean": rollback_clean,
    }

    print(
        "Rollback verification:",
        flush=True,
    )
    print(
        f"  case_exists={case_exists}",
        flush=True,
    )
    print(
        f"  surviving_counts={surviving_counts}",
        flush=True,
    )

    if not rollback_clean:
        raise AssertionError(
            "05E3 rollback verification failed: temporary data survived."
        )

    report_path = (
        OUT
        / "postgresql_transaction_gate.json"
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

    print("", flush=True)
    print(
        f"JSON: {report_path}",
        flush=True,
    )
    print(
        "OSINT EXPANSION 05E3b POSTGRESQL TRANSACTION GATE: PASS",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

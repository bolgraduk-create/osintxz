"""Live rollback-only probe for M022.2D Registry persistence.

The probe validates the real end-to-end path:

    EDRPOU -> desktop Registry Intelligence -> Registry Backend
           -> RegistryPersistenceService -> Source/Evidence/Entity

The database transaction is always rolled back, so the probe leaves no
persistent investigation data behind.
"""
from __future__ import annotations

import argparse
from uuid import UUID

from sqlalchemy import select

from app.core.service_container import ServiceContainer
from app.database.session import create_session
from app.models.case import Case
from app.models.entity import EntityType
from app.registry_intelligence.query_detection import detect_registry_query


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--edrpou",
        default="14359609",
        help="Exact Ukrainian EDRPOU identifier to probe.",
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help=(
            "Existing case UUID used only inside a rollback-only transaction. "
            "If omitted, the first existing case is used."
        ),
    )
    return parser.parse_args()


def _resolve_case_id(session, raw_case_id: str | None) -> UUID:
    if raw_case_id:
        return UUID(str(raw_case_id))

    case_id = session.scalar(select(Case.id).limit(1))
    if case_id is None:
        raise RuntimeError(
            "No case exists in the desktop database. Create one case first or "
            "pass --case-id <UUID>."
        )
    return UUID(str(case_id))


def _assert_first_pass(result, expected_edrpou: str) -> None:
    if len(result.search.records) != 1:
        raise AssertionError(
            f"Expected exactly one RegistryRecord, got {len(result.search.records)}."
        )

    record = result.search.records[0]
    if (record.registration_id or "").strip() != expected_edrpou:
        raise AssertionError(
            "Registry Backend returned an unexpected registration identifier: "
            f"{record.registration_id!r}."
        )
    if record.metadata.get("candidate_only"):
        raise AssertionError("Exact EDRPOU result must not be candidate_only.")

    persisted = result.persistence
    if len(persisted.records) != 1:
        raise AssertionError(
            f"Expected one persisted registry record, got {len(persisted.records)}."
        )

    item = persisted.records[0]
    if not item.entities:
        raise AssertionError("Registry record was not linked to an Entity.")

    organization = next(
        (
            entity
            for entity in item.entities
            if entity.entity_type is EntityType.ORGANIZATION
        ),
        None,
    )
    if organization is None:
        raise AssertionError("Exact company record did not resolve to ORGANIZATION.")

    if persisted.errors:
        raise AssertionError(f"Persistence reported errors: {persisted.errors!r}")


def _assert_second_pass_is_idempotent(result) -> None:
    persisted = result.persistence
    nonzero = {
        "sources_created": persisted.sources_created,
        "evidences_created": persisted.evidences_created,
        "entities_created": persisted.entities_created,
        "links_created": persisted.links_created,
    }
    nonzero = {key: value for key, value in nonzero.items() if value}
    if nonzero:
        raise AssertionError(
            "Second persistence pass created duplicates: "
            f"{nonzero!r}."
        )
    if persisted.errors:
        raise AssertionError(f"Second pass reported errors: {persisted.errors!r}")


def main() -> int:
    args = _parse_args()
    edrpou = str(args.edrpou).strip()
    if not edrpou:
        raise ValueError("--edrpou must not be empty.")

    query = detect_registry_query(f"edrpou:{edrpou}")
    if query is None:
        raise RuntimeError("Failed to build EDRPOU RegistryQuery.")

    session = create_session()
    container = ServiceContainer(session)

    try:
        case_id = _resolve_case_id(session, args.case_id)
        print(f"case_id: {case_id}")
        print(f"edrpou: {edrpou}")
        print("transaction: rollback-only")

        first = container.registry_intelligence_service.enrich(
            query,
            case_id=case_id,
        )
        session.flush()
        _assert_first_pass(first, edrpou)

        first_record = first.search.records[0]
        first_item = first.persistence.records[0]
        print("first_pass: PASS")
        print(f"name: {first_record.display_name}")
        print(f"provider: {first_record.provider}")
        print(f"source_id: {first_item.source.id}")
        print(f"evidence_id: {first_item.evidence.id}")
        print(f"resolution_method: {first_item.resolution_method}")
        print(
            "created: "
            f"sources={first.persistence.sources_created}; "
            f"evidences={first.persistence.evidences_created}; "
            f"entities={first.persistence.entities_created}; "
            f"links={first.persistence.links_created}"
        )

        second = container.registry_intelligence_service.enrich(
            query,
            case_id=case_id,
        )
        session.flush()
        _assert_second_pass_is_idempotent(second)
        print("second_pass_idempotency: PASS")
        print(
            "created_again: "
            f"sources={second.persistence.sources_created}; "
            f"evidences={second.persistence.evidences_created}; "
            f"entities={second.persistence.entities_created}; "
            f"links={second.persistence.links_created}"
        )

        print("M022.2D LIVE PERSISTENCE PROBE: PASS")
        return 0
    finally:
        try:
            container.rollback()
        finally:
            container.close()


if __name__ == "__main__":
    raise SystemExit(main())

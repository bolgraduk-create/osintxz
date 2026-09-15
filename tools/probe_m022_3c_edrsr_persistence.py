"""Live rollback-only probe for M022.3C EDRSR desktop integration.

Validates the real path without leaving investigation data behind:

    case number -> Desktop RegistryIntelligenceService -> RemoteRegistryProvider
                -> Registry Backend -> central EDRSR mirror
                -> Source/Evidence only (no automatic Entity identity resolution)
"""
from __future__ import annotations

import argparse
from uuid import UUID

from sqlalchemy import select

from app.core.service_container import ServiceContainer
from app.database.session import create_session
from app.models.case import Case
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryResultStatus,
)
from app.registry_intelligence.query_detection import detect_registry_query


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case-number",
        required=True,
        help="Exact EDRSR court case number known to exist in the synchronized mirror.",
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help=(
            "Existing investigation case UUID used only inside a rollback-only transaction. "
            "If omitted, the first existing investigation case is used."
        ),
    )
    return parser.parse_args()


def _resolve_case_id(session, raw_case_id: str | None) -> UUID:
    if raw_case_id:
        return UUID(str(raw_case_id))
    case_id = session.scalar(select(Case.id).limit(1))
    if case_id is None:
        raise RuntimeError(
            "No investigation case exists. Create one case first or pass --case-id <UUID>."
        )
    return UUID(str(case_id))


def _assert_search(result, expected_case_number: str) -> None:
    edrsr_results = [
        item
        for item in result.search.provider_results
        if item.provider == "ua_edrsr"
    ]
    if len(edrsr_results) != 1:
        raise AssertionError(f"Expected one ua_edrsr provider result, got {len(edrsr_results)}.")
    provider_result = edrsr_results[0]
    if provider_result.status not in {RegistryResultStatus.SUCCESS, RegistryResultStatus.PARTIAL}:
        raise AssertionError(
            f"ua_edrsr provider is not usable: {provider_result.status.value}; "
            f"error={provider_result.error!r}"
        )
    if not result.search.records:
        raise AssertionError("EDRSR returned no records for the supplied exact case number.")

    for record in result.search.records:
        if record.provider != "ua_edrsr":
            raise AssertionError(f"Unexpected provider in court result: {record.provider!r}.")
        if record.domain is not RegistryDomain.COURT:
            raise AssertionError(f"Unexpected registry domain: {record.domain!r}.")
        if record.entity_kind is not RegistryEntityKind.COURT_DECISION:
            raise AssertionError(f"Unexpected court entity kind: {record.entity_kind!r}.")
        if record.identifiers.get("CASE_NUMBER") != expected_case_number:
            raise AssertionError(
                "EDRSR returned an unexpected case number: "
                f"{record.identifiers.get('CASE_NUMBER')!r}."
            )
        if not record.sensitive_legal_data:
            raise AssertionError("Court decision is not marked sensitive_legal_data.")
        if record.metadata.get("person_identity_inference_prohibited") is not True:
            raise AssertionError("Person-identity inference guardrail is missing.")
        if record.metadata.get("legal_outcome_inference_prohibited") is not True:
            raise AssertionError("Legal-outcome inference guardrail is missing.")
        if record.metadata.get("legal_outcome") != "unknown":
            raise AssertionError("EDRSR provider must not infer legal outcome from raw decision metadata.")


def _assert_persistence(result) -> None:
    persisted = result.persistence
    if persisted.errors:
        raise AssertionError(f"Persistence reported errors: {persisted.errors!r}")
    if len(persisted.records) != len(result.search.records):
        raise AssertionError(
            "Not every court RegistryRecord produced an Evidence snapshot: "
            f"records={len(result.search.records)} persisted={len(persisted.records)}."
        )
    if persisted.entities_created != 0 or persisted.links_created != 0:
        raise AssertionError(
            "Court persistence must not automatically create/link identity Entities: "
            f"entities={persisted.entities_created}, links={persisted.links_created}."
        )
    for item in persisted.records:
        if item.entities:
            raise AssertionError("Court persistence attached an Entity unexpectedly.")
        if item.resolution_method != "no_identity_resolution":
            raise AssertionError(
                f"Unexpected court resolution method: {item.resolution_method!r}."
            )


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
        raise AssertionError(f"Second persistence pass created duplicates: {nonzero!r}.")
    if persisted.errors:
        raise AssertionError(f"Second pass reported errors: {persisted.errors!r}")


def main() -> int:
    args = _parse_args()
    court_case_number = str(args.case_number).strip()
    if not court_case_number:
        raise ValueError("--case-number must not be empty.")

    query = detect_registry_query(f"case:{court_case_number}")
    if query is None:
        raise RuntimeError("Failed to build CASE_NUMBER RegistryQuery.")

    session = create_session()
    container = ServiceContainer(session)
    try:
        case_id = _resolve_case_id(session, args.case_id)
        provider = container.registry_provider_registry.get("ua_edrsr")
        if provider is None:
            raise AssertionError("Desktop ServiceContainer did not register ua_edrsr.")
        if provider.__class__.__name__ != "RemoteRegistryProvider":
            raise AssertionError(
                "Desktop ua_edrsr must be RemoteRegistryProvider, not a local mirror provider."
            )

        print(f"investigation_case_id: {case_id}")
        print(f"court_case_number: {court_case_number}")
        print("desktop_provider: ua_edrsr / RemoteRegistryProvider")
        print("transaction: rollback-only")

        first = container.registry_intelligence_service.enrich(query, case_id=case_id)
        session.flush()
        _assert_search(first, court_case_number)
        _assert_persistence(first)

        print("first_pass: PASS")
        print(f"court_decisions: {len(first.search.records)}")
        print(f"sources_created: {first.persistence.sources_created}")
        print(f"evidences_created: {first.persistence.evidences_created}")
        print(f"entities_created: {first.persistence.entities_created}")
        print(f"links_created: {first.persistence.links_created}")
        print("identity_resolution: NOT ATTEMPTED")
        print("legal_outcome: NOT INFERRED")

        second = container.registry_intelligence_service.enrich(query, case_id=case_id)
        session.flush()
        _assert_search(second, court_case_number)
        _assert_second_pass_is_idempotent(second)
        print("second_pass_idempotency: PASS")
        print(
            "created_again: "
            f"sources={second.persistence.sources_created}; "
            f"evidences={second.persistence.evidences_created}; "
            f"entities={second.persistence.entities_created}; "
            f"links={second.persistence.links_created}"
        )

        print("M022.3C LIVE EDRSR PERSISTENCE PROBE: PASS")
        return 0
    finally:
        try:
            container.rollback()
        finally:
            container.close()


if __name__ == "__main__":
    raise SystemExit(main())

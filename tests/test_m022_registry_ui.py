from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.interface.desktop.workers.registry_search_worker import (
    RegistrySearchWorker,
    build_registry_ui_query,
)
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQueryKind,
    RegistryRecord,
)


def test_registry_ui_query_modes_map_to_explicit_safe_sources() -> None:
    edrpou = build_registry_ui_query("EDRPOU", "14359609")
    assert edrpou.domain is RegistryDomain.BUSINESS
    assert edrpou.kind is RegistryQueryKind.REGISTRATION_ID
    assert edrpou.country == "UA"
    assert edrpou.sources == ("ua_edr_business",)
    assert edrpou.entity_kind is RegistryEntityKind.COMPANY

    company = build_registry_ui_query("Company name", "ФЕРДАУС")
    assert company.kind is RegistryQueryKind.NAME
    assert company.sources == ("ua_edr_business",)
    assert company.entity_kind is RegistryEntityKind.COMPANY

    fop = build_registry_ui_query("FOP name", "Іванов Іван")
    assert fop.kind is RegistryQueryKind.PERSON_NAME
    assert fop.sources == ("ua_edr_business",)
    assert fop.entity_kind is RegistryEntityKind.SOLE_TRADER

    court = build_registry_ui_query("Court case number", "260/7098/24")
    assert court.domain is RegistryDomain.COURT
    assert court.kind is RegistryQueryKind.CASE_NUMBER
    assert court.sources == ("ua_edrsr",)
    assert court.entity_kind is RegistryEntityKind.COURT_CASE


def test_registry_ui_snapshot_preserves_candidate_and_legal_guardrails() -> None:
    candidate = RegistryRecord(
        provider="ua_edr_business",
        domain=RegistryDomain.BUSINESS,
        record_id="company:1",
        display_name="Candidate Company",
        entity_kind=RegistryEntityKind.COMPANY,
        metadata={"candidate_only": True, "identity_uncertainty": "name_only_match"},
    )
    candidate_snapshot = RegistrySearchWorker._snapshot_record(candidate)
    assert candidate_snapshot["candidateOnly"] is True
    assert candidate_snapshot["persistable"] is False

    court = RegistryRecord(
        provider="ua_edrsr",
        domain=RegistryDomain.COURT,
        record_id="decision:133056758",
        display_name="Ухвала · справа 260/7098/24",
        entity_kind=RegistryEntityKind.COURT_DECISION,
        sensitive_legal_data=True,
        identifiers={"CASE_NUMBER": "260/7098/24", "EDRSR_DOC_ID": "133056758"},
        metadata={
            "court_name": "Fixture Court",
            "case_number": "260/7098/24",
            "legal_outcome": "unknown",
            "legal_outcome_inference_prohibited": True,
            "person_identity_inference_prohibited": True,
        },
    )
    court_snapshot = RegistrySearchWorker._snapshot_record(court)
    assert court_snapshot["sensitiveLegalData"] is True
    assert court_snapshot["persistable"] is True
    assert court_snapshot["legalOutcome"] == "unknown"
    assert court_snapshot["personIdentityInferenceProhibited"] is True
    assert court_snapshot["legalOutcomeInferenceProhibited"] is True


def test_registry_ui_persistence_snapshot_never_needs_orm_after_transport() -> None:
    persistence = SimpleNamespace(
        sources_created=1,
        evidences_created=1,
        entities_created=0,
        links_created=0,
        skipped_records=0,
        errors=[],
        records=[
            SimpleNamespace(
                source=SimpleNamespace(id="source-id"),
                evidence=SimpleNamespace(id="evidence-id"),
                entities=[],
                resolution_method=None,
            )
        ],
    )
    snapshot = RegistrySearchWorker._snapshot_persistence(persistence)
    assert snapshot == {
        "attempted": True,
        "sourcesCreated": 1,
        "evidencesCreated": 1,
        "entitiesCreated": 0,
        "linksCreated": 0,
        "skippedRecords": 0,
        "errors": [],
        "records": [
            {
                "sourceId": "source-id",
                "evidenceId": "evidence-id",
                "entityIds": [],
                "resolutionMethod": "",
            }
        ],
    }


def test_registry_ui_bridge_and_qml_use_background_worker_and_dedicated_page() -> None:
    bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")
    worker = Path(
        "app/interface/desktop/workers/registry_search_worker.py"
    ).read_text(encoding="utf-8")
    main = Path(
        "app/interface/desktop/qml/Main.qml"
    ).read_text(encoding="utf-8")
    osint = Path(
        "app/interface/desktop/qml/pages/Osint.qml"
    ).read_text(encoding="utf-8")
    registry = Path(
        "app/interface/desktop/qml/pages/Registry.qml"
    ).read_text(encoding="utf-8")

    assert "RegistrySearchWorker(" in bridge
    assert "worker.moveToThread(thread)" in bridge
    assert "registry_intelligence_service" in worker
    assert "create_session()" in worker
    assert "ServiceContainer(session)" in worker
    assert 'case "registry": return "pages/Registry.qml"' in main
    assert "desktopBridge.openRegistry()" in osint
    assert 'model: ["EDRPOU", "Company name", "FOP name", "Court case number"]' in registry
    assert "desktopBridge.registrySearch(modeBox.currentText, value)" in registry
    assert "desktopBridge.registryPersistLast()" in registry
    assert "A match never implies identity, guilt or conviction." in registry

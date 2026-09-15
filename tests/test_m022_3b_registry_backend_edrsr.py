from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.registry_ua_edr import UaEdrSubject, UaEdrSyncState
from app.models.registry_ua_edrsr import UaEdrsrDecision, UaEdrsrSyncState
from app.registry_backend.api import create_registry_backend_app


def _factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    UaEdrSubject.__table__.create(engine)
    UaEdrSyncState.__table__.create(engine)
    UaEdrsrDecision.__table__.create(engine)
    UaEdrsrSyncState.__table__.create(engine)
    factory = sessionmaker(bind=engine)

    session = factory()
    session.add(
        UaEdrSyncState(
            source_code="ua_edr_business",
            active_generation="business-g1",
            status="ready",
            uo_record_count=1,
            fop_record_count=0,
        )
    )
    session.add(
        UaEdrsrSyncState(
            source_code="ua_edrsr",
            dataset_year=2026,
            active_generation="court-g1",
            status="ready",
            record_count=1,
        )
    )
    session.add(
        UaEdrsrDecision(
            dataset_year=2026,
            generation="court-g1",
            doc_id=195,
            cause_num="19/273",
            cause_num_normalized="19/273",
            court_code="5014",
            court_name="Court",
            judgment_code="5",
            judgment_name="Рішення",
            justice_kind="3",
            adjudication_date=datetime(2026, 1, 2),
            status=1,
            raw_reference="ua-edrsr:195",
        )
    )
    session.commit()
    session.close()
    return factory


def test_backend_reports_edrsr_readiness_and_serves_case_number_query():
    client = TestClient(create_registry_backend_app(session_factory=_factory()))
    health = client.get("/health/ready")
    assert health.status_code == 200
    edrsr = health.json()["providers"]["ua_edrsr"]
    assert edrsr["ready"] is True
    assert edrsr["ready_years"] == [2026]
    assert edrsr["decision_records"] == 1

    response = client.post(
        "/v1/providers/ua_edrsr/search",
        json={
            "domain": "court",
            "kind": "case_number",
            "value": "19/273",
            "country": "UA",
            "sources": ["ua_edrsr"],
            "entity_kind": "court_case",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "ua_edrsr"
    assert payload["records"][0]["identifiers"]["CASE_NUMBER"] == "19/273"
    assert payload["records"][0]["sensitive_legal_data"] is True
    assert payload["records"][0]["metadata"]["legal_outcome"] == "unknown"


def test_missing_edrsr_does_not_take_ready_business_provider_offline():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    UaEdrSubject.__table__.create(engine)
    UaEdrSyncState.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add(
        UaEdrSyncState(
            source_code="ua_edr_business",
            active_generation="g1",
            status="ready",
            uo_record_count=1,
            fop_record_count=0,
        )
    )
    session.commit()
    session.close()

    client = TestClient(create_registry_backend_app(session_factory=factory))
    health = client.get("/health/ready")
    assert health.status_code == 200
    assert health.json()["providers"]["ua_edr_business"]["ready"] is True
    assert health.json()["providers"]["ua_edrsr"]["ready"] is False

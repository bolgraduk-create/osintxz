from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.registry_ua_edr import UaEdrSubject, UaEdrSyncState
from app.registry_backend.api import create_registry_backend_app


def make_runtime():
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
    session.add(
        UaEdrSubject(
            generation="g1",
            subject_kind="company",
            record_id="101",
            name="TEST COMPANY",
            name_normalized="TEST COMPANY",
            registration_id="12345678",
            legal_form="ТОВ",
            status="registered",
            source_resource_id="uo-resource",
            raw_reference="ua-edr:company:101",
        )
    )
    session.commit()
    session.close()
    return factory


def test_registry_backend_health_and_authenticated_search():
    app = create_registry_backend_app(
        session_factory=make_runtime(),
        auth_token="secret",
    )
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["providers"]["ua_edr_business"]["ready"] is True

    unauthorized = client.post(
        "/v1/providers/ua_edr_business/search",
        json={
            "domain": "business",
            "kind": "registration_id",
            "value": "12345678",
            "country": "UA",
            "sources": ["ua_edr_business"],
            "entity_kind": "company",
        },
    )
    assert unauthorized.status_code == 401

    response = client.post(
        "/v1/providers/ua_edr_business/search",
        headers={"Authorization": "Bearer secret"},
        json={
            "domain": "business",
            "kind": "registration_id",
            "value": "12345678",
            "country": "UA",
            "sources": ["ua_edr_business"],
            "entity_kind": "company",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "ua_edr_business"
    assert payload["status"] == "success"
    assert payload["records"][0]["registration_id"] == "12345678"
    assert payload["records"][0]["display_name"] == "TEST COMPANY"
    assert payload["metadata"]["served_by"] == "registry_backend"

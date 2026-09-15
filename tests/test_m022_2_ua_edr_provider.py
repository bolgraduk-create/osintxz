from types import SimpleNamespace

from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
    RegistryResultStatus,
)
from app.registry_intelligence.providers.ukraine_edr import UkraineEdrRegistryProvider
from app.registry_intelligence.query_detection import detect_registry_query


class FakeRepository:
    def __init__(self, rows=(), generation="g1"):
        self.rows = list(rows)
        self.generation = generation

    def active_generation(self):
        return self.generation

    def search_registration_id(self, value, *, limit=20):
        return [row for row in self.rows if row.registration_id == value][:limit]

    def search_name(self, value, *, subject_kind=None, limit=20):
        rows = self.rows
        if subject_kind:
            rows = [row for row in rows if row.subject_kind == subject_kind]
        return rows[:limit]


def row(**overrides):
    values = dict(
        subject_kind="company",
        record_id="101",
        name="TEST COMPANY LLC",
        short_name="TEST LLC",
        registration_id="12345678",
        legal_form="ТОВ",
        status="registered",
        registration_info="2024-01-01",
        termination_info=None,
        estate_manager=None,
        family_farm=None,
        metadata_json="{}",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_exact_edrpou_is_verified_company_record():
    provider = UkraineEdrRegistryProvider(repository=FakeRepository([row()]))
    query = detect_registry_query("edrpou:12345678")
    result = provider.search(query)
    assert result.status is RegistryResultStatus.SUCCESS
    assert len(result.records) == 1
    record = result.records[0]
    assert record.entity_kind is RegistryEntityKind.COMPANY
    assert record.registration_id == "12345678"
    assert not record.metadata.get("candidate_only")
    assert record.source_url.startswith("https://data.gov.ua/")


def test_fop_name_is_candidate_only_and_never_claimed_as_same_person():
    provider = UkraineEdrRegistryProvider(
        repository=FakeRepository(
            [row(subject_kind="sole_trader", registration_id=None, name="ІВАНЕНКО ІВАН ІВАНОВИЧ")]
        )
    )
    query = detect_registry_query("fop:ІВАНЕНКО ІВАН ІВАНОВИЧ")
    result = provider.search(query)
    assert result.records[0].entity_kind is RegistryEntityKind.SOLE_TRADER
    assert result.records[0].metadata["candidate_only"] is True
    assert result.records[0].metadata["identity_uncertainty"] == "name_only_match"


def test_backend_provider_is_visible_but_not_fake_success_before_server_sync():
    provider = UkraineEdrRegistryProvider(repository=FakeRepository([], generation=None))
    result = provider.search(
        RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.REGISTRATION_ID,
            "12345678",
            country="UA",
        )
    )
    assert result.status is RegistryResultStatus.NOT_SUPPORTED
    assert result.metadata["action_required"] == "backend_sync"

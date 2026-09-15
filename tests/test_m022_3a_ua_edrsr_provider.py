from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
    RegistryResultStatus,
)
from app.registry_intelligence.providers.ukraine_edrsr import UkraineEdrsrRegistryProvider


class _Repository:
    def ready_years(self):
        return (2025, 2026)

    def search_case_number(self, value, *, limit=20, dataset_year=None):
        assert value == "19/273"
        return [
            SimpleNamespace(
                dataset_year=2006,
                doc_id=195,
                court_code="5014",
                court_name="Господарський суд Луганської області",
                instance_name="Перша інстанція",
                region_name="Луганська область",
                judgment_code="5",
                judgment_name="Рішення",
                justice_kind="3",
                justice_kind_name="Господарське",
                category_code="4047",
                category_name="Інший майновий спір",
                cause_num="19/273",
                adjudication_date=datetime(2006, 6, 1),
                receipt_date=datetime(2006, 6, 5),
                judge="Бойченко К.І.",
                doc_url="https://example.test/195",
                status=1,
                date_publ=datetime(2007, 8, 22),
                raw_reference="ua-edrsr:195",
            )
        ]


def test_exact_case_number_returns_sensitive_court_decision_record():
    provider = UkraineEdrsrRegistryProvider(repository=_Repository())
    result = provider.search(
        RegistryQuery(
            domain=RegistryDomain.COURT,
            kind=RegistryQueryKind.CASE_NUMBER,
            value="19/273",
            country="UA",
            entity_kind=RegistryEntityKind.COURT_CASE,
        )
    )
    assert result.status is RegistryResultStatus.SUCCESS
    assert len(result.records) == 1
    record = result.records[0]
    assert record.entity_kind is RegistryEntityKind.COURT_DECISION
    assert record.identifiers["CASE_NUMBER"] == "19/273"
    assert record.identifiers["EDRSR_DOC_ID"] == "195"
    assert record.sensitive_legal_data is True
    assert record.metadata["legal_outcome"] == "unknown"
    assert record.metadata["legal_outcome_inference_prohibited"] is True
    assert record.metadata["person_identity_inference_prohibited"] is True


def test_person_name_query_is_not_supported():
    provider = UkraineEdrsrRegistryProvider(repository=_Repository())
    result = provider.search(
        RegistryQuery(
            domain=RegistryDomain.COURT,
            kind=RegistryQueryKind.PERSON_NAME,
            value="Іван Петренко",
            country="UA",
        )
    )
    assert result.status is RegistryResultStatus.NOT_SUPPORTED

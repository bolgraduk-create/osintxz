from app.registry_intelligence.contracts import RegistryQueryKind
from app.registry_intelligence.countries.ukraine import (
    UA_EDRSR_PROVIDER_INFO,
    ukraine_source,
)


def test_edrsr_contract_is_case_number_only_and_sensitive():
    descriptor = ukraine_source("ua_edrsr")
    assert descriptor is not None
    assert descriptor.default_enabled is True
    assert descriptor.sensitive_legal_data is True
    assert descriptor.query_kinds == frozenset({RegistryQueryKind.CASE_NUMBER})

    assert UA_EDRSR_PROVIDER_INFO.query_kinds == frozenset({RegistryQueryKind.CASE_NUMBER})
    assert UA_EDRSR_PROVIDER_INFO.sensitive_legal_data is True
    assert UA_EDRSR_PROVIDER_INFO.trust_score == 0.96

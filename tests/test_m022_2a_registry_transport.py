from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryProviderResult,
    RegistryQuery,
    RegistryQueryKind,
    RegistryRecord,
    RegistryResultStatus,
    RegistrySourceType,
)
from app.registry_intelligence.transport import (
    registry_provider_result_from_wire,
    registry_provider_result_to_wire,
    registry_query_from_wire,
    registry_query_to_wire,
)


def test_registry_query_wire_roundtrip_preserves_routing_semantics():
    query = RegistryQuery(
        RegistryDomain.BUSINESS,
        RegistryQueryKind.REGISTRATION_ID,
        "12345678",
        country="UA",
        limit=7,
        timeout=19,
        sources=("ua_edr_business",),
        entity_kind=RegistryEntityKind.COMPANY,
    )
    restored = registry_query_from_wire(registry_query_to_wire(query))
    assert restored == query


def test_registry_provider_result_wire_roundtrip_preserves_provenance():
    result = RegistryProviderResult(
        provider="ua_edr_business",
        status=RegistryResultStatus.SUCCESS,
        records=[
            RegistryRecord(
                provider="ua_edr_business",
                domain=RegistryDomain.BUSINESS,
                record_id="company:101",
                display_name="TEST COMPANY",
                country="UA",
                registration_id="12345678",
                source_url="https://data.gov.ua/dataset/example",
                identifiers={"EDRPOU": "12345678"},
                metadata={"subject_kind": "company"},
                entity_kind=RegistryEntityKind.COMPANY,
                source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
                trust_score=0.96,
                raw_reference="ua-edr:company:101",
            )
        ],
        metadata={"mirror_generation": "g1"},
    )

    restored = registry_provider_result_from_wire(
        registry_provider_result_to_wire(result)
    )
    assert restored.status is RegistryResultStatus.SUCCESS
    assert restored.records[0].registration_id == "12345678"
    assert restored.records[0].source_type is RegistrySourceType.OFFICIAL_OPEN_DATA
    assert restored.records[0].raw_reference == "ua-edr:company:101"

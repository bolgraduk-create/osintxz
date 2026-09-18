from __future__ import annotations

from dataclasses import dataclass

from app.application.registry_intelligence_service import (
    RegistryIntelligenceService,
)
from app.application.registry_persistence_service import (
    RegistryPersistenceService,
)
from app.intelligence_sources.catalog import IntelligenceSourceCatalog
from app.intelligence_sources.contracts import (
    DataSensitivity,
    IntelligenceAccessMode,
    IntelligenceCost,
    IntelligenceDeliveryMode,
    IntelligenceSourceCategory,
    IntelligenceSourceDescriptor,
    IntelligenceSourceOrigin,
    IntelligenceTransport,
)
from app.intelligence_sources.policy import (
    IntelligenceDataPolicy,
    IntelligenceDataSanitizer,
)
from app.registry_intelligence.contracts import (
    RegistryAccessMode,
    RegistryDomain,
    RegistryEntityKind,
    RegistryProviderInfo,
    RegistryProviderResult,
    RegistryQuery,
    RegistryQueryKind,
    RegistryRecord,
    RegistryResultStatus,
    RegistrySourceType,
)
from app.registry_intelligence.provider import RegistryProvider
from app.registry_intelligence.registry import RegistryProviderRegistry


def _source(
    code: str,
    *,
    access: IntelligenceAccessMode = IntelligenceAccessMode.NO_AUTH,
    default_enabled: bool = True,
    cost: IntelligenceCost = IntelligenceCost.FREE,
    delivery: IntelligenceDeliveryMode = IntelligenceDeliveryMode.REMOTE_QUERY,
    remote: bool = True,
    bulk: bool = False,
) -> IntelligenceSourceDescriptor:
    return IntelligenceSourceDescriptor(
        code=code,
        display_name=code,
        categories=frozenset(
            {IntelligenceSourceCategory.BREACH_INTELLIGENCE}
        ),
        capabilities=frozenset({"email", "breach_lookup"}),
        transport=IntelligenceTransport.REST,
        access_mode=access,
        cost=cost,
        delivery_mode=delivery,
        origin=IntelligenceSourceOrigin.BREACH_PROVIDER,
        global_scope=True,
        default_enabled=default_enabled,
        remote_query_supported=remote,
        bulk_download_required=bulk,
        default_sensitivity=DataSensitivity.BREACH_METADATA,
    )


def test_public_remote_source_is_automatic():
    source = _source("public")
    assert source.automatic_eligible() is True


def test_free_api_key_source_requires_configured_credentials():
    source = _source(
        "credentialed",
        access=IntelligenceAccessMode.FREE_API_KEY,
    )
    assert source.automatic_eligible() is False
    assert source.automatic_eligible(
        credentials_available=True
    ) is True


def test_verified_scope_requires_credentials_and_scope():
    source = _source(
        "verified",
        access=IntelligenceAccessMode.VERIFIED_SCOPE,
    )
    assert source.automatic_eligible(
        credentials_available=True
    ) is False
    assert source.automatic_eligible(
        credentials_available=True,
        verified_scope=True,
    ) is True


def test_paid_source_never_automatic():
    source = _source(
        "paid",
        access=IntelligenceAccessMode.PAID,
        cost=IntelligenceCost.PAID,
    )
    assert source.automatic_eligible(
        credentials_available=True
    ) is False


def test_bulk_only_source_cannot_claim_remote_query():
    try:
        _source(
            "bulk",
            delivery=IntelligenceDeliveryMode.BULK_ONLY,
            remote=True,
        )
    except ValueError as exc:
        assert "BULK_ONLY" in str(exc)
    else:
        raise AssertionError("Expected source validation to fail.")


def test_catalog_filters_remote_sources_and_capabilities():
    catalog = IntelligenceSourceCatalog()
    catalog.register(_source("a"))
    catalog.register(
        IntelligenceSourceDescriptor(
            code="registry",
            display_name="Registry",
            categories=frozenset(
                {IntelligenceSourceCategory.REGISTRY}
            ),
            capabilities=frozenset({"registration_id"}),
            transport=IntelligenceTransport.REST,
            access_mode=IntelligenceAccessMode.NO_AUTH,
            global_scope=True,
            default_enabled=True,
        )
    )

    breach = catalog.find(
        category=IntelligenceSourceCategory.BREACH_INTELLIGENCE,
        capability="email",
    )
    assert tuple(item.code for item in breach) == ("a",)


def test_policy_for_secret_material_blocks_persistence_and_display():
    decision = IntelligenceDataPolicy().decision_for(
        DataSensitivity.SECRET_MATERIAL
    )
    assert decision.ingest_allowed is True
    assert decision.persist_allowed is False
    assert decision.analyze_allowed is False
    assert decision.display_allowed is False
    assert decision.export_allowed is False
    assert decision.redact_value is True


def test_restricted_requires_explicit_authorization():
    policy = IntelligenceDataPolicy()

    blocked = policy.decision_for(DataSensitivity.RESTRICTED)
    assert blocked.persist_allowed is False

    authorized = policy.decision_for(
        DataSensitivity.RESTRICTED,
        restricted_authorized=True,
    )
    assert authorized.persist_allowed is True
    assert authorized.display_allowed is True
    assert authorized.export_allowed is False


def test_sanitizer_redacts_nested_secrets_but_keeps_exposure_flags():
    payload = {
        "email": "person@example.com",
        "password_exposed": True,
        "password": "summer2026!",
        "nested": {
            "access_token": "abc123",
            "session_cookie": "sid=secret",
            "private_key": "-----BEGIN PRIVATE KEY-----",
            "token_exposed": True,
        },
    }

    result = IntelligenceDataSanitizer().sanitize(payload)

    assert result.value["email"] == "person@example.com"
    assert result.value["password_exposed"] is True
    assert result.value["password"] == "[REDACTED]"
    assert result.value["nested"]["access_token"] == "[REDACTED]"
    assert result.value["nested"]["session_cookie"] == "[REDACTED]"
    assert result.value["nested"]["private_key"] == "[REDACTED]"
    assert result.value["nested"]["token_exposed"] is True
    assert result.redacted_count == 4


@dataclass
class _LeakLike:
    email: str
    password: str
    password_exposed: bool


def test_sanitizer_handles_dataclasses():
    source = _LeakLike(
        email="a@example.com",
        password="secret",
        password_exposed=True,
    )
    result = IntelligenceDataSanitizer().sanitize(source)
    assert result.value.email == "a@example.com"
    assert result.value.password == "[REDACTED]"
    assert result.value.password_exposed is True


class _SecretMetadataProvider(RegistryProvider):
    @property
    def info(self) -> RegistryProviderInfo:
        return RegistryProviderInfo(
            name="secret-metadata-test",
            display_name="Secret Metadata Test",
            domains=frozenset({RegistryDomain.BUSINESS}),
            query_kinds=frozenset({RegistryQueryKind.EMAIL}),
            global_scope=True,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
            source_type=RegistrySourceType.AGGREGATOR,
            trust_score=0.5,
        )

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        return RegistryProviderResult(
            provider=self.info.name,
            status=RegistryResultStatus.SUCCESS,
            records=[
                RegistryRecord(
                    provider=self.info.name,
                    domain=RegistryDomain.BUSINESS,
                    record_id="record-1",
                    display_name="Breach metadata example",
                    identifiers={"EMAIL": query.value},
                    metadata={
                        "email": query.value,
                        "password_exposed": True,
                        "password": "raw-password",
                        "access_token": "raw-token",
                    },
                    entity_kind=RegistryEntityKind.LEGAL_ENTITY,
                    source_type=RegistrySourceType.AGGREGATOR,
                    trust_score=0.5,
                )
            ],
        )


def test_registry_search_sanitizes_provider_record_before_return():
    registry = RegistryProviderRegistry()
    registry.register(_SecretMetadataProvider())
    service = RegistryIntelligenceService(registry=registry)

    result = service.search(
        RegistryQuery(
            domain=RegistryDomain.BUSINESS,
            kind=RegistryQueryKind.EMAIL,
            value="person@example.com",
        )
    )

    metadata = result.records[0].metadata
    assert metadata["email"] == "person@example.com"
    assert metadata["password_exposed"] is True
    assert metadata["password"] == "[REDACTED]"
    assert metadata["access_token"] == "[REDACTED]"

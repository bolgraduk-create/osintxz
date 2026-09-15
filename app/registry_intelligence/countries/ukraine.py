"""M022 Ukraine Registry Source Matrix.

This module is declarative only. A listed source does not become executable until
its provider implementation is registered in RegistryProviderRegistry.
"""
from app.registry_intelligence.contracts import (
    RegistryAccessMode,
    RegistryDomain,
    RegistryProviderInfo,
    RegistryQueryKind,
    RegistrySourceType,
)
from app.registry_intelligence.source_catalog import RegistrySourceDescriptor


UKRAINE_REGISTRY_SOURCES: tuple[RegistrySourceDescriptor, ...] = (
    RegistrySourceDescriptor(
        code="ua_edr_business",
        display_name="Ukraine EDR — legal entities and sole traders",
        country="UA",
        domains=frozenset({RegistryDomain.BUSINESS}),
        query_kinds=frozenset({
            RegistryQueryKind.NAME,
            RegistryQueryKind.PERSON_NAME,
            RegistryQueryKind.REGISTRATION_ID,
        }),
        access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
        source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
        trust_score=0.96,
        public_data_only=True,
        requires_credentials=False,
        default_enabled=True,
        implementation_status="implemented_remote_backend",
        notes=(
            "Official weekly UO/FOP open-data mirror is synchronized centrally by "
            "the OSINTXZ Registry Backend. End-user desktops query the backend and "
            "do not download the national dataset."
        ),
    ),
    RegistrySourceDescriptor(
        code="ua_debtors",
        display_name="Ukraine Unified Register of Debtors",
        country="UA",
        domains=frozenset({RegistryDomain.ENFORCEMENT, RegistryDomain.LEGAL}),
        query_kinds=frozenset({RegistryQueryKind.PERSON_NAME, RegistryQueryKind.TAX_ID}),
        access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
        source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
        trust_score=0.94,
        public_data_only=True,
        requires_credentials=False,
        sensitive_legal_data=True,
        notes="A registry hit is an enforcement/debtor record, not a criminal-conviction claim.",
    ),
    RegistrySourceDescriptor(
        code="ua_court_case_status",
        display_name="Ukraine court case status",
        country="UA",
        domains=frozenset({RegistryDomain.COURT}),
        query_kinds=frozenset({RegistryQueryKind.CASE_NUMBER, RegistryQueryKind.PERSON_NAME}),
        access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
        source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
        trust_score=0.95,
        public_data_only=True,
        requires_credentials=False,
        sensitive_legal_data=True,
        notes="Participation in a case must never be interpreted as guilt or conviction.",
    ),
    RegistrySourceDescriptor(
        code="ua_court_hearings",
        display_name="Ukraine scheduled court hearings",
        country="UA",
        domains=frozenset({RegistryDomain.COURT}),
        query_kinds=frozenset({RegistryQueryKind.CASE_NUMBER, RegistryQueryKind.PERSON_NAME}),
        access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
        source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
        trust_score=0.94,
        public_data_only=True,
        requires_credentials=False,
        sensitive_legal_data=True,
    ),
    RegistrySourceDescriptor(
        code="ua_edrsr",
        display_name="Ukraine Unified State Register of Court Decisions",
        country="UA",
        domains=frozenset({RegistryDomain.COURT, RegistryDomain.LEGAL}),
        query_kinds=frozenset({RegistryQueryKind.CASE_NUMBER}),
        access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
        source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
        trust_score=0.96,
        public_data_only=True,
        requires_credentials=False,
        default_enabled=True,
        sensitive_legal_data=True,
        implementation_status="implemented_remote_backend",
        notes=(
            "Central Registry Backend source with yearly server-side ingestion. "
            "Initial automated provider is exact case-number only. Person-name "
            "matching is deliberately disabled: a "
            "court decision or party mention must never be treated as identity, guilt "
            "or conviction. Legal outcome is modeled explicitly in a later step."
        ),
    ),
    RegistrySourceDescriptor(
        code="ua_nazk_declarations",
        display_name="NACP public officials declarations",
        country="UA",
        domains=frozenset({RegistryDomain.PUBLIC_OFFICIAL}),
        query_kinds=frozenset({RegistryQueryKind.PERSON_NAME}),
        access_mode=RegistryAccessMode.API,
        source_type=RegistrySourceType.OFFICIAL_API,
        trust_score=0.96,
        public_data_only=True,
        requires_credentials=False,
    ),
    RegistrySourceDescriptor(
        code="ua_wanted_persons",
        display_name="Ukraine National Police wanted persons",
        country="UA",
        domains=frozenset({RegistryDomain.WANTED, RegistryDomain.LEGAL}),
        query_kinds=frozenset({RegistryQueryKind.PERSON_NAME}),
        access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
        source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
        trust_score=0.96,
        public_data_only=True,
        requires_credentials=False,
        sensitive_legal_data=True,
        notes="Identity uncertainty must be preserved; name-only matches are never treated as confirmed identity.",
    ),
    RegistrySourceDescriptor(
        code="ua_corruption_register",
        display_name="NACP corruption-offence register",
        country="UA",
        domains=frozenset({RegistryDomain.LEGAL}),
        query_kinds=frozenset({RegistryQueryKind.PERSON_NAME, RegistryQueryKind.REGISTRATION_ID}),
        access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
        source_type=RegistrySourceType.OFFICIAL_PORTAL,
        trust_score=0.95,
        public_data_only=True,
        requires_credentials=False,
        sensitive_legal_data=True,
    ),
    RegistrySourceDescriptor(
        code="ua_asvp",
        display_name="Ukraine automated enforcement proceedings system",
        country="UA",
        domains=frozenset({RegistryDomain.ENFORCEMENT}),
        query_kinds=frozenset({RegistryQueryKind.PERSON_NAME, RegistryQueryKind.TAX_ID}),
        access_mode=RegistryAccessMode.API,
        source_type=RegistrySourceType.CONTRACT_API,
        trust_score=0.96,
        public_data_only=False,
        requires_credentials=True,
        sensitive_legal_data=True,
        notes="Contract/authenticated source. Never auto-run without configured credentials and authorization.",
    ),
    RegistrySourceDescriptor(
        code="ua_property_rights",
        display_name="Ukraine State Register of Rights to Immovable Property",
        country="UA",
        domains=frozenset({RegistryDomain.PROPERTY}),
        query_kinds=frozenset({RegistryQueryKind.PERSON_NAME, RegistryQueryKind.REGISTRATION_ID, RegistryQueryKind.ADDRESS}),
        access_mode=RegistryAccessMode.API,
        source_type=RegistrySourceType.CONTRACT_API,
        trust_score=0.97,
        public_data_only=False,
        requires_credentials=True,
        notes="Paid/authorized source. Not eligible for automatic public execution.",
    ),
    RegistrySourceDescriptor(
        code="ua_movable_encumbrances",
        display_name="Ukraine Register of Encumbrances of Movable Property",
        country="UA",
        domains=frozenset({RegistryDomain.PROPERTY}),
        query_kinds=frozenset({RegistryQueryKind.PERSON_NAME, RegistryQueryKind.REGISTRATION_ID}),
        access_mode=RegistryAccessMode.API,
        source_type=RegistrySourceType.CONTRACT_API,
        trust_score=0.96,
        public_data_only=False,
        requires_credentials=True,
        notes="Paid/authorized source. Not eligible for automatic public execution.",
    ),
)


def ukraine_source(code: str) -> RegistrySourceDescriptor | None:
    normalized = (code or "").strip().casefold()
    for source in UKRAINE_REGISTRY_SOURCES:
        if source.code.casefold() == normalized:
            return source
    return None


UA_EDR_PROVIDER_INFO = RegistryProviderInfo(
    name="ua_edr_business",
    display_name="Ukraine EDR — legal entities and sole traders",
    domains=frozenset({RegistryDomain.BUSINESS}),
    query_kinds=frozenset({
        RegistryQueryKind.NAME,
        RegistryQueryKind.PERSON_NAME,
        RegistryQueryKind.REGISTRATION_ID,
    }),
    countries=frozenset({"UA"}),
    global_scope=False,
    public_data_only=True,
    requires_credentials=False,
    default_enabled=True,
    priority=20,
    access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
    source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
    trust_score=0.96,
)


UA_EDRSR_PROVIDER_INFO = RegistryProviderInfo(
    name="ua_edrsr",
    display_name="Ukraine Unified State Register of Court Decisions",
    domains=frozenset({RegistryDomain.COURT, RegistryDomain.LEGAL}),
    query_kinds=frozenset({RegistryQueryKind.CASE_NUMBER}),
    countries=frozenset({"UA"}),
    global_scope=False,
    public_data_only=True,
    requires_credentials=False,
    default_enabled=True,
    priority=30,
    access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
    source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
    trust_score=0.96,
    sensitive_legal_data=True,
)

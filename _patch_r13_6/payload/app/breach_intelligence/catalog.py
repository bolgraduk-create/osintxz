from __future__ import annotations

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


def register_hibp_sources(
    catalog: IntelligenceSourceCatalog,
) -> None:
    """
    Register HIBP capabilities in the Federation catalog.

    Account lookup is subscription-backed and therefore is not automatic by
    default. Pwned Passwords is free, remote and safe for automatic use.
    """

    sources = (
        IntelligenceSourceDescriptor(
            code="hibp_breached_account",
            display_name="Have I Been Pwned — Breached Account",
            categories=frozenset(
                {IntelligenceSourceCategory.BREACH_INTELLIGENCE}
            ),
            capabilities=frozenset({"email", "breach_lookup"}),
            transport=IntelligenceTransport.REST,
            access_mode=IntelligenceAccessMode.CONTRACT,
            cost=IntelligenceCost.MIXED,
            delivery_mode=IntelligenceDeliveryMode.REMOTE_QUERY,
            origin=IntelligenceSourceOrigin.BREACH_PROVIDER,
            global_scope=True,
            requires_credentials=True,
            default_enabled=False,
            remote_query_supported=True,
            default_sensitivity=DataSensitivity.BREACH_METADATA,
            raw_secret_storage_allowed=False,
            redistribution_allowed=False,
            documentation_url="https://haveibeenpwned.com/API/v3",
            terms_url="https://haveibeenpwned.com/TermsOfUse",
            notes=(
                "Email-address lookup requires an HIBP subscription key. "
                "Returned breach metadata is subject to HIBP terms."
            ),
        ),
        IntelligenceSourceDescriptor(
            code="hibp_pwned_passwords",
            display_name="Have I Been Pwned — Pwned Passwords",
            categories=frozenset(
                {IntelligenceSourceCategory.BREACH_INTELLIGENCE}
            ),
            capabilities=frozenset({"password_exposure"}),
            transport=IntelligenceTransport.REST,
            access_mode=IntelligenceAccessMode.NO_AUTH,
            cost=IntelligenceCost.FREE,
            delivery_mode=IntelligenceDeliveryMode.REMOTE_QUERY,
            origin=IntelligenceSourceOrigin.BREACH_PROVIDER,
            global_scope=True,
            requires_credentials=False,
            default_enabled=True,
            remote_query_supported=True,
            default_sensitivity=DataSensitivity.BREACH_METADATA,
            raw_secret_storage_allowed=False,
            redistribution_allowed=False,
            documentation_url="https://haveibeenpwned.com/API/v3",
            terms_url="https://haveibeenpwned.com/TermsOfUse",
            notes=(
                "Uses k-anonymity range lookup. The plaintext password and "
                "complete SHA-1 digest are never stored in a result."
            ),
        ),
    )

    for source in sources:
        existing = catalog.get(source.code)
        if existing is None:
            catalog.register(source)
        else:
            catalog.register(source, replace=True)

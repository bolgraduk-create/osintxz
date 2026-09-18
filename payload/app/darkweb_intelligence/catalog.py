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


def register_darkweb_sources(catalog: IntelligenceSourceCatalog) -> None:
    source = IntelligenceSourceDescriptor(
        code="tor_public_onion_fetch",
        display_name="Tor Public Onion Fetch",
        categories=frozenset({IntelligenceSourceCategory.DARK_WEB}),
        capabilities=frozenset(
            {
                "onion_url",
                "email",
                "domain",
                "username",
                "crypto_address",
                "public_page_observation",
            }
        ),
        transport=IntelligenceTransport.TOR_HTTP,
        access_mode=IntelligenceAccessMode.NO_AUTH,
        cost=IntelligenceCost.FREE,
        delivery_mode=IntelligenceDeliveryMode.REMOTE_QUERY,
        origin=IntelligenceSourceOrigin.DARKWEB_PUBLICATION,
        global_scope=True,
        requires_credentials=False,
        default_enabled=False,
        remote_query_supported=True,
        default_sensitivity=DataSensitivity.DARKWEB_PUBLIC,
        raw_secret_storage_allowed=False,
        redistribution_allowed=False,
        documentation_url=(
            "https://support.torproject.org/tor-browser/features/onion-services/"
        ),
        notes=(
            "Explicit public v3 .onion fetch only. No authentication bypass, "
            "redirect following, binary download, marketplace actions or direct fallback."
        ),
    )
    catalog.register(source, replace=catalog.get(source.code) is not None)

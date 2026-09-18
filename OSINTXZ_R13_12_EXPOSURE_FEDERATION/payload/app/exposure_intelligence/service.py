from __future__ import annotations

from app.exposure_intelligence.contracts import ExposureSearchResult, ExposureSummary
from app.intelligence_sources.adapters.contracts import RemoteSourceQuery
from app.intelligence_sources.adapters.service import RemoteSourceAdapterService


class ExposureFederationService:
    """Explicit exposure-intelligence routing over the generic adapter layer.

    Contract/subscription-backed providers are never invoked accidentally by a
    generic federation call. This service opts into the appropriate exposure
    providers for the requested target type.
    """

    _SOURCES: dict[str, tuple[str, ...]] = {
        "email": ("hibp_breached_account", "intelligencex_search"),
        "breach_lookup": ("hibp_breached_account", "intelligencex_search"),
        "domain": ("intelligencex_search",),
        "url": ("intelligencex_search",),
        "ip": ("intelligencex_search",),
        "phone": ("intelligencex_search",),
        "crypto_address": ("intelligencex_search",),
        "darkweb_index": ("intelligencex_search",),
        "onion_url": ("tor_public_onion_fetch",),
        "public_page_observation": ("tor_public_onion_fetch",),
    }

    def __init__(self, *, remote_service: RemoteSourceAdapterService) -> None:
        self.remote_service = remote_service

    def search(
        self,
        *,
        capability: str,
        value: str,
        limit: int = 20,
        timeout: int = 30,
    ) -> ExposureSearchResult:
        capability = (capability or "").strip().casefold()
        sources = self._SOURCES.get(capability)
        if not sources:
            raise ValueError(f"Unsupported exposure capability: {capability or '<empty>'}.")

        query = RemoteSourceQuery(
            capability=capability,
            value=value,
            limit=limit,
            timeout=timeout,
            sources=sources,
        )
        result = self.remote_service.search(query)
        return ExposureSearchResult(
            capability=capability,
            value=query.value,
            federated_result=result,
            summary=self._summarize(result),
        )

    def search_email(self, email: str, *, limit: int = 20, timeout: int = 30) -> ExposureSearchResult:
        return self.search(capability="email", value=email, limit=limit, timeout=timeout)

    def search_domain(self, domain: str, *, limit: int = 20, timeout: int = 30) -> ExposureSearchResult:
        return self.search(capability="domain", value=domain, limit=limit, timeout=timeout)

    def search_url(self, url: str, *, limit: int = 20, timeout: int = 30) -> ExposureSearchResult:
        return self.search(capability="url", value=url, limit=limit, timeout=timeout)

    def search_ip(self, ip: str, *, limit: int = 20, timeout: int = 30) -> ExposureSearchResult:
        return self.search(capability="ip", value=ip, limit=limit, timeout=timeout)

    def search_phone(self, phone: str, *, limit: int = 20, timeout: int = 30) -> ExposureSearchResult:
        return self.search(capability="phone", value=phone, limit=limit, timeout=timeout)

    def search_crypto_address(self, address: str, *, limit: int = 20, timeout: int = 30) -> ExposureSearchResult:
        return self.search(capability="crypto_address", value=address, limit=limit, timeout=timeout)

    def observe_onion(self, url: str, *, timeout: int = 30) -> ExposureSearchResult:
        return self.search(capability="onion_url", value=url, limit=1, timeout=timeout)

    @staticmethod
    def _summarize(result) -> ExposureSummary:
        summary = ExposureSummary(total_records=len(result.records))
        for provider in result.provider_results:
            summary.provider_statuses[provider.source] = provider.status

        for record in result.records:
            attrs = record.attributes or {}
            if record.record_type == "breach":
                summary.breach_records += 1
            if record.record_type in {"darkweb_public_observation", "darkweb_index_hit"}:
                summary.darkweb_records += 1
            if record.record_type in {"intelx_index_hit", "darkweb_index_hit"}:
                summary.indexed_leak_records += 1
            if attrs.get("password_exposed") is True:
                summary.password_exposed = True
            if attrs.get("secret_material_present") is True:
                summary.secret_material_present = True
            # Raw secret material is forbidden at both the adapter and sanitizer boundary.
            if attrs.get("raw_secret_values_stored") is True:
                summary.raw_secret_values_stored = True

        return summary

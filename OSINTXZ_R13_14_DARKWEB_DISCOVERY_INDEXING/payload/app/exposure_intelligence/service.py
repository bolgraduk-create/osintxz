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
        "email": ("hibp_breached_account", "hibp_pastes", "intelligencex_search"),
        "breach_lookup": ("hibp_breached_account", "hibp_pastes", "intelligencex_search"),
        "paste_exposure": ("hibp_pastes",),
        "verified_domain_breach": ("hibp_verified_domain",),
        "domain_exposure": ("hibp_verified_domain",),
        "stealer_log_email": ("hibp_stealer_logs_email",),
        "stealer_log_email_domain": ("hibp_stealer_logs_email_domain",),
        "stealer_log_website_domain": ("hibp_stealer_logs_website_domain",),
        "repository_secret_exposure": ("github_secret_scanning",),
        "domain": ("intelligencex_search",),
        "url": ("intelligencex_search",),
        "ip": ("intelligencex_search",),
        "phone": ("intelligencex_search",),
        "crypto_address": ("intelligencex_search",),
        "darkweb_index": ("intelligencex_search",),
        "onion_url": ("tor_public_onion_fetch",),
        "public_page_observation": ("tor_public_onion_fetch",),
        "darkweb_discovery": ("tor_onion_discovery",),
        "onion_discovery": ("tor_onion_discovery",),
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
        verified_scope: bool = False,
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
            verified_scope=verified_scope,
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

    def discover_onion(self, seed_url: str, *, limit: int = 25, timeout: int = 30) -> ExposureSearchResult:
        return self.search(capability="darkweb_discovery", value=seed_url, limit=limit, timeout=timeout)

    def search_pastes(self, email: str, *, limit: int = 20, timeout: int = 30) -> ExposureSearchResult:
        return self.search(capability="paste_exposure", value=email, limit=limit, timeout=timeout)

    def search_verified_domain(self, domain: str, *, verified_scope: bool = False, limit: int = 100, timeout: int = 30) -> ExposureSearchResult:
        if not verified_scope:
            raise ValueError("verified_scope=True is required for verified-domain exposure search.")
        return self.search(capability="verified_domain_breach", value=domain, limit=limit, timeout=timeout, verified_scope=True)

    def search_stealer_logs_email(self, email: str, *, verified_scope: bool = False, limit: int = 100, timeout: int = 30) -> ExposureSearchResult:
        if not verified_scope:
            raise ValueError("verified_scope=True is required for stealer-log email search.")
        return self.search(capability="stealer_log_email", value=email, limit=limit, timeout=timeout, verified_scope=True)

    def search_stealer_logs_email_domain(self, domain: str, *, verified_scope: bool = False, limit: int = 100, timeout: int = 30) -> ExposureSearchResult:
        if not verified_scope:
            raise ValueError("verified_scope=True is required for stealer-log email-domain search.")
        return self.search(capability="stealer_log_email_domain", value=domain, limit=limit, timeout=timeout, verified_scope=True)

    def search_stealer_logs_website_domain(self, domain: str, *, verified_scope: bool = False, limit: int = 100, timeout: int = 30) -> ExposureSearchResult:
        if not verified_scope:
            raise ValueError("verified_scope=True is required for stealer-log website-domain search.")
        return self.search(capability="stealer_log_website_domain", value=domain, limit=limit, timeout=timeout, verified_scope=True)

    def search_repository_secret_exposure(self, repository: str, *, verified_scope: bool = False, limit: int = 100, timeout: int = 30) -> ExposureSearchResult:
        if not verified_scope:
            raise ValueError("verified_scope=True is required for repository secret exposure search.")
        return self.search(capability="repository_secret_exposure", value=repository, limit=limit, timeout=timeout, verified_scope=True)

    @staticmethod
    def _summarize(result) -> ExposureSummary:
        summary = ExposureSummary(total_records=len(result.records))
        for provider in result.provider_results:
            summary.provider_statuses[provider.source] = provider.status

        for record in result.records:
            attrs = record.attributes or {}
            if record.record_type == "breach":
                summary.breach_records += 1
            if record.record_type in {"darkweb_public_observation", "darkweb_index_hit", "darkweb_discovery_observation"}:
                summary.darkweb_records += 1
            if record.record_type == "darkweb_discovery_observation":
                summary.darkweb_discovery_records += 1
            if record.record_type in {"intelx_index_hit", "darkweb_index_hit"}:
                summary.indexed_leak_records += 1
            if record.record_type == "paste_exposure":
                summary.paste_records += 1
            if record.record_type == "stealer_log_exposure":
                summary.stealer_log_records += 1
            if record.record_type == "secret_scanning_alert":
                summary.secret_alert_records += 1
            if attrs.get("verified_scope") is True:
                summary.verified_scope_records += 1
            if attrs.get("password_exposed") is True:
                summary.password_exposed = True
            if attrs.get("secret_material_present") is True:
                summary.secret_material_present = True
            # Raw secret material is forbidden at both the adapter and sanitizer boundary.
            if attrs.get("raw_secret_values_stored") is True:
                summary.raw_secret_values_stored = True

        return summary

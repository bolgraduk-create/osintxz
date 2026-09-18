from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)


class HibpExtendedConfigurationError(RuntimeError):
    pass


class HibpVerifiedScopeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HibpSubscribedDomain:
    domain: str
    pwn_count: int | None = None
    pwn_count_excluding_spam_lists: int | None = None


class HibpExtendedClient:
    """Bounded metadata-only client for HIBP paste/domain/stealer APIs.

    R13.13 deliberately never calls any endpoint that can return a password.
    Paste endpoints expose only paste metadata. Stealer-log endpoints expose
    affected domains/email selectors but not credentials. Verified-domain
    workflows additionally confirm that HIBP already recognises the domain as
    subscribed/verified before querying sensitive domain-level results.
    """

    API_BASE_URL = "https://haveibeenpwned.com/api/v3"
    MAX_JSON_BYTES = 4_000_000

    def __init__(
        self,
        *,
        api_key: str | None,
        transport=None,
        user_agent: str = "OSINTXZ/1.0 ExposureIntelligence",
    ) -> None:
        self.api_key = (api_key or "").strip() or None
        self.transport = transport
        self.user_agent = user_agent.strip() or "OSINTXZ/1.0 ExposureIntelligence"

    @property
    def configured(self) -> bool:
        return self.api_key is not None

    def paste_account(self, email: str, *, timeout: int = 30) -> list[dict[str, Any]]:
        value = self._email(email)
        payload = self._get_json(
            f"/pasteAccount/{quote(value, safe='')}",
            timeout=timeout,
            not_found=[] ,
        )
        if not isinstance(payload, list):
            raise ValueError("HIBP paste response must be a JSON list.")
        return [item for item in payload if isinstance(item, dict)]

    def subscribed_domains(self, *, timeout: int = 30) -> list[HibpSubscribedDomain]:
        payload = self._get_json("/subscribedDomains", timeout=timeout, not_found=[])
        if not isinstance(payload, list):
            raise ValueError("HIBP subscribed-domains response must be a JSON list.")
        out: list[HibpSubscribedDomain] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            domain = self._domain(str(item.get("DomainName") or ""), allow_empty=True)
            if not domain:
                continue
            out.append(
                HibpSubscribedDomain(
                    domain=domain,
                    pwn_count=self._int_or_none(item.get("PwnCount")),
                    pwn_count_excluding_spam_lists=self._int_or_none(
                        item.get("PwnCountExcludingSpamLists")
                    ),
                )
            )
        return out

    def require_verified_domain(self, domain: str, *, timeout: int = 30) -> str:
        target = self._domain(domain)
        verified = {item.domain for item in self.subscribed_domains(timeout=timeout)}
        if target not in verified:
            raise HibpVerifiedScopeError(
                "HIBP does not report this domain as subscribed/verified for the configured key."
            )
        return target

    def breached_domain(self, domain: str, *, timeout: int = 30) -> dict[str, list[str]]:
        target = self.require_verified_domain(domain, timeout=timeout)
        payload = self._get_json(
            f"/breachedDomain/{quote(target, safe='')}",
            timeout=timeout,
            not_found={},
        )
        if not isinstance(payload, dict):
            raise ValueError("HIBP breached-domain response must be a JSON object.")
        out: dict[str, list[str]] = {}
        for alias, breaches in payload.items():
            alias_text = str(alias or "").strip()
            if not alias_text or not isinstance(breaches, list):
                continue
            out[alias_text] = [
                str(item).strip()
                for item in breaches
                if str(item).strip()
            ]
        return out

    def stealer_logs_by_email(self, email: str, *, timeout: int = 30) -> list[str]:
        value = self._email(email)
        self.require_verified_domain(value.rsplit("@", 1)[1], timeout=timeout)
        payload = self._get_json(
            f"/stealerLogsByEmail/{quote(value, safe='')}",
            timeout=timeout,
            not_found=[],
        )
        return self._string_list(payload, "HIBP stealer-logs-by-email")

    def stealer_logs_by_email_domain(
        self,
        domain: str,
        *,
        timeout: int = 30,
    ) -> dict[str, list[str]]:
        target = self.require_verified_domain(domain, timeout=timeout)
        payload = self._get_json(
            f"/stealerLogsByEmailDomain/{quote(target, safe='')}",
            timeout=timeout,
            not_found={},
        )
        if not isinstance(payload, dict):
            raise ValueError("HIBP stealer-logs-by-email-domain response must be a JSON object.")
        out: dict[str, list[str]] = {}
        for alias, domains in payload.items():
            alias_text = str(alias or "").strip()
            if not alias_text:
                continue
            out[alias_text] = self._string_list(
                domains,
                "HIBP stealer-log website list",
            )
        return out

    def stealer_logs_by_website_domain(
        self,
        domain: str,
        *,
        timeout: int = 30,
    ) -> list[str]:
        target = self.require_verified_domain(domain, timeout=timeout)
        payload = self._get_json(
            f"/stealerLogsByWebsiteDomain/{quote(target, safe='')}",
            timeout=timeout,
            not_found=[],
        )
        return self._string_list(payload, "HIBP stealer-logs-by-website-domain")

    def _get_json(self, path: str, *, timeout: int, not_found: Any) -> Any:
        if not self.api_key:
            raise HibpExtendedConfigurationError("HIBP API key is not configured.")

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "hibp-api-key": self.api_key,
            "User-Agent": self.user_agent,
        }
        with httpx.Client(
            base_url=self.API_BASE_URL,
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers=headers,
            follow_redirects=False,
        ) as client:
            with client.stream("GET", path) as response:
                if response.status_code == 404:
                    return not_found
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ValueError("Unexpected HIBP response content encoding.")
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(body) + len(chunk) > self.MAX_JSON_BYTES:
                        raise ValueError("HIBP response exceeds download limit.")
                    body.extend(chunk)
                response.raise_for_status()

        try:
            return httpx.Response(200, content=bytes(body)).json()
        except ValueError as exc:
            raise ValueError("HIBP response must be valid JSON.") from exc

    @staticmethod
    def _email(value: str) -> str:
        value = (value or "").strip()
        if not value or "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Malformed email address.")
        return value

    @staticmethod
    def _domain(value: str, *, allow_empty: bool = False) -> str:
        value = (value or "").strip().casefold().rstrip(".")
        if not value and allow_empty:
            return ""
        if not value or "." not in value or any(ch.isspace() for ch in value):
            raise ValueError("Malformed domain.")
        return value

    @staticmethod
    def _string_list(payload: Any, label: str) -> list[str]:
        if not isinstance(payload, list):
            raise ValueError(f"{label} response must be a JSON list.")
        return [str(item).strip() for item in payload if str(item).strip()]

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class _HibpExplicitAdapter(RemoteSourceAdapter):
    def __init__(self, *, client: HibpExtendedClient) -> None:
        self.client = client

    @property
    def configured(self) -> bool:
        return self.client.configured

    @property
    def automatic_enabled(self) -> bool:
        return False

    @staticmethod
    def _failure(source: str, exc: Exception) -> RemoteAdapterResult:
        if isinstance(exc, HibpExtendedConfigurationError):
            return RemoteAdapterResult(
                source=source,
                status=RemoteAdapterStatus.NOT_CONFIGURED,
                error=str(exc),
                metadata={"credentials_required": True},
            )
        if isinstance(exc, HibpVerifiedScopeError):
            return RemoteAdapterResult(
                source=source,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error=str(exc),
                metadata={
                    "verified_scope_required": True,
                    "server_side_domain_verification": True,
                },
            )
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            if code in {401, 403}:
                return RemoteAdapterResult(
                    source=source,
                    status=RemoteAdapterStatus.NOT_SUPPORTED if code == 403 else RemoteAdapterStatus.FAILED,
                    error=f"HIBP access rejected (HTTP {code}).",
                    metadata={
                        "credentials_invalid": code == 401,
                        "verified_scope_or_plan_required": code == 403,
                        "retryable": False,
                    },
                )
            retryable = code == 429 or code >= 500
            return RemoteAdapterResult(
                source=source,
                status=RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"HIBP HTTP {code}.",
                metadata={"retryable": retryable, "rate_limited": code == 429},
            )
        if isinstance(exc, httpx.RequestError):
            return RemoteAdapterResult(
                source=source,
                status=RemoteAdapterStatus.PARTIAL,
                error=str(exc),
                metadata={"retryable": True},
            )
        return RemoteAdapterResult(
            source=source,
            status=RemoteAdapterStatus.FAILED,
            error=str(exc),
            metadata={"failure_isolated": True},
        )


class HibpPasteAdapter(_HibpExplicitAdapter):
    @property
    def source_code(self) -> str:
        return "hibp_pastes"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"email", "paste_exposure"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.supports(query):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED)
        try:
            rows = self.client.paste_account(query.value, timeout=query.timeout)
        except Exception as exc:
            return self._failure(self.source_code, exc)

        records: list[RemoteSourceRecord] = []
        for row in rows[: query.limit]:
            paste_id = str(row.get("Id") or "").strip()
            paste_source = str(row.get("Source") or "").strip()
            if not paste_id or not paste_source:
                continue
            title = str(row.get("Title") or "").strip() or f"{paste_source} paste {paste_id}"
            records.append(
                RemoteSourceRecord(
                    source=self.source_code,
                    record_id=f"{paste_source.casefold()}:{paste_id}",
                    record_type="paste_exposure",
                    display_name=title,
                    source_url="https://haveibeenpwned.com/",
                    identifiers={"PASTE_SOURCE": paste_source, "PASTE_ID": paste_id},
                    attributes={
                        "paste_source": paste_source,
                        "paste_id": paste_id,
                        "date": row.get("Date"),
                        "email_count": row.get("EmailCount"),
                        "subject_match_confirmed": True,
                        "identity_confirmed": False,
                        "metadata_only": True,
                        "paste_content_fetched": False,
                        "raw_secret_values_stored": False,
                    },
                )
            )
        return RemoteAdapterResult(
            source=self.source_code,
            status=RemoteAdapterStatus.SUCCESS,
            records=records,
            metadata={
                "records_found": len(records),
                "metadata_only": True,
                "paste_content_fetched": False,
                "raw_secret_values_stored": False,
            },
        )


class HibpVerifiedDomainAdapter(_HibpExplicitAdapter):
    @property
    def source_code(self) -> str:
        return "hibp_verified_domain"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"verified_domain_breach", "domain_exposure"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.supports(query):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED)
        if not query.verified_scope:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_SUPPORTED,
                error="Verified scope is required for HIBP domain search.",
                metadata={"verified_scope_required": True},
            )
        try:
            rows = self.client.breached_domain(query.value, timeout=query.timeout)
        except Exception as exc:
            return self._failure(self.source_code, exc)

        domain = query.value.strip().casefold().rstrip(".")
        records: list[RemoteSourceRecord] = []
        for alias, breaches in list(rows.items())[: query.limit]:
            address = f"{alias}@{domain}"
            records.append(
                RemoteSourceRecord(
                    source=self.source_code,
                    record_id=address.casefold(),
                    record_type="verified_domain_breach",
                    display_name=f"Breach exposure · {address}",
                    source_url="https://haveibeenpwned.com/DomainSearch",
                    identifiers={"EMAIL": address, "DOMAIN": domain},
                    attributes={
                        "email": address,
                        "breaches": list(breaches),
                        "breach_count": len(breaches),
                        "verified_scope": True,
                        "server_side_domain_verification": True,
                        "identity_confirmed": False,
                        "raw_secret_values_stored": False,
                    },
                )
            )
        return RemoteAdapterResult(
            self.source_code,
            RemoteAdapterStatus.SUCCESS,
            records=records,
            metadata={
                "records_found": len(records),
                "verified_scope": True,
                "server_side_domain_verification": True,
                "raw_secret_values_stored": False,
            },
        )


class HibpStealerLogEmailAdapter(_HibpExplicitAdapter):
    @property
    def source_code(self) -> str:
        return "hibp_stealer_logs_email"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"stealer_log_email"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not query.verified_scope:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_SUPPORTED,
                error="Verified scope is required for HIBP stealer-log email search.",
                metadata={"verified_scope_required": True},
            )
        try:
            domains = self.client.stealer_logs_by_email(query.value, timeout=query.timeout)
        except Exception as exc:
            return self._failure(self.source_code, exc)
        records = [
            RemoteSourceRecord(
                source=self.source_code,
                record_id=f"{query.value.casefold()}::{domain.casefold()}",
                record_type="stealer_log_exposure",
                display_name=f"Stealer-log exposure · {domain}",
                source_url="https://haveibeenpwned.com/",
                identifiers={"EMAIL": query.value, "WEBSITE_DOMAIN": domain},
                attributes={
                    "email": query.value,
                    "website_domain": domain,
                    "credential_exposed": True,
                    "secret_material_present": True,
                    "password_value_returned": False,
                    "verified_scope": True,
                    "server_side_domain_verification": True,
                    "raw_secret_values_stored": False,
                },
            )
            for domain in domains[: query.limit]
        ]
        return RemoteAdapterResult(
            self.source_code,
            RemoteAdapterStatus.SUCCESS,
            records=records,
            metadata={
                "records_found": len(records),
                "credential_exposure_only": True,
                "password_values_returned": False,
                "verified_scope": True,
                "raw_secret_values_stored": False,
            },
        )


class HibpStealerLogEmailDomainAdapter(_HibpExplicitAdapter):
    @property
    def source_code(self) -> str:
        return "hibp_stealer_logs_email_domain"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"stealer_log_email_domain"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not query.verified_scope:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_SUPPORTED,
                error="Verified scope is required for HIBP stealer-log email-domain search.",
                metadata={"verified_scope_required": True},
            )
        try:
            rows = self.client.stealer_logs_by_email_domain(query.value, timeout=query.timeout)
        except Exception as exc:
            return self._failure(self.source_code, exc)
        domain = query.value.strip().casefold().rstrip(".")
        records: list[RemoteSourceRecord] = []
        for alias, websites in list(rows.items())[: query.limit]:
            email = f"{alias}@{domain}"
            records.append(
                RemoteSourceRecord(
                    source=self.source_code,
                    record_id=email.casefold(),
                    record_type="stealer_log_exposure",
                    display_name=f"Stealer-log exposure · {email}",
                    source_url="https://haveibeenpwned.com/",
                    identifiers={"EMAIL": email, "DOMAIN": domain},
                    attributes={
                        "email": email,
                        "website_domains": list(websites),
                        "website_count": len(websites),
                        "credential_exposed": True,
                        "secret_material_present": True,
                        "password_values_returned": False,
                        "verified_scope": True,
                        "server_side_domain_verification": True,
                        "raw_secret_values_stored": False,
                    },
                )
            )
        return RemoteAdapterResult(
            self.source_code,
            RemoteAdapterStatus.SUCCESS,
            records=records,
            metadata={
                "records_found": len(records),
                "password_values_returned": False,
                "verified_scope": True,
                "raw_secret_values_stored": False,
            },
        )


class HibpStealerLogWebsiteDomainAdapter(_HibpExplicitAdapter):
    @property
    def source_code(self) -> str:
        return "hibp_stealer_logs_website_domain"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"stealer_log_website_domain"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not query.verified_scope:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_SUPPORTED,
                error="Verified scope is required for HIBP stealer-log website-domain search.",
                metadata={"verified_scope_required": True},
            )
        try:
            emails = self.client.stealer_logs_by_website_domain(query.value, timeout=query.timeout)
        except Exception as exc:
            return self._failure(self.source_code, exc)
        domain = query.value.strip().casefold().rstrip(".")
        records = [
            RemoteSourceRecord(
                source=self.source_code,
                record_id=email.casefold(),
                record_type="stealer_log_exposure",
                display_name=f"Stealer-log exposure · {email}",
                source_url="https://haveibeenpwned.com/",
                identifiers={"EMAIL": email, "WEBSITE_DOMAIN": domain},
                attributes={
                    "email": email,
                    "website_domain": domain,
                    "credential_exposed": True,
                    "secret_material_present": True,
                    "password_values_returned": False,
                    "verified_scope": True,
                    "server_side_domain_verification": True,
                    "raw_secret_values_stored": False,
                },
            )
            for email in emails[: query.limit]
        ]
        return RemoteAdapterResult(
            self.source_code,
            RemoteAdapterStatus.SUCCESS,
            records=records,
            metadata={
                "records_found": len(records),
                "password_values_returned": False,
                "verified_scope": True,
                "raw_secret_values_stored": False,
            },
        )

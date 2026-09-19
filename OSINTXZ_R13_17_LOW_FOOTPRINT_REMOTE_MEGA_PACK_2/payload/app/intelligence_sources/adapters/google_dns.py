from __future__ import annotations

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient


_TYPES = ("A", "AAAA", "CNAME", "MX", "NS", "TXT")


def _domain(value: str) -> str | None:
    raw = (value or "").strip().rstrip(".").casefold()
    if not raw or "://" in raw or any(ch.isspace() for ch in raw):
        return None
    try:
        result = raw.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if "." not in result or len(result) > 253:
        return None
    return result


class GooglePublicDnsAdapter(RemoteSourceAdapter):
    API = "https://dns.google/resolve"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 GooglePublicDNS",
        )

    @property
    def source_code(self) -> str:
        return "google_public_dns"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"domain", "dns", "domain_dns"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        domain = _domain(query.value)
        if domain is None:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="DNS lookup requires a domain name.",
            )
        records: dict[str, list[dict[str, object]]] = {}
        failures: list[str] = []
        for rtype in _TYPES:
            try:
                payload = self.client.request_json(
                    "GET",
                    self.API,
                    params={"name": domain, "type": rtype, "do": "1"},
                    timeout=query.timeout,
                    max_bytes=750_000,
                )
                answers = payload.get("Answer", []) if isinstance(payload, dict) else []
                clean = []
                for answer in answers[:50]:
                    if not isinstance(answer, dict):
                        continue
                    clean.append({
                        "name": answer.get("name"),
                        "type": answer.get("type"),
                        "ttl": answer.get("TTL"),
                        "data": answer.get("data"),
                    })
                if clean:
                    records[rtype] = clean
            except Exception as exc:
                failures.append(f"{rtype}:{type(exc).__name__}")

        if not records and failures:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.PARTIAL,
                error="All DNS record queries failed.",
                metadata={"record_types_failed": failures, "failure_isolated": True},
            )
        if not records:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=[],
                metadata={"records_found": 0, "no_local_cache": True},
            )
        record = RemoteSourceRecord(
            source=self.source_code,
            record_id=domain,
            record_type="dns_snapshot",
            display_name=domain,
            source_url="https://dns.google/",
            identifiers={"DOMAIN": domain},
            attributes={
                "dns_records": records,
                "record_types_queried": list(_TYPES),
                "record_types_failed": failures,
                "dnssec_requested": True,
                "public_dns_data": True,
                "raw_response_stored": False,
                "no_local_cache": True,
            },
        )
        return RemoteAdapterResult(
            source=self.source_code,
            status=RemoteAdapterStatus.PARTIAL if failures else RemoteAdapterStatus.SUCCESS,
            records=[record],
            metadata={"records_found": 1, "no_local_cache": True},
        )

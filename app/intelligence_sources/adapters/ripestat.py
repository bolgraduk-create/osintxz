from __future__ import annotations

import ipaddress
import re

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list


_ASN_RE = re.compile(r"^(?:AS)?(\d{1,10})$", re.I)


class RipeStatAdapter(RemoteSourceAdapter):
    API = "https://stat.ripe.net/data"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 RIPEstat",
        )

    @property
    def source_code(self) -> str:
        return "ripestat"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"ip", "ip_address", "asn", "autonomous_system", "network_registration"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip()
        if query.capability in {"ip", "ip_address", "network_registration"}:
            try:
                resource = str(ipaddress.ip_address(value))
            except ValueError:
                return self._unsupported("RIPEstat IP lookup requires an exact IP address.")
            endpoint = "network-info"
        else:
            match = _ASN_RE.fullmatch(value)
            if not match:
                return self._unsupported("RIPEstat ASN lookup requires an exact ASN.")
            number = int(match.group(1))
            if not 1 <= number <= 4_294_967_295:
                return self._unsupported("Malformed ASN.")
            resource = f"AS{number}"
            endpoint = "as-overview"

        try:
            payload = self.client.request_json(
                "GET",
                f"{self.API}/{endpoint}/data.json",
                params={"resource": resource, "sourceapp": "osintxz"},
                timeout=query.timeout,
                max_bytes=1_500_000,
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
                raise ValueError("RIPEstat response is missing data.")
            data = payload["data"]
            if endpoint == "network-info":
                prefix = str(data.get("prefix") or "").strip()
                asns = [str(item) for item in (data.get("asns") or []) if str(item).strip()]
                display = prefix or resource
                identifiers = {"IP": resource}
                if prefix:
                    identifiers["PREFIX"] = prefix
                attrs = {
                    "prefix": prefix or None,
                    "asns": asns,
                    "exact_ip_lookup": True,
                    "public_network_data": True,
                }
                record_id = f"ip:{resource}"
            else:
                number = resource.removeprefix("AS")
                display = str(data.get("holder") or resource).strip()
                identifiers = {"ASN": resource}
                attrs = {
                    "holder": data.get("holder"),
                    "announced": data.get("announced"),
                    "block": data.get("block"),
                    "resource_type": data.get("type"),
                    "exact_asn_lookup": True,
                    "public_network_data": True,
                }
                record_id = f"asn:{number}"
            attrs.update({"raw_response_stored": False, "no_local_cache": True})
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=[RemoteSourceRecord(
                    source=self.source_code,
                    record_id=record_id,
                    record_type="network_registration",
                    display_name=display,
                    source_url=f"https://stat.ripe.net/{resource}",
                    identifiers=identifiers,
                    attributes=attrs,
                )],
                metadata={"records_found": 1, "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

    def _unsupported(self, message: str) -> RemoteAdapterResult:
        return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error=message)

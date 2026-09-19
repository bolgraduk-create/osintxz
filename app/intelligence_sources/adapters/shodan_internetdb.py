from __future__ import annotations

import ipaddress

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list


class ShodanInternetDbAdapter(RemoteSourceAdapter):
    BASE = "https://internetdb.shodan.io"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 ShodanInternetDB",
        )

    @property
    def source_code(self) -> str:
        return "shodan_internetdb"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"ip", "ip_address", "open_ports", "vulnerability"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        try:
            ip = str(ipaddress.ip_address(query.value.strip()))
        except ValueError:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="InternetDB requires a valid IP address.",
            )
        try:
            payload = self.client.request_json(
                "GET",
                f"{self.BASE}/{ip}",
                timeout=query.timeout,
                max_bytes=500_000,
            )
            if not isinstance(payload, dict):
                return RemoteAdapterResult(source=self.source_code, status=RemoteAdapterStatus.SUCCESS)
            record = RemoteSourceRecord(
                source=self.source_code,
                record_id=ip,
                record_type="internet_host_observation",
                display_name=ip,
                source_url=f"https://internetdb.shodan.io/{ip}",
                identifiers={"IP": ip},
                attributes={
                    "ports": list(payload.get("ports") or [])[:200],
                    "cpes": text_list(payload.get("cpes"), limit=100),
                    "hostnames": text_list(payload.get("hostnames"), limit=100),
                    "tags": text_list(payload.get("tags"), limit=100),
                    "vulnerabilities": text_list(payload.get("vulns"), limit=100),
                    "banner_data_returned": False,
                    "public_snapshot": True,
                    "no_local_cache": True,
                },
            )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=[record],
                metadata={"records_found": 1, "no_local_cache": True},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return RemoteAdapterResult(
                    source=self.source_code,
                    status=RemoteAdapterStatus.SUCCESS,
                    records=[],
                    metadata={"records_found": 0},
                )
            return failure_result(self.source_code, exc)
        except Exception as exc:
            return failure_result(self.source_code, exc)

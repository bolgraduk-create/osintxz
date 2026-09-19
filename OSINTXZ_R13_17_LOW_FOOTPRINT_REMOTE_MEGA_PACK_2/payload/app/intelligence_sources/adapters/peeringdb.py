from __future__ import annotations

import re

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result


_ASN_RE = re.compile(r"^(?:AS)?(\d{1,10})$", re.I)


class PeeringDbAdapter(RemoteSourceAdapter):
    API = "https://www.peeringdb.com/api/net"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 PeeringDB",
        )

    @property
    def source_code(self) -> str:
        return "peeringdb_public"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"asn", "autonomous_system", "peering_network"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        match = _ASN_RE.fullmatch(query.value.strip())
        if not match:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="PeeringDB lookup requires an exact ASN.",
            )
        asn = int(match.group(1))
        if not 1 <= asn <= 4_294_967_295:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="Malformed ASN.",
            )
        try:
            payload = self.client.request_json(
                "GET",
                self.API,
                params={
                    "asn": str(asn),
                    "limit": str(min(query.limit, 20)),
                    "depth": "0",
                    "fields": "id,org_id,name,aka,name_long,asn,website,info_type,info_prefixes4,info_prefixes6,irr_as_set,status",
                },
                timeout=query.timeout,
                max_bytes=1_500_000,
            )
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            records: list[RemoteSourceRecord] = []
            for row in rows[: query.limit]:
                if not isinstance(row, dict):
                    continue
                row_asn = row.get("asn")
                if str(row_asn or "") != str(asn):
                    continue
                rid = str(row.get("id") or f"asn-{asn}")
                records.append(RemoteSourceRecord(
                    source=self.source_code,
                    record_id=rid,
                    record_type="peering_network",
                    display_name=str(row.get("name") or f"AS{asn}"),
                    source_url=f"https://www.peeringdb.com/net/{rid}" if row.get("id") else None,
                    identifiers={"ASN": f"AS{asn}"},
                    attributes={
                        "organization_id": row.get("org_id"),
                        "aka": row.get("aka"),
                        "long_name": row.get("name_long"),
                        "website": row.get("website"),
                        "network_type": row.get("info_type"),
                        "ipv4_prefixes": row.get("info_prefixes4"),
                        "ipv6_prefixes": row.get("info_prefixes6"),
                        "irr_as_set": row.get("irr_as_set"),
                        "status": row.get("status"),
                        "exact_asn_lookup": True,
                        "contact_data_requested": False,
                        "raw_response_stored": False,
                        "no_local_cache": True,
                    },
                ))
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records), "guest_api": True, "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

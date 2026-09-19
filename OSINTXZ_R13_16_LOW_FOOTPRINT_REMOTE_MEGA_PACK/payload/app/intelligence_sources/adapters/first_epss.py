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


_CVE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.I)


class FirstEpssAdapter(RemoteSourceAdapter):
    API = "https://api.first.org/data/v1/epss"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 FIRST-EPSS",
        )

    @property
    def source_code(self) -> str:
        return "first_epss"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"cve", "cve_id", "epss"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip().upper()
        if not _CVE.fullmatch(value):
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="EPSS requires an exact CVE identifier.",
            )
        try:
            payload = self.client.request_json(
                "GET",
                self.API,
                params={"cve": value},
                timeout=query.timeout,
                max_bytes=500_000,
            )
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            records: list[RemoteSourceRecord] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                cve = str(row.get("cve") or "").strip().upper()
                if not _CVE.fullmatch(cve):
                    continue
                records.append(
                    RemoteSourceRecord(
                        source=self.source_code,
                        record_id=cve,
                        record_type="vulnerability_probability",
                        display_name=f"{cve} — EPSS {row.get('epss')}",
                        source_url="https://www.first.org/epss/",
                        identifiers={"CVE": cve},
                        attributes={
                            "epss": row.get("epss"),
                            "percentile": row.get("percentile"),
                            "date": row.get("date"),
                            "exact_identifier": True,
                            "public_data": True,
                        },
                    )
                )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records), "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

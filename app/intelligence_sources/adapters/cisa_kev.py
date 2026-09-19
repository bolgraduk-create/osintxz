from __future__ import annotations

import re

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list


_CVE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.I)


class CisaKevAdapter(RemoteSourceAdapter):
    FEED = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 CISA-KEV",
        )

    @property
    def source_code(self) -> str:
        return "cisa_kev"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"cve", "cve_id", "known_exploited"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip().upper()
        if not _CVE.fullmatch(value):
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="CISA KEV lookup requires an exact CVE identifier.",
            )
        try:
            payload = self.client.request_json(
                "GET",
                self.FEED,
                timeout=query.timeout,
                max_bytes=4_000_000,
            )
            rows = payload.get("vulnerabilities", []) if isinstance(payload, dict) else []
            match = next(
                (
                    row
                    for row in rows
                    if isinstance(row, dict)
                    and str(row.get("cveID") or "").strip().upper() == value
                ),
                None,
            )
            if match is None:
                return RemoteAdapterResult(
                    source=self.source_code,
                    status=RemoteAdapterStatus.SUCCESS,
                    records=[],
                    metadata={
                        "records_found": 0,
                        "catalog_version": payload.get("catalogVersion") if isinstance(payload, dict) else None,
                        "transient_feed_bytes_only": True,
                        "feed_persisted": False,
                    },
                )
            record = RemoteSourceRecord(
                source=self.source_code,
                record_id=value,
                record_type="known_exploited_vulnerability",
                display_name=str(match.get("vulnerabilityName") or value),
                source_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                identifiers={"CVE": value},
                attributes={
                    "vendor_project": match.get("vendorProject"),
                    "product": match.get("product"),
                    "date_added": match.get("dateAdded"),
                    "short_description": match.get("shortDescription"),
                    "required_action": match.get("requiredAction"),
                    "due_date": match.get("dueDate"),
                    "known_ransomware_campaign_use": match.get("knownRansomwareCampaignUse"),
                    "notes": text_list(str(match.get("notes") or "").split(";"), limit=20),
                    "cwes": text_list(match.get("cwes"), limit=20),
                    "exact_identifier": True,
                    "authoritative_kev_catalog": True,
                    "public_data": True,
                },
            )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=[record],
                metadata={
                    "records_found": 1,
                    "catalog_version": payload.get("catalogVersion") if isinstance(payload, dict) else None,
                    "transient_feed_bytes_only": True,
                    "feed_persisted": False,
                },
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

from __future__ import annotations

import re
from typing import Any

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import (
    PublicJsonClient,
    failure_result,
)


_CVE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.I)


class NvdCveAdapter(RemoteSourceAdapter):
    API = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self, *, api_key: str | None = None, transport=None) -> None:
        headers = {}
        if (api_key or "").strip():
            headers["apiKey"] = str(api_key).strip()
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 NVDPublicData",
            extra_headers=headers,
        )

    @property
    def source_code(self) -> str:
        return "nvd_cve_api"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({
            "cve",
            "cve_id",
            "vulnerability",
            "product",
            "vendor",
            "keyword",
        })

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        exact = bool(_CVE.fullmatch(query.value))
        params: dict[str, Any] = {
            "resultsPerPage": min(query.limit, 100),
            "startIndex": 0,
        }
        if exact:
            params["cveId"] = query.value.upper()
        else:
            params["keywordSearch"] = query.value
        try:
            payload = self.client.request_json(
                "GET",
                self.API,
                params=params,
                timeout=query.timeout,
            )
            rows = payload.get("vulnerabilities", []) if isinstance(payload, dict) else []
            records: list[RemoteSourceRecord] = []
            for wrapper in rows:
                if not isinstance(wrapper, dict):
                    continue
                cve = wrapper.get("cve")
                if not isinstance(cve, dict):
                    continue
                cve_id = str(cve.get("id") or "").strip().upper()
                if not _CVE.fullmatch(cve_id):
                    continue
                description = self._english_description(cve.get("descriptions"))
                records.append(
                    RemoteSourceRecord(
                        source=self.source_code,
                        record_id=cve_id,
                        record_type="vulnerability",
                        display_name=(
                            f"{cve_id} — {description[:140]}"
                            if description
                            else cve_id
                        ),
                        source_url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                        identifiers={"CVE": cve_id},
                        attributes={
                            "description": description,
                            "vuln_status": cve.get("vulnStatus"),
                            "published": cve.get("published"),
                            "last_modified": cve.get("lastModified"),
                            "cvss": self._cvss(cve.get("metrics")),
                            "weaknesses": self._weaknesses(cve.get("weaknesses")),
                            "references": self._references(cve.get("references")),
                            "exact_identifier": exact,
                            "public_data": True,
                        },
                    )
                )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records[: query.limit],
                metadata={
                    "records_found": len(records[: query.limit]),
                    "total_results": (
                        payload.get("totalResults")
                        if isinstance(payload, dict)
                        else None
                    ),
                    "api_key_optional": True,
                },
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

    @staticmethod
    def _english_description(rows) -> str | None:
        if not isinstance(rows, list):
            return None
        for row in rows:
            if isinstance(row, dict) and str(row.get("lang") or "").lower() == "en":
                value = str(row.get("value") or "").strip()
                if value:
                    return value
        return None

    @staticmethod
    def _cvss(metrics) -> dict[str, Any]:
        if not isinstance(metrics, dict):
            return {}
        for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            rows = metrics.get(key)
            if not isinstance(rows, list) or not rows:
                continue
            first = rows[0] if isinstance(rows[0], dict) else {}
            data = first.get("cvssData") if isinstance(first.get("cvssData"), dict) else {}
            return {
                "version": data.get("version"),
                "base_score": data.get("baseScore"),
                "base_severity": data.get("baseSeverity") or first.get("baseSeverity"),
                "vector": data.get("vectorString"),
                "source": first.get("source"),
            }
        return {}

    @staticmethod
    def _weaknesses(rows) -> list[str]:
        out: list[str] = []
        if not isinstance(rows, list):
            return out
        for row in rows:
            if not isinstance(row, dict):
                continue
            for desc in row.get("description") or []:
                if not isinstance(desc, dict):
                    continue
                value = str(desc.get("value") or "").strip()
                if value and value not in out:
                    out.append(value)
                if len(out) >= 20:
                    return out
        return out

    @staticmethod
    def _references(rows) -> list[str]:
        out: list[str] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "").strip()
            if url and url not in out:
                out.append(url)
            if len(out) >= 10:
                break
        return out

from __future__ import annotations

import hashlib
import json
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)


class TradeCslAdapter(RemoteSourceAdapter):
    URL = "https://api.trade.gov/gateway/v1/consolidated_screening_list/search"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: JsonHttpClient | None = None,
    ) -> None:
        self.api_key = (api_key or "").strip() or None
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "us_trade_csl"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"name", "organization", "person", "screening", "fuzzy_name"})

    @property
    def global_scope(self) -> bool:
        return True

    @property
    def configured(self) -> bool:
        return self.api_key is not None

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.configured:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_CONFIGURED,
                error="TRADE_GOV_API_KEY is not configured.",
            )
        params: dict[str, str | int] = {"api_key": self.api_key or ""}
        if query.capability == "fuzzy_name":
            params["fuzzy_name"] = query.value
        else:
            params["name"] = query.value
        try:
            payload = self.client.get_json(self.URL, params=params, timeout=query.timeout)
            items = payload.get("results", []) if isinstance(payload, dict) else []
            if not isinstance(items, list):
                raise ValueError("Malformed CSL response.")
            records = [
                self._map(item)
                for item in items[: query.limit]
                if isinstance(item, dict)
            ]
            records = [record for record in records if record is not None]
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={
                    "records_found": len(records),
                    "screening_only": True,
                    "identity_confirmation_performed": False,
                    "due_diligence_required": True,
                },
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            retryable = code == 429 or code >= 500
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"Trade.gov CSL HTTP {code}",
                metadata={
                    "retryable": retryable,
                    "rate_limited": code == 429,
                    "credentials_invalid_or_forbidden": code in {401, 403},
                },
            )

    def _map(self, item: dict) -> RemoteSourceRecord | None:
        name = str(item.get("name") or "").strip()
        if not name:
            return None
        source = str(item.get("source") or item.get("source_list") or "").strip()
        raw_id = item.get("id") or item.get("uid")
        if raw_id:
            record_id = str(raw_id).strip()
        else:
            stable = json.dumps(
                [name, source, item.get("addresses"), item.get("country")],
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            record_id = hashlib.sha256(stable.encode("utf-8")).hexdigest()

        source_url = item.get("source_information_url")
        if not isinstance(source_url, str) or not source_url.startswith("http"):
            source_url = "https://www.trade.gov/consolidated-screening-list"

        country = str(item.get("country") or "").strip().upper() or None
        if country and len(country) != 2:
            country = None

        return RemoteSourceRecord(
            source=self.source_code,
            record_id=record_id,
            record_type="screening_candidate",
            display_name=name,
            source_url=source_url,
            country=country,
            identifiers={},
            attributes={
                "source_list": source,
                "addresses": item.get("addresses"),
                "alt_names": item.get("alt_names") or item.get("alternate_names"),
                "programs": item.get("programs"),
                "remarks": item.get("remarks"),
                "score": item.get("score"),
                "type": item.get("type"),
                "candidate_only": True,
                "screening_match_only": True,
                "identity_confirmed": False,
                "restriction_status_inferred": False,
                "due_diligence_required": True,
            },
        )

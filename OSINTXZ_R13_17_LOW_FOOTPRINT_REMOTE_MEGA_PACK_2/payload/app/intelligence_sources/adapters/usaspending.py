from __future__ import annotations

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result


class UsaSpendingRecipientAdapter(RemoteSourceAdapter):
    API = "https://api.usaspending.gov/api/v2/recipient/"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 USAspending",
        )

    @property
    def source_code(self) -> str:
        return "usaspending_recipients"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"recipient", "organization", "uei", "duns", "federal_award_recipient"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"US"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip()
        if len(value) < 2:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="USAspending recipient search requires at least two characters.",
            )
        try:
            payload = self.client.request_json(
                "POST",
                self.API,
                json_body={
                    "keyword": value,
                    "order": "desc",
                    "sort": "amount",
                    "page": 1,
                    "limit": min(query.limit, 50),
                    "award_type": "all",
                },
                timeout=query.timeout,
                max_bytes=2_000_000,
            )
            rows = payload.get("results", []) if isinstance(payload, dict) else []
            records: list[RemoteSourceRecord] = []
            for row in rows[: query.limit]:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or row.get("recipient_name") or "").strip()
                rid = str(row.get("id") or row.get("recipient_id") or row.get("uei") or row.get("duns") or name).strip()
                if not name or not rid:
                    continue
                identifiers: dict[str, str] = {}
                if row.get("uei"):
                    identifiers["UEI"] = str(row["uei"])
                if row.get("duns"):
                    identifiers["DUNS"] = str(row["duns"])
                records.append(RemoteSourceRecord(
                    source=self.source_code,
                    record_id=rid,
                    record_type="federal_award_recipient",
                    display_name=name,
                    source_url="https://www.usaspending.gov/",
                    country="US",
                    identifiers=identifiers,
                    attributes={
                        "recipient_level": row.get("level") or row.get("recipient_level"),
                        "total_award_amount": row.get("amount"),
                        "candidate_only": True,
                        "name_match_is_not_identity_confirmation": True,
                        "public_federal_spending_data": True,
                        "raw_response_stored": False,
                        "no_local_cache": True,
                    },
                ))
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records), "no_auth": True, "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

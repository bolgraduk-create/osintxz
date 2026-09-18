from __future__ import annotations

from typing import Any

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import (
    PublicJsonClient,
)


class OpenFecAdapter(RemoteSourceAdapter):
    """Free OpenFEC search using DEMO_KEY or an optional free user key."""

    BASE = "https://api.open.fec.gov/v1"

    def __init__(self, *, api_key: str | None = None, transport=None) -> None:
        self.api_key = (api_key or "").strip() or "DEMO_KEY"
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 OpenFEC",
        )

    @property
    def source_code(self) -> str:
        return "us_fec"

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"US"})

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({
            "candidate",
            "committee",
            "organization",
            "contribution",
            "contributor",
            "name",
        })

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        specs = self._specs(query)
        records: list[RemoteSourceRecord] = []
        errors: list[str] = []
        retryable = False
        for endpoint, params, kind in specs:
            params = {
                **params,
                "api_key": self.api_key,
                "per_page": min(query.limit, 100),
                "page": 1,
            }
            try:
                payload = self.client.request_json(
                    "GET",
                    f"{self.BASE}{endpoint}",
                    params=params,
                    timeout=query.timeout,
                )
            except httpx.HTTPStatusError as exc:
                errors.append(f"{kind}: HTTP {exc.response.status_code}")
                retryable = retryable or (
                    exc.response.status_code == 429
                    or exc.response.status_code >= 500
                )
                continue
            except Exception as exc:
                errors.append(f"{kind}: {exc}")
                continue

            rows = payload.get("results", []) if isinstance(payload, dict) else []
            for row in rows if isinstance(rows, list) else []:
                if isinstance(row, dict):
                    rec = self._record(kind, row)
                    if rec is not None:
                        records.append(rec)
                if len(records) >= query.limit:
                    break
            if len(records) >= query.limit:
                break

        status = RemoteAdapterStatus.SUCCESS
        if errors and records:
            status = RemoteAdapterStatus.PARTIAL
        elif errors and not records:
            status = RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED
        return RemoteAdapterResult(
            source=self.source_code,
            status=status,
            records=records[: query.limit],
            error="; ".join(errors) if errors else None,
            metadata={
                "records_found": len(records[: query.limit]),
                "demo_key_used": self.api_key == "DEMO_KEY",
                "street_address_fields_retained": False,
            },
        )

    def _specs(self, query: RemoteSourceQuery):
        if query.capability == "candidate":
            return [("/candidates/search/", {"q": query.value}, "candidate")]
        if query.capability in {"committee", "organization"}:
            return [("/committees/", {"q": query.value}, "committee")]
        if query.capability in {"contribution", "contributor"}:
            return [(
                "/schedules/schedule_a/",
                {"contributor_name": query.value},
                "contribution",
            )]
        return [
            ("/candidates/search/", {"q": query.value}, "candidate"),
            ("/committees/", {"q": query.value}, "committee"),
        ]

    @staticmethod
    def _record(kind: str, row: dict[str, Any]) -> RemoteSourceRecord | None:
        if kind == "candidate":
            rid = str(row.get("candidate_id") or "").strip()
            if not rid:
                return None
            return RemoteSourceRecord(
                source="us_fec",
                record_id=f"candidate:{rid}",
                record_type="fec_candidate",
                display_name=str(row.get("name") or rid).strip(),
                source_url=f"https://www.fec.gov/data/candidate/{rid}/",
                country="US",
                identifiers={"FEC_CANDIDATE_ID": rid},
                attributes={
                    "office": row.get("office_full") or row.get("office"),
                    "party": row.get("party_full") or row.get("party"),
                    "state": row.get("state"),
                    "district": row.get("district"),
                    "cycles": row.get("cycles") or [],
                    "candidate_only": True,
                    "public_sensitive": True,
                },
            )
        if kind == "committee":
            rid = str(row.get("committee_id") or "").strip()
            if not rid:
                return None
            return RemoteSourceRecord(
                source="us_fec",
                record_id=f"committee:{rid}",
                record_type="fec_committee",
                display_name=str(row.get("name") or rid).strip(),
                source_url=f"https://www.fec.gov/data/committee/{rid}/",
                country="US",
                identifiers={"FEC_COMMITTEE_ID": rid},
                attributes={
                    "committee_type": row.get("committee_type_full"),
                    "designation": row.get("designation_full"),
                    "party": row.get("party_full"),
                    "state": row.get("state"),
                    "cycles": row.get("cycles") or [],
                    "candidate_only": True,
                    "public_sensitive": True,
                },
            )
        rid = str(
            row.get("sub_id")
            or row.get("transaction_id")
            or row.get("file_number")
            or ""
        ).strip()
        if not rid:
            return None
        return RemoteSourceRecord(
            source="us_fec",
            record_id=f"contribution:{rid}",
            record_type="fec_contribution",
            display_name=str(row.get("contributor_name") or "FEC contribution").strip(),
            source_url="https://www.fec.gov/data/receipts/individual-contributions/",
            country="US",
            identifiers={
                k: str(v).strip()
                for k, v in {
                    "FEC_SUB_ID": row.get("sub_id"),
                    "FEC_COMMITTEE_ID": row.get("committee_id"),
                    "FEC_CANDIDATE_ID": row.get("candidate_id"),
                }.items()
                if str(v or "").strip()
            },
            attributes={
                "amount": row.get("contribution_receipt_amount"),
                "date": row.get("contribution_receipt_date"),
                "occupation": row.get("contributor_occupation"),
                "employer": row.get("contributor_employer"),
                "state": row.get("contributor_state"),
                "memo_text": row.get("memo_text"),
                "street_address_fields_retained": False,
                "public_sensitive": True,
                "candidate_only": True,
            },
        )

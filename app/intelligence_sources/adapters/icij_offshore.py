from __future__ import annotations

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


class IcijOffshoreLeaksAdapter(RemoteSourceAdapter):
    """ICIJ Offshore Leaks reconciliation API.

    Reconciliation hits are investigative candidates, never automatic proof
    that an investigation subject is the same person or organization.
    """

    API = "https://offshoreleaks.icij.org/api/v1/reconcile"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 ICIJOffshoreReconciliation",
        )

    @property
    def source_code(self) -> str:
        return "icij_offshore_leaks"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({
            "name",
            "person",
            "organization",
            "offshore_entity",
            "officer",
            "intermediary",
            "address",
        })

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        body: dict[str, Any] = {
            "query": query.value,
            "limit": min(query.limit, 25),
        }
        type_name = {
            "person": "Officer",
            "officer": "Officer",
            "organization": "Entity",
            "offshore_entity": "Entity",
            "intermediary": "Intermediary",
            "address": "Address",
        }.get(query.capability)
        if type_name:
            body["type"] = type_name

        try:
            payload = self.client.request_json(
                "POST",
                self.API,
                json_body=body,
                timeout=query.timeout,
            )
            rows = payload.get("result", []) if isinstance(payload, dict) else []
            records: list[RemoteSourceRecord] = []
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                rid = str(row.get("id") or "").strip()
                name = str(row.get("name") or "").strip()
                if not rid or not name:
                    continue
                type_rows = row.get("type") if isinstance(row.get("type"), list) else []
                types = [
                    str(item.get("name") or item.get("id") or "").strip()
                    for item in type_rows
                    if isinstance(item, dict)
                    and str(item.get("name") or item.get("id") or "").strip()
                ]
                records.append(
                    RemoteSourceRecord(
                        source=self.source_code,
                        record_id=rid,
                        record_type="icij_reconciliation_candidate",
                        display_name=name,
                        source_url=f"https://offshoreleaks.icij.org/nodes/{rid}",
                        identifiers={"ICIJ_NODE_ID": rid},
                        attributes={
                            "score": row.get("score"),
                            "match": bool(row.get("match")),
                            "types": types,
                            "candidate_only": True,
                            "identity_inference_prohibited": True,
                            "offshore_status_inference_prohibited": True,
                            "public_investigative_dataset": True,
                        },
                    )
                )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records[: query.limit],
                metadata={
                    "records_found": len(records[: query.limit]),
                    "reconciliation_candidates_only": True,
                    "batch_limit": 25,
                },
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

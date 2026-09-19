from __future__ import annotations

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list


class FbiWantedAdapter(RemoteSourceAdapter):
    API = "https://api.fbi.gov/wanted/v1/list"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 FBIWantedPublic",
        )

    @property
    def source_code(self) -> str:
        return "fbi_wanted"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"wanted_person", "wanted_name"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"US"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        try:
            payload = self.client.request_json(
                "GET",
                self.API,
                params={"title": query.value, "page": 1, "pageSize": min(query.limit, 20)},
                timeout=query.timeout,
                max_bytes=4_000_000,
            )
            rows = payload.get("items", []) if isinstance(payload, dict) else []
            records: list[RemoteSourceRecord] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                uid = str(row.get("uid") or row.get("@id") or row.get("url") or "").strip()
                title = str(row.get("title") or "").strip()
                if not uid or not title:
                    continue
                records.append(
                    RemoteSourceRecord(
                        source=self.source_code,
                        record_id=uid,
                        record_type="public_wanted_notice_candidate",
                        display_name=title,
                        source_url=str(row.get("url") or row.get("@id") or "") or None,
                        country="US",
                        identifiers={"FBI_UID": uid},
                        attributes={
                            "subjects": text_list(row.get("subjects"), limit=10),
                            "aliases": text_list(row.get("aliases"), limit=20),
                            "dates_of_birth_used": text_list(row.get("dates_of_birth_used"), limit=10),
                            "nationality": row.get("nationality"),
                            "sex": row.get("sex"),
                            "race": row.get("race"),
                            "hair": row.get("hair"),
                            "eyes": row.get("eyes"),
                            "reward_text": row.get("reward_text"),
                            "description": row.get("description"),
                            "caution": row.get("caution"),
                            "candidate_only": True,
                            "identity_inference_prohibited": True,
                            "guilt_inference_prohibited": True,
                            "legal_outcome_inference_prohibited": True,
                            "public_notice_only": True,
                            "notice_is_not_proof_of_identity_or_guilt": True,
                        },
                    )
                )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records[: query.limit],
                metadata={
                    "records_found": len(records[: query.limit]),
                    "candidate_only": True,
                    "legal_safety": True,
                    "no_local_cache": True,
                },
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

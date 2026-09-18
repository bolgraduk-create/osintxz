from __future__ import annotations

import re

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
    first_text,
    text_list,
)


_ORCID = re.compile(r"^\d{4}-\d{4}-\d{4}-[\dX]{4}$", re.I)


class OrcidPublicAdapter(RemoteSourceAdapter):
    """Read-only ORCID anonymous/public expanded search."""

    SEARCH_URL = "https://pub.orcid.org/v3.0/expanded-search/"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 ORCIDPublicSearch",
            extra_headers={"Accept": "application/json"},
        )

    @property
    def source_code(self) -> str:
        return "orcid_public"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"orcid", "person", "researcher", "name"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip()
        q = f"orcid:{value}" if _ORCID.fullmatch(value) else value
        try:
            payload = self.client.request_json(
                "GET",
                self.SEARCH_URL,
                params={
                    "q": q,
                    "start": 0,
                    "rows": min(query.limit, 100),
                },
                timeout=query.timeout,
            )
            rows = []
            if isinstance(payload, dict):
                rows = (
                    payload.get("expanded-result")
                    or payload.get("expanded-search:expanded-result")
                    or []
                )
            if isinstance(rows, dict):
                rows = [rows]
            records: list[RemoteSourceRecord] = []
            exact = bool(_ORCID.fullmatch(value))
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                orcid = str(
                    row.get("orcid-id")
                    or row.get("orcid")
                    or ""
                ).strip()
                if not _ORCID.fullmatch(orcid):
                    continue
                given = first_text(row.get("given-names")) or ""
                family = first_text(row.get("family-names")) or ""
                credit = first_text(row.get("credit-name")) or ""
                display = credit or " ".join(
                    part for part in (given, family) if part
                ).strip() or orcid
                records.append(
                    RemoteSourceRecord(
                        source=self.source_code,
                        record_id=orcid,
                        record_type="orcid_researcher",
                        display_name=display,
                        source_url=f"https://orcid.org/{orcid}",
                        identifiers={"ORCID": orcid},
                        attributes={
                            "given_names": given or None,
                            "family_names": family or None,
                            "credit_name": credit or None,
                            "other_names": text_list(
                                row.get("other-name"), limit=20
                            ),
                            "public_emails": text_list(
                                row.get("email"), limit=10
                            ),
                            "institutions": text_list(
                                row.get("institution-name"), limit=20
                            ),
                            "candidate_only": not exact,
                            "identity_inference_prohibited": not exact,
                            "public_profile_data": True,
                        },
                    )
                )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records[: query.limit],
                metadata={
                    "records_found": len(records[: query.limit]),
                    "anonymous_public_api": True,
                    "candidate_only": not exact,
                },
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

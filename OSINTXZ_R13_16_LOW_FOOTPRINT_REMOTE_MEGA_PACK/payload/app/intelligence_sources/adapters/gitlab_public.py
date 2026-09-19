from __future__ import annotations

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result


class GitLabPublicUserAdapter(RemoteSourceAdapter):
    API = "https://gitlab.com/api/v4/users"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 GitLabPublicUser",
        )

    @property
    def source_code(self) -> str:
        return "gitlab_public_user"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"username", "gitlab_username"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        username = query.value.strip().lstrip("@")
        if not username or len(username) > 255:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="Malformed GitLab username.",
            )
        try:
            payload = self.client.request_json(
                "GET",
                self.API,
                params={"username": username, "per_page": min(query.limit, 20)},
                timeout=query.timeout,
                max_bytes=1_500_000,
            )
            rows = payload if isinstance(payload, list) else []
            records: list[RemoteSourceRecord] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                login = str(row.get("username") or "").strip()
                if not login:
                    continue
                records.append(
                    RemoteSourceRecord(
                        source=self.source_code,
                        record_id=str(row.get("id") or login),
                        record_type="public_account",
                        display_name=str(row.get("name") or login),
                        source_url=str(row.get("web_url") or f"https://gitlab.com/{login}"),
                        identifiers={"GITLAB_USERNAME": login},
                        attributes={
                            "username": login,
                            "name": row.get("name"),
                            "public_email": row.get("public_email"),
                            "state": row.get("state"),
                            "created_at": row.get("created_at"),
                            "location": row.get("location"),
                            "organization": row.get("organization"),
                            "bio": row.get("bio"),
                            "website_url": row.get("website_url"),
                            "job_title": row.get("job_title"),
                            "account_identity_only": True,
                            "person_identity_inference_prohibited": True,
                            "public_profile_data": True,
                            "raw_response_stored": False,
                        },
                    )
                )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records[: query.limit],
                metadata={"records_found": len(records[: query.limit]), "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

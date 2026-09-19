from __future__ import annotations

from urllib.parse import quote

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result


class GitHubPublicUserAdapter(RemoteSourceAdapter):
    API = "https://api.github.com/users"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 GitHubPublicUser",
            extra_headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
        )

    @property
    def source_code(self) -> str:
        return "github_public_user"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"username", "github_username"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        username = query.value.strip().lstrip("@")
        if not username or "/" in username or len(username) > 100:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="Malformed GitHub username.",
            )
        try:
            payload = self.client.request_json(
                "GET",
                f"{self.API}/{quote(username, safe='')}",
                timeout=query.timeout,
                max_bytes=1_000_000,
            )
            if not isinstance(payload, dict):
                return RemoteAdapterResult(
                    source=self.source_code,
                    status=RemoteAdapterStatus.FAILED,
                    error="GitHub response must be an object.",
                )
            login = str(payload.get("login") or "").strip()
            if not login:
                return RemoteAdapterResult(
                    source=self.source_code,
                    status=RemoteAdapterStatus.SUCCESS,
                    records=[],
                )
            record = RemoteSourceRecord(
                source=self.source_code,
                record_id=str(payload.get("id") or login),
                record_type="public_account",
                display_name=str(payload.get("name") or login),
                source_url=str(payload.get("html_url") or f"https://github.com/{login}"),
                identifiers={"GITHUB_USERNAME": login},
                attributes={
                    "login": login,
                    "name": payload.get("name"),
                    "company": payload.get("company"),
                    "blog": payload.get("blog"),
                    "location": payload.get("location"),
                    "public_email": payload.get("email"),
                    "bio": payload.get("bio"),
                    "twitter_username": payload.get("twitter_username"),
                    "public_repos": payload.get("public_repos"),
                    "public_gists": payload.get("public_gists"),
                    "followers": payload.get("followers"),
                    "following": payload.get("following"),
                    "created_at": payload.get("created_at"),
                    "updated_at": payload.get("updated_at"),
                    "account_identity_only": True,
                    "person_identity_inference_prohibited": True,
                    "public_profile_data": True,
                    "raw_response_stored": False,
                },
            )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=[record],
                metadata={"records_found": 1, "no_local_cache": True},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return RemoteAdapterResult(
                    source=self.source_code,
                    status=RemoteAdapterStatus.SUCCESS,
                    records=[],
                    metadata={"records_found": 0},
                )
            return failure_result(self.source_code, exc)
        except Exception as exc:
            return failure_result(self.source_code, exc)

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)


_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubSecretScanningClient:
    """Read authorised GitHub secret-scanning alert metadata with secrets hidden."""

    API_BASE_URL = "https://api.github.com"
    API_VERSION = "2026-03-10"
    MAX_JSON_BYTES = 4_000_000

    def __init__(
        self,
        *,
        token: str | None,
        transport=None,
        user_agent: str = "OSINTXZ/1.0 ExposureIntelligence",
    ) -> None:
        self.token = (token or "").strip() or None
        self.transport = transport
        self.user_agent = user_agent.strip() or "OSINTXZ/1.0 ExposureIntelligence"

    @property
    def configured(self) -> bool:
        return self.token is not None

    def list_repository_alerts(
        self,
        repository: str,
        *,
        limit: int = 20,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        if not self.token:
            raise RuntimeError("GitHub token is not configured.")
        repository = (repository or "").strip()
        if not _REPOSITORY_RE.fullmatch(repository):
            raise ValueError("Repository must use owner/name format.")
        owner, repo = repository.split("/", 1)
        path = f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/secret-scanning/alerts"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": self.API_VERSION,
            "User-Agent": self.user_agent,
            "Accept-Encoding": "identity",
        }
        with httpx.Client(
            base_url=self.API_BASE_URL,
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers=headers,
            follow_redirects=False,
        ) as client:
            with client.stream(
                "GET",
                path,
                params={
                    "per_page": min(max(int(limit), 1), 100),
                    "hide_secret": "true",
                },
            ) as response:
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ValueError("Unexpected GitHub response content encoding.")
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(body) + len(chunk) > self.MAX_JSON_BYTES:
                        raise ValueError("GitHub secret-scanning response exceeds download limit.")
                    body.extend(chunk)
                response.raise_for_status()

        try:
            payload = httpx.Response(200, content=bytes(body)).json()
        except ValueError as exc:
            raise ValueError("GitHub secret-scanning response must be valid JSON.") from exc
        if not isinstance(payload, list):
            raise ValueError("GitHub secret-scanning response must be a JSON list.")
        return [item for item in payload if isinstance(item, dict)][: int(limit)]


class GitHubSecretScanningAdapter(RemoteSourceAdapter):
    def __init__(self, *, client: GitHubSecretScanningClient) -> None:
        self.client = client

    @property
    def source_code(self) -> str:
        return "github_secret_scanning"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"repository_secret_exposure"})

    @property
    def configured(self) -> bool:
        return self.client.configured

    @property
    def automatic_enabled(self) -> bool:
        return False

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.supports(query):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED)
        if not query.verified_scope:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_SUPPORTED,
                error="Verified repository scope is required for GitHub secret scanning.",
                metadata={"verified_scope_required": True},
            )
        if not self.configured:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_CONFIGURED,
                error="GitHub token is not configured.",
                metadata={"credentials_required": True},
            )

        try:
            rows = self.client.list_repository_alerts(
                query.value,
                limit=query.limit,
                timeout=query.timeout,
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code in {401, 403}:
                return RemoteAdapterResult(
                    self.source_code,
                    RemoteAdapterStatus.FAILED,
                    error=f"GitHub secret scanning access rejected (HTTP {code}).",
                    metadata={"retryable": False, "access_rejected": True},
                )
            if code == 404:
                return RemoteAdapterResult(
                    self.source_code,
                    RemoteAdapterStatus.NOT_SUPPORTED,
                    error=(
                        "Repository is unavailable to the token or secret scanning is not enabled/eligible."
                    ),
                    metadata={"eligible_or_accessible": False},
                )
            retryable = code == 429 or code >= 500
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"GitHub HTTP {code}.",
                metadata={"retryable": retryable, "rate_limited": code == 429},
            )
        except httpx.RequestError as exc:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL,
                error=str(exc),
                metadata={"retryable": True},
            )
        except Exception as exc:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.FAILED,
                error=str(exc),
                metadata={"failure_isolated": True},
            )

        records: list[RemoteSourceRecord] = []
        for row in rows:
            number = row.get("number")
            if number is None:
                continue
            first_location = row.get("first_location_detected")
            if not isinstance(first_location, dict):
                first_location = {}
            secret_type = str(row.get("secret_type") or "unknown").strip() or "unknown"
            display_type = str(row.get("secret_type_display_name") or secret_type).strip()
            records.append(
                RemoteSourceRecord(
                    source=self.source_code,
                    record_id=f"{query.value.casefold()}#{number}",
                    record_type="secret_scanning_alert",
                    display_name=f"GitHub secret alert · {display_type}",
                    source_url=str(row.get("html_url") or "").strip() or None,
                    identifiers={
                        "REPOSITORY": query.value,
                        "ALERT_NUMBER": str(number),
                    },
                    attributes={
                        "repository": query.value,
                        "alert_number": number,
                        "state": row.get("state"),
                        "resolution": row.get("resolution"),
                        "created_at": row.get("created_at"),
                        "resolved_at": row.get("resolved_at"),
                        "secret_type": secret_type,
                        "secret_type_display_name": display_type,
                        "validity": row.get("validity"),
                        "publicly_leaked": row.get("publicly_leaked"),
                        "multi_repo": row.get("multi_repo"),
                        "is_base64_encoded": row.get("is_base64_encoded"),
                        "push_protection_bypassed": row.get("push_protection_bypassed"),
                        "first_location_path": first_location.get("path"),
                        "first_location_commit_sha": first_location.get("commit_sha"),
                        "credential_exposed": True,
                        "secret_material_present": True,
                        "secret_hidden_at_provider": True,
                        "literal_secret_returned": False,
                        "verified_scope": True,
                        "identity_confirmed": False,
                        "raw_secret_values_stored": False,
                    },
                )
            )

        return RemoteAdapterResult(
            self.source_code,
            RemoteAdapterStatus.SUCCESS,
            records=records,
            metadata={
                "records_found": len(records),
                "verified_scope": True,
                "hide_secret_requested": True,
                "literal_secret_returned": False,
                "raw_secret_values_stored": False,
            },
        )

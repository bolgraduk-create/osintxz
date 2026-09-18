from __future__ import annotations

import time
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)


class IntelligenceXConfigurationError(RuntimeError):
    pass


class IntelligenceXSearchError(RuntimeError):
    pass


class IntelligenceXSearchClient:
    """Bounded metadata-only client for the Intelligence X Search API.

    The client deliberately uses only the search lifecycle endpoints. It never
    calls file/read, file/view, file/preview, export ZIP, or other endpoints that
    retrieve the underlying indexed document contents.
    """

    OFFICIAL_HOSTS = frozenset({
        "2.intelx.io",
        "3.intelx.io",
        "free.intelx.io",
        "public.intelx.io",
    })

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = "https://2.intelx.io",
        transport=None,
        sleep_fn: Callable[[float], None] = time.sleep,
        poll_interval: float = 0.25,
        max_polls: int = 40,
        user_agent: str = "OSINTXZ/1.0 ExposureIntelligence",
    ) -> None:
        self.api_key = (api_key or "").strip() or None
        self.base_url = self._normalize_base_url(base_url)
        self.transport = transport
        self.sleep_fn = sleep_fn
        self.poll_interval = max(float(poll_interval), 0.0)
        self.max_polls = max(int(max_polls), 1)
        self.user_agent = user_agent

    @property
    def configured(self) -> bool:
        return self.api_key is not None

    @classmethod
    def _normalize_base_url(cls, value: str) -> str:
        raw = (value or "").strip().rstrip("/")
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or host not in cls.OFFICIAL_HOSTS:
            raise IntelligenceXConfigurationError(
                "Intelligence X API URL must use HTTPS and an official IntelX API host."
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise IntelligenceXConfigurationError("Malformed Intelligence X API URL.")
        return f"https://{host}"

    def search_metadata(
        self,
        term: str,
        *,
        limit: int = 20,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            raise IntelligenceXConfigurationError(
                "Intelligence X API key is not configured."
            )
        term = (term or "").strip()
        if not term:
            raise ValueError("Intelligence X search term must not be empty.")
        if not 1 <= int(limit) <= 100:
            raise ValueError("Intelligence X limit must be 1..100.")

        headers = {
            "Accept": "application/json",
            "X-Key": self.api_key,
            "User-Agent": self.user_agent,
        }
        search_id: str | None = None
        complete = False
        records: list[dict[str, Any]] = []
        seen: set[str] = set()

        with httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers=headers,
            follow_redirects=False,
        ) as client:
            response = client.post(
                f"{self.base_url}/intelligent/search",
                json={
                    "term": term,
                    "buckets": [],
                    "lookuplevel": 0,
                    "maxresults": int(limit),
                    "timeout": min(max(int(timeout), 1), 120),
                    "datefrom": "",
                    "dateto": "",
                    "sort": 4,
                    "media": 0,
                    "terminate": [],
                },
            )
            response.raise_for_status()
            payload = self._json_object(response, "search initialization")
            search_id = str(payload.get("id") or "").strip()
            if not search_id:
                raise IntelligenceXSearchError(
                    "Intelligence X did not return a search id."
                )

            try:
                for poll_index in range(self.max_polls):
                    result_response = client.get(
                        f"{self.base_url}/intelligent/search/result",
                        params={
                            "id": search_id,
                            "limit": int(limit),
                            "media": 0,
                            "previewlines": 0,
                        },
                    )
                    result_response.raise_for_status()
                    page = self._json_object(result_response, "search result")
                    status = self._status(page.get("status"))

                    rows = page.get("records", [])
                    if rows is None:
                        rows = []
                    if not isinstance(rows, list):
                        raise IntelligenceXSearchError(
                            "Intelligence X search result records must be a list."
                        )
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        key = str(
                            row.get("systemid")
                            or row.get("storageid")
                            or row.get("randomid")
                            or ""
                        ).strip()
                        if not key:
                            continue
                        if key in seen:
                            continue
                        seen.add(key)
                        records.append(row)
                        if len(records) >= int(limit):
                            break

                    if status == 1:
                        complete = True
                        break
                    if status == 2:
                        raise IntelligenceXSearchError(
                            "Intelligence X search id was not found."
                        )
                    if status == 4:
                        raise IntelligenceXSearchError(
                            "Intelligence X reported a search error."
                        )
                    if len(records) >= int(limit):
                        break
                    if status not in {0, 3}:
                        raise IntelligenceXSearchError(
                            f"Unexpected Intelligence X search status: {status}."
                        )
                    if poll_index + 1 < self.max_polls and self.poll_interval:
                        self.sleep_fn(self.poll_interval)
            finally:
                if search_id and not complete:
                    try:
                        client.get(
                            f"{self.base_url}/intelligent/search/terminate",
                            params={"id": search_id},
                        )
                    except httpx.HTTPError:
                        pass

        return records[: int(limit)]

    @staticmethod
    def _json_object(response: httpx.Response, label: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise IntelligenceXSearchError(
                f"Intelligence X {label} response must be JSON."
            ) from exc
        if not isinstance(payload, dict):
            raise IntelligenceXSearchError(
                f"Intelligence X {label} response must be an object."
            )
        return payload

    @staticmethod
    def _status(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise IntelligenceXSearchError(
                "Intelligence X search result is missing a valid status."
            ) from exc


class IntelligenceXMetadataAdapter(RemoteSourceAdapter):
    """Metadata-only exposure/search adapter.

    Search-result metadata can be retained as a lead. Indexed document contents
    are deliberately not fetched, previewed, exported, persisted or exposed.
    """

    def __init__(self, *, client: IntelligenceXSearchClient) -> None:
        self.client = client

    @property
    def source_code(self) -> str:
        return "intelligencex_search"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({
            "email",
            "domain",
            "url",
            "ip",
            "phone",
            "crypto_address",
            "breach_lookup",
            "darkweb_index",
        })

    @property
    def configured(self) -> bool:
        return self.client.configured

    @property
    def automatic_enabled(self) -> bool:
        # Contract/API usage must be explicitly selected by the Exposure layer.
        return False

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.supports(query):
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="Unsupported Intelligence X query.",
            )
        if not self.configured:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_CONFIGURED,
                error="Intelligence X API key is not configured.",
                metadata={"credentials_required": True},
            )

        try:
            rows = self.client.search_metadata(
                query.value,
                limit=query.limit,
                timeout=query.timeout,
            )
        except IntelligenceXConfigurationError as exc:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_CONFIGURED,
                error=str(exc),
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            retryable = code == 429 or code >= 500
            return RemoteAdapterResult(
                source=self.source_code,
                status=(
                    RemoteAdapterStatus.PARTIAL
                    if retryable
                    else RemoteAdapterStatus.FAILED
                ),
                error=f"Intelligence X HTTP {code}.",
                metadata={
                    "retryable": retryable,
                    "rate_limited": code == 429,
                    "credentials_invalid": code in {401, 403},
                },
            )
        except httpx.RequestError as exc:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.PARTIAL,
                error=str(exc),
                metadata={"retryable": True},
            )
        except Exception as exc:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.FAILED,
                error=str(exc),
                metadata={"failure_isolated": True},
            )

        records = [
            record
            for row in rows
            if (record := self._to_record(row)) is not None
        ]
        return RemoteAdapterResult(
            source=self.source_code,
            status=RemoteAdapterStatus.SUCCESS,
            records=records,
            metadata={
                "records_found": len(records),
                "metadata_only": True,
                "raw_content_fetched": False,
                "preview_fetched": False,
                "raw_secret_values_stored": False,
                "identity_confirmed": False,
                "lead_only": True,
            },
        )

    def _to_record(self, row: dict[str, Any]) -> RemoteSourceRecord | None:
        system_id = str(row.get("systemid") or "").strip()
        storage_id = str(row.get("storageid") or "").strip()
        record_id = system_id or storage_id
        if not record_id:
            return None

        bucket = str(row.get("bucket") or "").strip()
        bucket_h = str(row.get("bucketh") or "").strip()
        darkweb = bucket.casefold().startswith("darknet.") or "darknet" in bucket_h.casefold()
        record_type = "darkweb_index_hit" if darkweb else "intelx_index_hit"

        attributes = {
            "system_id": system_id or None,
            "storage_id": storage_id or None,
            "bucket": bucket or None,
            "bucket_label": bucket_h or None,
            "added": row.get("added"),
            "date": row.get("date"),
            "size": row.get("size"),
            "in_store": row.get("instore"),
            "access_level": row.get("accesslevel"),
            "access_level_label": row.get("accesslevelh"),
            "media": row.get("media"),
            "media_label": row.get("mediah"),
            "content_type": row.get("type"),
            "content_type_label": row.get("typeh"),
            "xscore": row.get("xscore"),
            "group": row.get("group"),
            "index_file": row.get("indexfile"),
            "candidate_only": True,
            "lead_only": True,
            "identity_confirmed": False,
            "darkweb_index_hit": darkweb,
            "metadata_only": True,
            "raw_content_fetched": False,
            "preview_fetched": False,
            "raw_secret_values_stored": False,
        }

        # Intentionally exclude upstream name/description/tags because they can
        # contain fragments of indexed leaked content or secret material.
        return RemoteSourceRecord(
            source=self.source_code,
            record_id=record_id,
            record_type=record_type,
            display_name=f"Intelligence X metadata hit {record_id[:12]}",
            source_url="https://intelx.io/",
            identifiers={"INTELX_SYSTEM_ID": system_id} if system_id else {},
            attributes=attributes,
        )

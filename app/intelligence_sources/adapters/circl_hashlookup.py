from __future__ import annotations

import re

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result


_HEX = re.compile(r"^[0-9a-fA-F]+$")


class CirclHashlookupAdapter(RemoteSourceAdapter):
    BASE = "https://hashlookup.circl.lu/lookup"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 CIRCLHashlookup",
        )

    @property
    def source_code(self) -> str:
        return "circl_hashlookup"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"hash", "md5", "sha1", "sha256"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip().upper()
        algorithm = self._algorithm(value)
        if algorithm is None:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="CIRCL hashlookup supports exact MD5, SHA-1 or SHA-256 values.",
            )
        try:
            payload = self.client.request_json(
                "GET",
                f"{self.BASE}/{algorithm}/{value}",
                timeout=query.timeout,
                max_bytes=1_000_000,
            )
            if not isinstance(payload, dict):
                return RemoteAdapterResult(source=self.source_code, status=RemoteAdapterStatus.SUCCESS)
            identifiers = {algorithm.upper().replace("SHA1", "SHA-1").replace("SHA256", "SHA-256"): value}
            for key, out_key in (("MD5", "MD5"), ("SHA-1", "SHA-1"), ("SHA-256", "SHA-256"), ("SHA-512", "SHA-512")):
                if payload.get(key):
                    identifiers[out_key] = str(payload[key])
            product = payload.get("ProductCode") if isinstance(payload.get("ProductCode"), dict) else {}
            os_info = payload.get("OpSystemCode") if isinstance(payload.get("OpSystemCode"), dict) else {}
            record = RemoteSourceRecord(
                source=self.source_code,
                record_id=f"{algorithm}:{value}",
                record_type="known_file_hash",
                display_name=str(payload.get("FileName") or value),
                source_url=f"https://hashlookup.circl.lu/lookup/{algorithm}/{value}",
                identifiers=identifiers,
                attributes={
                    "file_name": payload.get("FileName"),
                    "file_size": payload.get("FileSize"),
                    "source_dataset": payload.get("source") or payload.get("db"),
                    "database": payload.get("db"),
                    "trust": payload.get("hashlookup:trust"),
                    "product_name": product.get("ProductName"),
                    "product_version": product.get("ProductVersion"),
                    "application_type": product.get("ApplicationType"),
                    "os_name": os_info.get("OpSystemName"),
                    "known_file_context_only": True,
                    "maliciousness_inference_prohibited": True,
                    "public_data": True,
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

    @staticmethod
    def _algorithm(value: str) -> str | None:
        if not _HEX.fullmatch(value):
            return None
        return {32: "md5", 40: "sha1", 64: "sha256"}.get(len(value))

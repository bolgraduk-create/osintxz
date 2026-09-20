from __future__ import annotations

from time import perf_counter
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from app.intelligence_sources.adapters.contracts import RemoteSourceQuery
from app.intelligence_sources.contracts import IntelligenceAccessMode


_SECRET_MARKERS = (
    "password", "passwd", "token", "cookie", "secret", "private_key",
    "privatekey", "authorization", "credential", "session",
)


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= 3:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 40:
                out["_truncated"] = True
                break
            name = str(key)
            if any(marker in name.casefold() for marker in _SECRET_MARKERS):
                out[name] = "[REDACTED]"
            else:
                out[name] = _safe_value(item, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe_value(item, depth=depth + 1) for item in list(value)[:40]]
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:2000]


class FederatedSourceSearchWorker(QObject):
    """Run one bounded Federation search in a thread-owned service container."""

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        capability: str,
        value: str,
        country: str = "",
        source_code: str = "",
        verified_scope: bool = False,
        limit: int = 20,
        timeout: int = 30,
    ) -> None:
        super().__init__()
        self.capability = str(capability or "").strip().casefold()
        self.value = str(value or "").strip()
        self.country = str(country or "").strip().upper()
        self.source_code = str(source_code or "").strip().casefold()
        self.verified_scope = bool(verified_scope)
        self.limit = max(1, min(int(limit), 100))
        self.timeout = max(1, int(timeout))

    @Slot()
    def run(self) -> None:
        from app.core.service_container import ServiceContainer
        from app.database.session import create_session

        started = perf_counter()
        container = None
        session = None
        try:
            if not self.capability:
                raise ValueError("Federated search requires a capability.")
            if not self.value:
                raise ValueError("Federated search requires a target value.")
            if self.country and (len(self.country) != 2 or not self.country.isalpha()):
                raise ValueError("Country must be a two-letter ISO code or blank.")

            session = create_session()
            container = ServiceContainer(session)

            if self.source_code:
                adapter = container.remote_source_adapter_registry.get(self.source_code)
                if adapter is None:
                    raise ValueError(f"Unknown Federation source: {self.source_code}")
                descriptor = container.intelligence_source_catalog.get(self.source_code)
                if (
                    descriptor is not None
                    and descriptor.access_mode is IntelligenceAccessMode.VERIFIED_SCOPE
                    and not self.verified_scope
                ):
                    raise ValueError(
                        "This source requires verified scope. Confirm authorization before running it."
                    )
                sources = (self.source_code,)
            else:
                # Empty sources intentionally means the registry's safe automatic
                # set. Contract/verified-scope/Tor adapters that opt out of
                # automatic execution will not run unexpectedly.
                sources = ()

            query = RemoteSourceQuery(
                capability=self.capability,
                value=self.value,
                country=self.country or None,
                limit=self.limit,
                timeout=self.timeout,
                sources=sources,
                verified_scope=self.verified_scope,
            )
            result = container.remote_source_adapter_service.search(query)
            snapshot = self._snapshot_result(result)
            container.rollback()
            self.succeeded.emit({
                "snapshot": snapshot,
                "duration": perf_counter() - started,
            })
        except Exception as exc:
            try:
                if container is not None:
                    container.rollback()
                elif session is not None:
                    session.rollback()
            except Exception:
                pass
            self.failed.emit({
                "error": str(exc),
                "duration": perf_counter() - started,
                "capability": self.capability,
                "value": self.value,
                "country": self.country,
                "sourceCode": self.source_code,
            })
        finally:
            try:
                if container is not None:
                    container.close()
                elif session is not None:
                    session.close()
            except Exception:
                pass

    @classmethod
    def _snapshot_result(cls, result: Any) -> dict[str, Any]:
        query = getattr(result, "query", None)
        records = [cls._snapshot_record(item) for item in list(getattr(result, "records", ()) or ())]
        providers = [cls._snapshot_provider(item) for item in list(getattr(result, "provider_results", ()) or ())]
        successful = sum(1 for item in providers if item["status"] == "success")
        partial = sum(1 for item in providers if item["status"] == "partial")
        not_configured = sum(1 for item in providers if item["status"] == "not_configured")
        failed = sum(1 for item in providers if item["status"] == "failed")
        not_supported = sum(1 for item in providers if item["status"] == "not_supported")
        return {
            "hasRun": True,
            "status": "completed_with_errors" if failed or partial else "completed",
            "capability": str(getattr(query, "capability", "") or ""),
            "value": str(getattr(query, "value", "") or ""),
            "country": str(getattr(query, "country", "") or ""),
            "sources": list(getattr(query, "sources", ()) or ()),
            "verifiedScope": bool(getattr(query, "verified_scope", False)),
            "records": records,
            "providers": providers,
            "summary": {
                "records": len(records),
                "providers": len(providers),
                "successful": successful,
                "partial": partial,
                "notConfigured": not_configured,
                "failed": failed,
                "notSupported": not_supported,
            },
            "rawSecretValuesStored": False,
        }

    @staticmethod
    def _snapshot_record(record: Any) -> dict[str, Any]:
        identifiers = {
            str(key): str(value)
            for key, value in dict(getattr(record, "identifiers", {}) or {}).items()
            if value is not None and str(value).strip()
        }
        attributes = _safe_value(dict(getattr(record, "attributes", {}) or {}))
        if not isinstance(attributes, dict):
            attributes = {}
        detail_parts: list[str] = []
        for key, value in list(attributes.items())[:8]:
            if isinstance(value, (str, int, float, bool)) and str(value).strip():
                detail_parts.append(f"{str(key).replace('_', ' ').title()}: {value}")
        return {
            "id": f"{getattr(record, 'source', '')}:{getattr(record, 'record_id', '')}",
            "source": str(getattr(record, "source", "") or ""),
            "recordId": str(getattr(record, "record_id", "") or ""),
            "type": str(getattr(record, "record_type", "") or ""),
            "title": str(getattr(record, "display_name", "") or "Remote record"),
            "sourceUrl": str(getattr(record, "source_url", "") or ""),
            "country": str(getattr(record, "country", "") or ""),
            "identifiers": identifiers,
            "identifiersText": " · ".join(f"{key}: {value}" for key, value in identifiers.items()),
            "attributes": attributes,
            "detail": " · ".join(detail_parts)[:1000],
        }

    @staticmethod
    def _snapshot_provider(provider: Any) -> dict[str, Any]:
        records = list(getattr(provider, "records", ()) or ())
        metadata = _safe_value(dict(getattr(provider, "metadata", {}) or {}))
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            "source": str(getattr(provider, "source", "") or ""),
            "status": str(getattr(getattr(provider, "status", None), "value", None) or getattr(provider, "status", "") or ""),
            "records": len(records),
            "error": str(getattr(provider, "error", "") or ""),
            "metadata": metadata,
            "rawSecretValuesStored": False,
        }

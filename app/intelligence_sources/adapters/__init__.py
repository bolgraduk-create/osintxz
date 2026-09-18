"""Remote intelligence-source adapters."""

from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.registry import RemoteSourceAdapterRegistry
from app.intelligence_sources.adapters.service import RemoteSourceAdapterService

__all__ = [
    "RemoteAdapterResult",
    "RemoteAdapterStatus",
    "RemoteSourceAdapterRegistry",
    "RemoteSourceAdapterService",
    "RemoteSourceQuery",
    "RemoteSourceRecord",
]

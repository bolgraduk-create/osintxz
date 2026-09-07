"""Open-Web Discovery Layer public contracts."""

from app.osint.open_web.contracts import (
    OpenWebDocument, OpenWebProviderInfo, OpenWebQuery,
    OpenWebResult, OpenWebStatus,
)
from app.osint.open_web.provider import OpenWebProvider
from app.osint.open_web.registry import OpenWebProviderRegistry
from app.osint.open_web.service import OpenWebDiscoveryService

__all__ = [
    "OpenWebDocument", "OpenWebProvider", "OpenWebProviderInfo",
    "OpenWebProviderRegistry", "OpenWebQuery", "OpenWebResult",
    "OpenWebStatus", "OpenWebDiscoveryService",
]

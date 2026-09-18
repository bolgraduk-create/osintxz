"""Cross-subsystem intelligence source catalog and data-handling policy."""

from app.intelligence_sources.catalog import IntelligenceSourceCatalog
from app.intelligence_sources.contracts import (
    DataHandlingDecision,
    DataSensitivity,
    IntelligenceAccessMode,
    IntelligenceCost,
    IntelligenceDeliveryMode,
    IntelligenceSourceCategory,
    IntelligenceSourceDescriptor,
    IntelligenceSourceOrigin,
    IntelligenceTransport,
)
from app.intelligence_sources.policy import (
    IntelligenceDataPolicy,
    IntelligenceDataSanitizer,
    SanitizationResult,
)

__all__ = [
    "DataHandlingDecision",
    "DataSensitivity",
    "IntelligenceAccessMode",
    "IntelligenceCost",
    "IntelligenceDataPolicy",
    "IntelligenceDataSanitizer",
    "IntelligenceDeliveryMode",
    "IntelligenceSourceCatalog",
    "IntelligenceSourceCategory",
    "IntelligenceSourceDescriptor",
    "IntelligenceSourceOrigin",
    "IntelligenceTransport",
    "SanitizationResult",
]
from app.intelligence_sources.coverage import (
    RemoteSourceCoverage,
    SourceCoverageEntry,
    SourceImplementationStatus,
)
from app.intelligence_sources.builtin_sources import (
    MASSIVE_REMOTE_SOURCES,
    register_massive_remote_sources,
)


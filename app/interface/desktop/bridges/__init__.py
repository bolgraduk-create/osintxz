"""Python view-models exposed to the Qt Quick presentation layer."""

from app.interface.desktop.bridges.desktop_bridge import DesktopBridge
from app.interface.desktop.bridges.investigation_search_bridge import InvestigationSearchBridge
from app.interface.desktop.bridges.registry_center_bridge import RegistryCenterBridge
from app.interface.desktop.bridges.source_center_bridge import SourceCenterBridge

__all__ = [
    "DesktopBridge",
    "InvestigationSearchBridge",
    "RegistryCenterBridge",
    "SourceCenterBridge",
]

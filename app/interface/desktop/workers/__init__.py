"""Background workers used by the QML desktop interface."""

from app.interface.desktop.workers.osint_collection_worker import (
    OsintCollectionWorker,
)
from app.interface.desktop.workers.registry_search_worker import (
    RegistrySearchWorker,
)

__all__ = ["OsintCollectionWorker", "RegistrySearchWorker"]

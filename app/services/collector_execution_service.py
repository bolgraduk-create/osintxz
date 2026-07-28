"""
Collector execution service.

Executes collectors and starts investigation.

Responsibilities:

- execute collector
- store collected items
- start investigation runner

Does NOT:

- parse collector data
- analyze evidence
- generate AI reports
"""

from __future__ import annotations

from uuid import UUID

from app.services.collection_service import CollectionService
from app.services.investigation_runner import InvestigationRunner


class CollectorExecutionService:
    """
    Executes collectors.
    """

    def __init__(
        self,
        collection_service: CollectionService,
        investigation_runner: InvestigationRunner,
    ):
        self.collection_service = collection_service
        self.investigation_runner = investigation_runner

    def execute(
        self,
        collector,
        case_id: UUID,
        *args,
        **kwargs,
    ) -> None:
        """
        Execute collector.
        """

        collected_items = collector.collect(
            *args,
            **kwargs,
        )

        self.collection_service.store_items(
            case_id=case_id,
            items=collected_items,
        )

        self.investigation_runner.run(
            case_id,
        )
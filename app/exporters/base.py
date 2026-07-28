"""
Base exporter interface.

Defines contract for all report exporters.

Responsibilities:

- define export method
- provide exporter metadata

Does NOT:

- generate reports
- modify report data
- save investigation results
"""

from __future__ import annotations


from abc import ABC, abstractmethod

from typing import Any


from app.reporting.models import (
    InvestigationReport,
)



class BaseExporter(
    ABC
):
    """
    Abstract exporter interface.
    """


    # ==========================================================
    # Export
    # ==========================================================

    @abstractmethod
    def export(
        self,
        report: InvestigationReport,
    ) -> Any:
        """
        Export report.

        Must be implemented
        by concrete exporters.
        """

        raise NotImplementedError



    # ==========================================================
    # Metadata
    # ==========================================================

    @abstractmethod
    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Exporter metadata.
        """

        raise NotImplementedError
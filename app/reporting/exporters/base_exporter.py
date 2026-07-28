"""
Base report exporter.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from app.reporting.models import (
    InvestigationReport,
)


class BaseReportExporter(ABC):
    """
    Base class for all report exporters.
    """

    @abstractmethod
    def export(
        self,
        report: InvestigationReport,
    ) -> str:
        """
        Export report.

        Returns exported content.
        """
        raise NotImplementedError
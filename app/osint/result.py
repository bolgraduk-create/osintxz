"""
OSINT result models.

Universal result returned
by every OSINT connector.

Responsibilities:

- standardized connector output
- discovered objects
- execution metadata

Does NOT:

- store database models
- execute tools
- call AI
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any


class ResultStatus(str, Enum):
    """
    Connector execution status.
    """

    SUCCESS = "success"

    PARTIAL = "partial"

    FAILED = "failed"

    NOT_SUPPORTED = "not_supported"

    NOT_AVAILABLE = "not_available"


@dataclass(slots=True)
class OsintFinding:
    """
    Single discovered object.
    """

    category: str

    value: str

    confidence: float = 1.0

    source: str | None = None

    url: str | None = None

    reliability: float = 1.0

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(slots=True)
class OsintResult:
    """
    Universal connector result.
    """

    connector: str

    status: ResultStatus

    findings: list[OsintFinding] = field(
        default_factory=list,
    )

    raw_data: Any | None = None

    execution_time: float = 0.0

    error: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    @property
    def success(
        self,
    ) -> bool:
        """
        Returns True if execution succeeded.
        """

        return self.status in (
            ResultStatus.SUCCESS,
            ResultStatus.PARTIAL,
        )

    @property
    def total_findings(
        self,
    ) -> int:
        """
        Number of discovered objects.
        """

        return len(
            self.findings
        )

    def add_finding(
        self,
        finding: OsintFinding,
    ) -> None:
        """
        Append discovered object.
        """

        self.findings.append(
            finding
        )

    @classmethod
    def failed(
        cls,
        connector: str,
        error: str,
    ) -> "OsintResult":
        """
        Create failed connector result.
        """

        return cls(
            connector=connector,
            status=ResultStatus.FAILED,
            error=error,
        )

    @classmethod
    def success_result(
        cls,
        connector: str,
    ) -> "OsintResult":
        """
        Create successful empty result.
        """

        return cls(
            connector=connector,
            status=ResultStatus.SUCCESS,
        )

    @classmethod
    def partial_result(
        cls,
        connector: str,
        error: str | None = None,
    ) -> "OsintResult":
        """
        Create partially successful result.
        """

        return cls(
            connector=connector,
            status=ResultStatus.PARTIAL,
            error=error,
        )

    @classmethod
    def unsupported(
        cls,
        connector: str,
    ) -> "OsintResult":
        """
        Connector does not support target.
        """

        return cls(
            connector=connector,
            status=ResultStatus.NOT_SUPPORTED,
        )

    @classmethod
    def unavailable(
        cls,
        connector: str,
        error: str | None = None,
    ) -> "OsintResult":
        """
        External tool unavailable.
        """

        return cls(
            connector=connector,
            status=ResultStatus.NOT_AVAILABLE,
            error=error,
        )
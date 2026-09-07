"""
Investigation action result.

Represents the outcome of a workspace investigation action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(
    slots=True,
    frozen=True,
)
class InvestigationActionResult:
    """
    Result of an executed investigation action.
    """

    success: bool

    title: str

    message: str

    refresh_workspace: bool = True

    target_tab: str | None = None

    payload: dict[str, Any] | None = None

    @classmethod
    def success_result(
        cls,
        *,
        title: str,
        message: str,
        target_tab: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> "InvestigationActionResult":

        return cls(
            success=True,
            title=title,
            message=message,
            target_tab=target_tab,
            payload=payload,
        )

    @classmethod
    def error_result(
        cls,
        *,
        title: str,
        message: str,
    ) -> "InvestigationActionResult":

        return cls(
            success=False,
            title=title,
            message=message,
            refresh_workspace=False,
        )
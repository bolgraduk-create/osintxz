"""
Base investigation action handler.

Every investigation action is implemented as
an independent handler.

Responsibilities:

- execute one action
- return InvestigationActionResult

Does NOT:

- access UI
- contain dispatcher logic
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from app.application.investigation_action import (
    InvestigationActionRequest,
)

from app.application.investigation_action_result import (
    InvestigationActionResult,
)


class InvestigationActionHandler(
    ABC,
):
    """
    Base class for all investigation handlers.
    """

    @abstractmethod
    def execute(
        self,
        request: InvestigationActionRequest,
    ) -> InvestigationActionResult:
        """
        Execute investigation action.
        """
"""
Base controller.

Every desktop controller inherits
from this class.

Responsible for:

- storing application services
- common controller behaviour

Does NOT:

- access UI widgets directly
- access repositories
"""

from __future__ import annotations


class BaseController:
    """
    Base desktop controller.
    """

    def __init__(
        self,
        container,
    ) -> None:

        self.container = container
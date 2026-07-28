"""
Command line interface.

Provides user interaction layer.

Does NOT contain
application business logic.
"""

from __future__ import annotations


from typing import Any, Callable


from app.interface.base import (
    BaseInterface,
)



class CLIInterface(
    BaseInterface
):
    """
    Command line interface.
    """



    def __init__(
        self,
        handler: Callable | None = None,
    ):
        self.handler = handler



    # ==========================================================
    # Request handling
    # ==========================================================

    def handle(
        self,
        request: Any,
    ) -> Any:
        """
        Process user request.
        """


        if self.handler is None:

            return {

                "status":
                    "no_handler"

            }


        return self.handler(
            request
        )



    # ==========================================================
    # Input helper
    # ==========================================================

    def execute_command(
        self,
        command: str,
    ) -> Any:
        """
        Execute CLI command.
        """

        return self.handle(
            command
        )
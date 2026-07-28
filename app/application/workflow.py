"""
Investigation workflow engine.

Coordinates execution order
between application components.

Does NOT:

- perform analysis
- execute AI models
- generate reports
- export files
"""

from __future__ import annotations


from typing import Any, Callable



class InvestigationWorkflow:
    """
    Controls investigation execution flow.
    """



    def __init__(
        self,
        steps: list[Callable] | None = None,
    ):
        self.steps = (
            steps
            or []
        )



    # ==========================================================
    # Step management
    # ==========================================================

    def add_step(
        self,
        step: Callable,
    ) -> None:
        """
        Add workflow step.
        """

        self.steps.append(
            step
        )



    # ==========================================================
    # Execution
    # ==========================================================

    def execute(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute workflow steps.
        """


        result = data


        for step in self.steps:

            result = step(
                result
            )


        return result



    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Workflow metadata.
        """

        return {

            "type":
                "investigation_workflow",

            "version":
                "1.0",

        }
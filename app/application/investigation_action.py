"""
Investigation action definitions.

Provides a shared contract for actions initiated from
workspace views.

Responsible for:

- defining supported investigation actions;
- carrying action payloads between UI and application layers;
- validating basic request structure.

Does NOT:

- access database;
- execute business logic;
- contain UI logic;
- call controllers or services.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class InvestigationActionType(
    str,
    Enum,
):
    """
    Supported investigation workspace actions.
    """

    CREATE_EVIDENCE = "create_evidence"

    CREATE_ENTITY = "create_entity"

    ADD_TIMELINE_EVENT = "add_timeline_event"

    ANALYZE_WITH_AI = "analyze_with_ai"


@dataclass(
    slots=True,
    frozen=True,
)
class InvestigationActionRequest:
    """
    Immutable request for an investigation action.

    Attributes:
        action_type:
            Operation that must be performed.

        source_type:
            Workspace object that initiated the action.

        payload:
            Serialized source data.

        options:
            Additional action-specific parameters.
    """

    action_type: InvestigationActionType

    source_type: str

    payload: dict[str, Any]

    options: dict[str, Any] | None = None

    def __post_init__(
        self,
    ) -> None:
        """
        Validate and normalize request data.
        """

        normalized_source_type = str(
            self.source_type
        ).strip()

        if not normalized_source_type:

            raise ValueError(
                "source_type cannot be empty."
            )

        if not isinstance(
            self.payload,
            dict,
        ):

            raise TypeError(
                "payload must be a dictionary."
            )

        if (
            self.options is not None
            and not isinstance(
                self.options,
                dict,
            )
        ):

            raise TypeError(
                "options must be a dictionary or None."
            )

        object.__setattr__(
            self,
            "source_type",
            normalized_source_type,
        )

        object.__setattr__(
            self,
            "payload",
            dict(
                self.payload
            ),
        )

        if self.options is not None:

            object.__setattr__(
                self,
                "options",
                dict(
                    self.options
                ),
            )

    def option(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Return one optional action parameter.
        """

        if self.options is None:

            return default

        return self.options.get(
            key,
            default,
        )
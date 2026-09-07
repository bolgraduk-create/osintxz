"""
Message context selector.

Selects chronological messages surrounding one selected message.

Responsible for:

- sorting messages chronologically
- locating the selected message
- selecting preceding messages
- selecting following messages
- handling missing identifiers safely

Does NOT:

- access the database
- build prompts
- call AI providers
- modify workspace data
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class MessageContextSelector:
    """
    Selects chronological context around one message.
    """

    def __init__(
        self,
        *,
        previous_limit: int = 10,
        next_limit: int = 10,
    ) -> None:

        self.previous_limit = (
            self._normalize_limit(
                previous_limit,
                field_name="previous_limit",
            )
        )

        self.next_limit = (
            self._normalize_limit(
                next_limit,
                field_name="next_limit",
            )
        )

    # ==========================================================
    # Selection
    # ==========================================================

    def select(
        self,
        messages: list[dict[str, Any]],
        selected_message: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Select chronological messages before and after one message.
        """

        if not isinstance(
            messages,
            list,
        ):

            raise TypeError(
                "messages must be a list."
            )

        if not isinstance(
            selected_message,
            dict,
        ):

            raise TypeError(
                "selected_message must be a dictionary."
            )

        normalized_messages = [
            deepcopy(
                message
            )
            for message in messages
            if isinstance(
                message,
                dict,
            )
        ]

        normalized_messages.sort(
            key=self._message_sort_key
        )

        selected_index = self._find_selected_index(
            messages=normalized_messages,
            selected_message=selected_message,
        )

        if selected_index is None:

            return {
                "selected_message": deepcopy(
                    selected_message
                ),
                "previous_messages": [],
                "next_messages": [],
                "selected_index": None,
                "total_messages": len(
                    normalized_messages
                ),
                "found": False,
            }

        previous_start = max(
            0,
            selected_index
            - self.previous_limit,
        )

        next_end = min(
            len(
                normalized_messages
            ),
            selected_index
            + self.next_limit
            + 1,
        )

        previous_messages = (
            normalized_messages[
                previous_start:selected_index
            ]
        )

        next_messages = (
            normalized_messages[
                selected_index
                + 1:next_end
            ]
        )

        return {
            "selected_message": deepcopy(
                normalized_messages[
                    selected_index
                ]
            ),
            "previous_messages": previous_messages,
            "next_messages": next_messages,
            "selected_index": selected_index,
            "total_messages": len(
                normalized_messages
            ),
            "found": True,
        }

    # ==========================================================
    # Lookup
    # ==========================================================

    def _find_selected_index(
        self,
        *,
        messages: list[dict[str, Any]],
        selected_message: dict[str, Any],
    ) -> int | None:
        """
        Find the selected message using stable identifiers.
        """

        selected_id = self._normalize_compare_value(
            selected_message.get(
                "id"
            )
        )

        selected_external_id = (
            self._normalize_compare_value(
                selected_message.get(
                    "external_id"
                )
            )
        )

        selected_source_id = (
            self._normalize_compare_value(
                selected_message.get(
                    "source_id"
                )
            )
        )

        if selected_id:

            for index, message in enumerate(
                messages
            ):

                message_id = (
                    self._normalize_compare_value(
                        message.get(
                            "id"
                        )
                    )
                )

                if message_id == selected_id:

                    return index

        if selected_external_id:

            for index, message in enumerate(
                messages
            ):

                message_external_id = (
                    self._normalize_compare_value(
                        message.get(
                            "external_id"
                        )
                    )
                )

                message_source_id = (
                    self._normalize_compare_value(
                        message.get(
                            "source_id"
                        )
                    )
                )

                if (
                    message_external_id
                    == selected_external_id
                    and (
                        not selected_source_id
                        or message_source_id
                        == selected_source_id
                    )
                ):

                    return index

        selected_signature = (
            self._message_signature(
                selected_message
            )
        )

        if selected_signature:

            for index, message in enumerate(
                messages
            ):

                if (
                    self._message_signature(
                        message
                    )
                    == selected_signature
                ):

                    return index

        return None

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _message_sort_key(
        message: dict[str, Any],
    ) -> tuple[str, str, str]:
        """
        Return a stable chronological sorting key.
        """

        return (
            str(
                message.get(
                    "sent_at"
                )
                or ""
            ),
            str(
                message.get(
                    "external_id"
                )
                or ""
            ),
            str(
                message.get(
                    "id"
                )
                or ""
            ),
        )

    @staticmethod
    def _message_signature(
        message: dict[str, Any],
    ) -> tuple[str, ...] | None:
        """
        Build a fallback signature for messages without identifiers.
        """

        signature = (
            str(
                message.get(
                    "sent_at"
                )
                or ""
            ).strip(),
            str(
                message.get(
                    "sender"
                )
                or ""
            ).strip().casefold(),
            str(
                message.get(
                    "receiver"
                )
                or ""
            ).strip().casefold(),
            str(
                message.get(
                    "chat_name"
                )
                or ""
            ).strip().casefold(),
            str(
                message.get(
                    "text"
                )
                or ""
            ).strip(),
        )

        if not any(
            signature
        ):

            return None

        return signature

    @staticmethod
    def _normalize_compare_value(
        value: Any,
    ) -> str:
        """
        Normalize an identifier for comparison.
        """

        return str(
            value
            or ""
        ).strip().casefold()

    @staticmethod
    def _normalize_limit(
        value: int,
        *,
        field_name: str,
    ) -> int:
        """
        Validate a non-negative integer limit.
        """

        try:

            normalized_value = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                f"{field_name} must be an integer."
            ) from error

        if normalized_value < 0:

            raise ValueError(
                f"{field_name} cannot be negative."
            )

        return normalized_value
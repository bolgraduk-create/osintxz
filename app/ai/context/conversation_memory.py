"""
Conversation memory.

Stores a bounded in-memory conversation for one investigation.

Responsible for:

- storing user and assistant messages
- keeping conversations separated by case
- limiting retained history
- preparing recent messages for AI prompts
- clearing one case conversation or all conversations

Does NOT:

- access the database
- call AI providers
- render prompts
- contain Qt UI logic
- persist history between application restarts
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import UTC
from datetime import datetime
from typing import Any
from uuid import UUID


class ConversationMemory:
    """
    Bounded in-memory AI conversation storage.

    Each investigation has an independent conversation history.
    """

    USER_ROLE = "user"

    ASSISTANT_ROLE = "assistant"

    SYSTEM_ROLE = "system"

    ALLOWED_ROLES = {
        USER_ROLE,
        ASSISTANT_ROLE,
        SYSTEM_ROLE,
    }

    def __init__(
        self,
        *,
        max_messages_per_case: int = 12,
        max_message_characters: int = 6000,
    ) -> None:

        self.max_messages_per_case = (
            self._normalize_positive_integer(
                max_messages_per_case,
                field_name=(
                    "max_messages_per_case"
                ),
            )
        )

        self.max_message_characters = (
            self._normalize_positive_integer(
                max_message_characters,
                field_name=(
                    "max_message_characters"
                ),
            )
        )

        self._conversations: dict[
            str,
            deque[dict[str, Any]],
        ] = {}

    # ==========================================================
    # Adding messages
    # ==========================================================

    def add_user_message(
        self,
        case_id: str | UUID,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Add one user message to a case conversation.
        """

        return self.add_message(
            case_id=case_id,
            role=self.USER_ROLE,
            content=content,
            metadata=metadata,
        )

    def add_assistant_message(
        self,
        case_id: str | UUID,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Add one assistant response to a case conversation.
        """

        return self.add_message(
            case_id=case_id,
            role=self.ASSISTANT_ROLE,
            content=content,
            metadata=metadata,
        )

    def add_system_message(
        self,
        case_id: str | UUID,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Add one internal system-level conversation message.
        """

        return self.add_message(
            case_id=case_id,
            role=self.SYSTEM_ROLE,
            content=content,
            metadata=metadata,
        )

    def add_message(
        self,
        *,
        case_id: str | UUID,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Add one normalized message to a case conversation.
        """

        normalized_case_id = self._normalize_case_id(
            case_id
        )

        normalized_role = self._normalize_role(
            role
        )

        normalized_content = self._normalize_content(
            content
        )

        normalized_metadata = (
            deepcopy(
                metadata
            )
            if isinstance(
                metadata,
                dict,
            )
            else {}
        )

        message = {
            "role": normalized_role,
            "content": normalized_content,
            "created_at": datetime.now(
                UTC
            ).isoformat(),
            "metadata": normalized_metadata,
        }

        conversation = self._get_or_create_conversation(
            normalized_case_id
        )

        conversation.append(
            message
        )

        return deepcopy(
            message
        )

    # ==========================================================
    # Reading history
    # ==========================================================

    def get_history(
        self,
        case_id: str | UUID,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return a defensive copy of conversation history.
        """

        normalized_case_id = self._normalize_case_id(
            case_id
        )

        conversation = self._conversations.get(
            normalized_case_id
        )

        if conversation is None:

            return []

        history = list(
            conversation
        )

        if limit is not None:

            normalized_limit = (
                self._normalize_positive_integer(
                    limit,
                    field_name="limit",
                )
            )

            history = history[
                -normalized_limit:
            ]

        return deepcopy(
            history
        )

    def get_prompt_history(
        self,
        case_id: str | UUID,
        *,
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        """
        Return compact history suitable for an AI prompt.

        Metadata and timestamps are intentionally omitted.
        """

        history = self.get_history(
            case_id,
            limit=limit,
        )

        return [
            {
                "role": str(
                    message.get(
                        "role"
                    )
                    or ""
                ),
                "content": str(
                    message.get(
                        "content"
                    )
                    or ""
                ),
            }
            for message in history
        ]

    def get_last_message(
        self,
        case_id: str | UUID,
    ) -> dict[str, Any] | None:
        """
        Return the most recent conversation message.
        """

        history = self.get_history(
            case_id,
            limit=1,
        )

        if not history:

            return None

        return history[0]

    # ==========================================================
    # Conversation state
    # ==========================================================

    def has_history(
        self,
        case_id: str | UUID,
    ) -> bool:
        """
        Return whether a case has stored conversation messages.
        """

        normalized_case_id = self._normalize_case_id(
            case_id
        )

        conversation = self._conversations.get(
            normalized_case_id
        )

        return bool(
            conversation
        )

    def count(
        self,
        case_id: str | UUID,
    ) -> int:
        """
        Return the number of stored messages for one case.
        """

        normalized_case_id = self._normalize_case_id(
            case_id
        )

        conversation = self._conversations.get(
            normalized_case_id
        )

        if conversation is None:

            return 0

        return len(
            conversation
        )

    # ==========================================================
    # Clearing history
    # ==========================================================

    def clear_case(
        self,
        case_id: str | UUID,
    ) -> bool:
        """
        Remove conversation history for one case.
        """

        normalized_case_id = self._normalize_case_id(
            case_id
        )

        if normalized_case_id not in self._conversations:

            return False

        del self._conversations[
            normalized_case_id
        ]

        return True

    def clear_all(
        self,
    ) -> None:
        """
        Remove all conversation histories.
        """

        self._conversations.clear()

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return conversation-memory information.
        """

        return {
            "type": "conversation_memory",
            "storage": "in_memory",
            "max_messages_per_case": (
                self.max_messages_per_case
            ),
            "max_message_characters": (
                self.max_message_characters
            ),
            "active_conversations": len(
                self._conversations
            ),
            "message_counts": {
                case_id: len(
                    conversation
                )
                for case_id, conversation
                in self._conversations.items()
            },
        }

    # ==========================================================
    # Internal helpers
    # ==========================================================

    def _get_or_create_conversation(
        self,
        case_id: str,
    ) -> deque[dict[str, Any]]:
        """
        Return or create a bounded case conversation.
        """

        conversation = self._conversations.get(
            case_id
        )

        if conversation is None:

            conversation = deque(
                maxlen=(
                    self.max_messages_per_case
                )
            )

            self._conversations[
                case_id
            ] = conversation

        return conversation

    def _normalize_content(
        self,
        content: str,
    ) -> str:
        """
        Validate and truncate conversation content.
        """

        normalized_content = str(
            content
            or ""
        ).strip()

        if not normalized_content:

            raise ValueError(
                "Conversation content cannot be empty."
            )

        if (
            len(
                normalized_content
            )
            <= self.max_message_characters
        ):

            return normalized_content

        omitted_count = (
            len(
                normalized_content
            )
            - self.max_message_characters
        )

        suffix = (
            "\n\n"
            f"[Truncated {omitted_count} characters]"
        )

        available_length = max(
            0,
            self.max_message_characters
            - len(
                suffix
            ),
        )

        return (
            normalized_content[
                :available_length
            ]
            + suffix
        )

    @classmethod
    def _normalize_role(
        cls,
        role: str,
    ) -> str:
        """
        Validate a conversation role.
        """

        normalized_role = str(
            role
            or ""
        ).strip().lower()

        if normalized_role not in cls.ALLOWED_ROLES:

            allowed_roles = ", ".join(
                sorted(
                    cls.ALLOWED_ROLES
                )
            )

            raise ValueError(
                "Unsupported conversation role: "
                f"{normalized_role!r}. "
                f"Allowed roles: {allowed_roles}."
            )

        return normalized_role

    @staticmethod
    def _normalize_case_id(
        case_id: str | UUID,
    ) -> str:
        """
        Normalize a case identifier.
        """

        normalized_case_id = str(
            case_id
            or ""
        ).strip()

        if not normalized_case_id:

            raise ValueError(
                "case_id cannot be empty."
            )

        return normalized_case_id

    @staticmethod
    def _normalize_positive_integer(
        value: int,
        *,
        field_name: str,
    ) -> int:
        """
        Validate a positive integer.
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

        if normalized_value <= 0:

            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return normalized_value
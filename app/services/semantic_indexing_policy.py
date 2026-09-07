"""
Semantic indexing policy.

Defines which SearchIndex records are useful enough
to receive semantic vector representations.

The policy is deliberately independent from:

- embedding providers
- pgvector
- semantic retrieval
- rank fusion
- UI

Its only responsibility is deciding whether a textual
search representation is meaningful enough for semantic
indexing.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.models.search_index import (
    SearchIndex,
)


# ==========================================================
# Decision
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SemanticIndexingDecision:
    """
    Result of semantic indexing policy evaluation.
    """

    allowed: bool

    reason: str

    text_length: int = 0

    word_count: int = 0


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SemanticIndexingPolicyConfig:
    """
    Semantic indexing policy configuration.

    minimum_text_length:
        Minimum number of meaningful characters.

    minimum_word_count:
        Minimum number of textual tokens.

    message_minimum_text_length:
        Messages are especially noisy, so they use
        a slightly stronger minimum length threshold.

    message_minimum_word_count:
        Minimum token count for messages.

    skip_numeric_only:
        Skip strings containing only numbers and
        punctuation.

    skip_symbol_only:
        Skip strings without letters or digits.
    """

    minimum_text_length: int = 3

    minimum_word_count: int = 1

    message_minimum_text_length: int = 4

    message_minimum_word_count: int = 1

    skip_numeric_only: bool = True

    skip_symbol_only: bool = True

    skip_low_information_reactions: bool = True

    def __post_init__(
        self,
    ) -> None:

        if self.minimum_text_length < 1:

            raise ValueError(
                "minimum_text_length must "
                "be at least 1."
            )

        if self.minimum_word_count < 1:

            raise ValueError(
                "minimum_word_count must "
                "be at least 1."
            )

        if (
            self.message_minimum_text_length
            < 1
        ):

            raise ValueError(
                "message_minimum_text_length "
                "must be at least 1."
            )

        if (
            self.message_minimum_word_count
            < 1
        ):

            raise ValueError(
                "message_minimum_word_count "
                "must be at least 1."
            )


# ==========================================================
# Policy
# ==========================================================


class SemanticIndexingPolicy:
    """
    Determines whether a SearchIndex should receive
    a semantic embedding.
    """

    _WORD_PATTERN = re.compile(
        r"\b[\w'-]+\b",
        flags=re.UNICODE,
    )

    _LETTER_PATTERN = re.compile(
        r"[^\W\d_]",
        flags=re.UNICODE,
    )

    _ALPHANUMERIC_PATTERN = re.compile(
        r"\w",
        flags=re.UNICODE,
    )

    _LOW_INFORMATION_REACTION_PATTERN = re.compile(
        r"^(?:"
        r"ха(?:ха)*"
        r"|ах(?:ах)*а?"
        r"|хех(?:е|ех)*"
        r"|лол+"
        r"|кек+"
        r"|мм+"
        r"|мда+"
        r"|угу+"
        r")$",
        flags=re.IGNORECASE | re.UNICODE,
    )

    def __init__(
        self,
        config: (
            SemanticIndexingPolicyConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or SemanticIndexingPolicyConfig()
        )

    # ======================================================
    # Public API
    # ======================================================

    def evaluate(
        self,
        index: SearchIndex,
        text: str,
    ) -> SemanticIndexingDecision:
        """
        Decide whether the provided representation should
        receive a semantic embedding.
        """

        object_type = (
            self._object_type(
                index
            )
        )

        evaluation_text = text

        if object_type == "message":

            evaluation_text = (
                self._extract_message_text(
                    index
                )
            )

        normalized = (
            self._normalize_text(
                evaluation_text
            )
        )

        if not normalized:

            return SemanticIndexingDecision(
                allowed=False,
                reason="empty_text",
            )

        text_length = len(
            normalized
        )

        words = (
            self._extract_words(
                normalized
            )
        )

        word_count = len(
            words
        )


        # --------------------------------------------------
        # Symbol-only noise
        # --------------------------------------------------

        if (
            self.config.skip_symbol_only
            and not self._ALPHANUMERIC_PATTERN.search(
                normalized
            )
        ):

            return SemanticIndexingDecision(
                allowed=False,
                reason="symbol_only",
                text_length=text_length,
                word_count=word_count,
            )

        # --------------------------------------------------
        # Numeric-only noise
        # --------------------------------------------------

        if (
            self.config.skip_numeric_only
            and not self._LETTER_PATTERN.search(
                normalized
            )
        ):

            return SemanticIndexingDecision(
                allowed=False,
                reason="numeric_only",
                text_length=text_length,
                word_count=word_count,
            )

        # --------------------------------------------------
        # Low-information reactions
        # --------------------------------------------------

        if (
            self.config.skip_low_information_reactions
            and self._LOW_INFORMATION_REACTION_PATTERN.fullmatch(
                normalized
            )
        ):

            return SemanticIndexingDecision(
                allowed=False,
                reason="low_information_reaction",
                text_length=text_length,
                word_count=word_count,
            )

        # --------------------------------------------------
        # Messages
        # --------------------------------------------------

        if object_type == "message":

            if (
                text_length
                < self.config
                .message_minimum_text_length
            ):

                return SemanticIndexingDecision(
                    allowed=False,
                    reason="message_too_short",
                    text_length=text_length,
                    word_count=word_count,
                )

            if (
                word_count
                < self.config
                .message_minimum_word_count
            ):

                return SemanticIndexingDecision(
                    allowed=False,
                    reason=(
                        "message_too_few_words"
                    ),
                    text_length=text_length,
                    word_count=word_count,
                )

        # --------------------------------------------------
        # Other searchable objects
        # --------------------------------------------------

        else:

            if (
                text_length
                < self.config
                .minimum_text_length
            ):

                return SemanticIndexingDecision(
                    allowed=False,
                    reason="text_too_short",
                    text_length=text_length,
                    word_count=word_count,
                )

            if (
                word_count
                < self.config
                .minimum_word_count
            ):

                return SemanticIndexingDecision(
                    allowed=False,
                    reason="too_few_words",
                    text_length=text_length,
                    word_count=word_count,
                )

        # --------------------------------------------------
        # Accepted
        # --------------------------------------------------

        return SemanticIndexingDecision(
            allowed=True,
            reason="accepted",
            text_length=text_length,
            word_count=word_count,
        )

    def should_index(
        self,
        index: SearchIndex,
        text: str,
    ) -> bool:
        """
        Convenience boolean API.
        """

        return self.evaluate(
            index,
            text,
        ).allowed

    # ======================================================
    # Helpers
    # ======================================================

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        """
        Normalize whitespace for policy evaluation.
        """

        return " ".join(
            str(
                text
            ).split()
        ).strip()

    @classmethod
    def _extract_words(
        cls,
        text: str,
    ) -> list[str]:
        """
        Extract lightweight Unicode-aware word tokens.
        """

        return cls._WORD_PATTERN.findall(
            text
        )

    @staticmethod
    def _object_type(
        index: SearchIndex,
    ) -> str:
        """
        Normalize SearchIndex object type.
        """

        value = (
            index.object_type.value
            if hasattr(
                index.object_type,
                "value",
            )
            else str(
                index.object_type
            )
        )

        return (
            value
            .strip()
            .lower()
        )

    @staticmethod
    def _extract_message_text(
        index: SearchIndex,
    ) -> str:
        """
        Extract actual message body from structured
        SearchIndex content.

        Technical metadata such as sender, timestamps,
        external IDs and JSON metadata must not influence
        the semantic indexing policy.
        """

        content = (
            index.content
            or ""
        )

        marker = "MESSAGE_TEXT:\n"

        start = content.find(
            marker
        )

        if start < 0:

            # Old SearchIndex format.
            #
            # We intentionally do not try to guess which
            # fragment is the real message because the old
            # representation mixed text and metadata.
            return ""

        start += len(
            marker
        )

        remaining = content[
            start:
        ]

        end = remaining.find(
            "\n\n"
        )

        if end >= 0:

            remaining = remaining[
                :end
            ]

        return remaining.strip()
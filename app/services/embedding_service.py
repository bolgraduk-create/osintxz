"""
Embedding service contracts.

Defines the common abstraction used by semantic search
and vector indexing.

Architecture:

text
  ↓
EmbeddingService
  ↓
embedding vector
  ↓
pgvector / semantic retrieval

Concrete providers may use:

- Ollama
- local sentence-transformers
- another embedding backend in the future

The rest of the application must not depend directly
on a concrete embedding provider.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from math import isfinite
from typing import Sequence


@dataclass(
    frozen=True,
    slots=True,
)
class EmbeddingResult:
    """
    Result of one embedding operation.
    """

    vector: tuple[float, ...]

    model: str

    dimensions: int

    @classmethod
    def create(
        cls,
        *,
        vector: Sequence[float],
        model: str,
    ) -> "EmbeddingResult":
        """
        Validate and construct an embedding result.
        """

        normalized_model = (
            model.strip()
        )

        if not normalized_model:

            raise ValueError(
                "Embedding model cannot be empty."
            )

        values = tuple(
            float(value)
            for value in vector
        )

        if not values:

            raise ValueError(
                "Embedding vector cannot be empty."
            )

        for value in values:

            if not isfinite(
                value
            ):

                raise ValueError(
                    "Embedding vector values "
                    "must be finite."
                )

        return cls(
            vector=values,
            model=normalized_model,
            dimensions=len(
                values
            ),
        )


class EmbeddingService(
    ABC
):
    """
    Common embedding provider interface.

    Semantic search depends on this abstraction rather
    than directly on Ollama or another provider.
    """

    @property
    @abstractmethod
    def model_name(
        self,
    ) -> str:
        """
        Embedding model identifier.
        """

        raise NotImplementedError

    @abstractmethod
    def embed(
        self,
        text: str,
    ) -> EmbeddingResult:
        """
        Generate embedding for one text.
        """

        raise NotImplementedError

    def embed_many(
        self,
        texts: Sequence[str],
    ) -> list[
        EmbeddingResult
    ]:
        """
        Generate embeddings for several texts.

        Default implementation intentionally delegates
        to embed() so every provider immediately supports
        batch callers.

        Concrete providers may override this later with
        true batch inference.
        """

        return [
            self.embed(
                text
            )
            for text in texts
        ]

    @staticmethod
    def validate_text(
        text: str | None,
    ) -> str:
        """
        Validate text before embedding.
        """

        if text is None:

            raise ValueError(
                "Embedding text cannot be None."
            )

        normalized = (
            str(
                text
            )
            .strip()
        )

        if not normalized:

            raise ValueError(
                "Embedding text cannot be empty."
            )

        return normalized
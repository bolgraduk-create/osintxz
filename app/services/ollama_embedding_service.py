"""
Ollama embedding service.

Concrete EmbeddingService implementation backed by
a locally running Ollama server.

Architecture:

Semantic Search
      ↓
EmbeddingService
      ↑
OllamaEmbeddingService
      ↓
Ollama HTTP API
      ↓
local embedding model

Responsibilities:

- validate embedding input
- communicate with Ollama
- request local embeddings
- validate Ollama responses
- convert responses into EmbeddingResult
- support batch embedding requests

Does NOT:

- perform semantic retrieval
- access PostgreSQL
- know about pgvector
- perform rank fusion
- manage SearchIndex objects
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import requests

from app.services.embedding_service import (
    EmbeddingResult,
    EmbeddingService,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class OllamaEmbeddingConfig:
    """
    Ollama embedding configuration.
    """

    host: str = "http://localhost:11434"

    model: str = "nomic-embed-text"

    timeout_seconds: float = 60.0

    def __post_init__(
        self,
    ) -> None:

        normalized_host = (
            self.host
            .strip()
            .rstrip("/")
        )

        normalized_model = (
            self.model.strip()
        )

        if not normalized_host:

            raise ValueError(
                "Ollama host cannot be empty."
            )

        if not normalized_model:

            raise ValueError(
                "Ollama embedding model "
                "cannot be empty."
            )

        if (
            self.timeout_seconds
            <= 0.0
        ):

            raise ValueError(
                "Ollama timeout must be "
                "greater than zero."
            )

        object.__setattr__(
            self,
            "host",
            normalized_host,
        )

        object.__setattr__(
            self,
            "model",
            normalized_model,
        )


# ==========================================================
# Service
# ==========================================================


class OllamaEmbeddingService(
    EmbeddingService
):
    """
    Local Ollama embedding provider.
    """

    def __init__(
        self,
        config: OllamaEmbeddingConfig
        | None = None,
        *,
        session: requests.Session
        | None = None,
    ) -> None:

        self.config = (
            config
            or OllamaEmbeddingConfig()
        )

        self._session = (
            session
            or requests.Session()
        )

    # ======================================================
    # Provider information
    # ======================================================

    @property
    def model_name(
        self,
    ) -> str:

        return self.config.model

    # ======================================================
    # Single embedding
    # ======================================================

    def embed(
        self,
        text: str,
    ) -> EmbeddingResult:
        """
        Generate embedding for one text.
        """

        normalized_text = (
            self.validate_text(
                text
            )
        )

        results = self._request_embeddings(
            [
                normalized_text,
            ]
        )

        if len(
            results
        ) != 1:

            raise RuntimeError(
                "Ollama returned an unexpected "
                "number of embeddings."
            )

        return EmbeddingResult.create(
            vector=results[0],
            model=self.model_name,
        )

    # ======================================================
    # Batch embeddings
    # ======================================================

    def embed_many(
        self,
        texts: Sequence[str],
    ) -> list[
        EmbeddingResult
    ]:
        """
        Generate embeddings for several texts in one
        Ollama request when possible.
        """

        if not texts:

            return []

        normalized_texts = [
            self.validate_text(
                text
            )
            for text in texts
        ]

        vectors = (
            self._request_embeddings(
                normalized_texts
            )
        )

        if (
            len(
                vectors
            )
            != len(
                normalized_texts
            )
        ):

            raise RuntimeError(
                "Ollama returned an unexpected "
                "number of embeddings."
            )

        results = [
            EmbeddingResult.create(
                vector=vector,
                model=self.model_name,
            )
            for vector in vectors
        ]

        dimensions = {
            result.dimensions
            for result in results
        }

        if len(
            dimensions
        ) != 1:

            raise RuntimeError(
                "Ollama returned embeddings "
                "with inconsistent dimensions."
            )

        return results

    # ======================================================
    # HTTP request
    # ======================================================

    def _request_embeddings(
        self,
        texts: Sequence[str],
    ) -> list[
        list[
            float
        ]
    ]:
        """
        Request embeddings from Ollama.

        Modern Ollama API:

            POST /api/embed

        Body:

            {
                "model": "...",
                "input": [...]
            }
        """

        url = (
            f"{self.config.host}"
            "/api/embed"
        )

        payload = {
            "model": (
                self.model_name
            ),
            "input": list(
                texts
            ),
        }

        try:

            response = (
                self._session.post(
                    url,
                    json=payload,
                    timeout=(
                        self.config
                        .timeout_seconds
                    ),
                )
            )

        except requests.RequestException as error:

            raise RuntimeError(
                "Could not connect to Ollama "
                f"at {self.config.host}."
            ) from error

        if not response.ok:

            message = (
                response.text
                .strip()
            )

            if len(
                message
            ) > 500:

                message = (
                    message[
                        :500
                    ]
                    + "..."
                )

            raise RuntimeError(
                "Ollama embedding request "
                f"failed with HTTP "
                f"{response.status_code}: "
                f"{message}"
            )

        try:

            data = response.json()

        except ValueError as error:

            raise RuntimeError(
                "Ollama returned invalid JSON."
            ) from error

        embeddings = data.get(
            "embeddings"
        )

        if not isinstance(
            embeddings,
            list,
        ):

            raise RuntimeError(
                "Ollama response does not "
                "contain embeddings."
            )

        validated: list[
            list[
                float
            ]
        ] = []

        for vector in embeddings:

            if not isinstance(
                vector,
                list,
            ):

                raise RuntimeError(
                    "Ollama returned an invalid "
                    "embedding vector."
                )

            if not vector:

                raise RuntimeError(
                    "Ollama returned an empty "
                    "embedding vector."
                )

            try:

                numeric_vector = [
                    float(
                        value
                    )
                    for value in vector
                ]

            except (
                TypeError,
                ValueError,
            ) as error:

                raise RuntimeError(
                    "Ollama embedding contains "
                    "non-numeric values."
                ) from error

            validated.append(
                numeric_vector
            )

        return validated
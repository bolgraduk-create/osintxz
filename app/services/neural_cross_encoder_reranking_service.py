"""
Optional local neural cross-encoder reranking.

Architecture:

Mathematical ranked hits
        ↓
SearchResultGroupingService
        ↓
Top-N candidate window
        ↓
NeuralCrossEncoderRerankingService
        ↓
length-aware token buckets
        ↓
ONNX Cross-Encoder logits
        ↓
window normalization
        ↓
mathematical + neural combination
        ↓
scores.rerank
scores.final

The service is intentionally optional and fail-safe.
It performs local ONNX inference only and does not require
PyTorch or network access at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Any

from app.investigation.search_query import InvestigationSearchQuery
from app.investigation.search_result import InvestigationSearchHit
from app.services.search_index_field_extractor import (
    SearchIndexFieldExtractor,
    SearchIndexFields,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(frozen=True, slots=True)
class NeuralCrossEncoderRerankingConfig:
    """Configuration for local neural reranking."""

    model_directory: Path = Path(
        "storage/cache/models/mmarco-mMiniLMv2-L12-H384-v1"
    )
    model_filename: str = "onnx/model_quint8_avx2.onnx"
    model_identifier: str = (
        "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    )

    maximum_candidates: int = 30
    batch_size: int = 30
    max_length: int = 512
    max_document_chars: int = 12000

    # Candidates are bucketed by their already-tokenized pair
    # length before padding. This prevents one long document from
    # expanding an otherwise short batch to 512 tokens.
    length_bucket_boundaries: tuple[int, ...] = (
        32,
        64,
        128,
        256,
        384,
        512,
    )

    mathematical_weight: float = 0.75
    neural_weight: float = 0.25
    minimum_logit_range: float = 1e-8

    def __post_init__(self) -> None:
        if self.maximum_candidates < 1:
            raise ValueError(
                "maximum_candidates must be at least 1."
            )

        if self.batch_size < 1:
            raise ValueError(
                "batch_size must be at least 1."
            )

        if self.max_length < 8:
            raise ValueError(
                "max_length must be at least 8."
            )

        if self.max_document_chars < 1:
            raise ValueError(
                "max_document_chars must be at least 1."
            )

        boundaries = self.length_bucket_boundaries

        if not boundaries:
            raise ValueError(
                "length_bucket_boundaries cannot be empty."
            )

        if any(
            not isinstance(value, int) or value < 1
            for value in boundaries
        ):
            raise ValueError(
                "length bucket boundaries must be positive integers."
            )

        if tuple(sorted(set(boundaries))) != boundaries:
            raise ValueError(
                "length_bucket_boundaries must be strictly increasing."
            )

        if boundaries[-1] < self.max_length:
            raise ValueError(
                "The last length bucket boundary must be >= max_length."
            )

        for weight in (
            self.mathematical_weight,
            self.neural_weight,
        ):
            if not isfinite(weight):
                raise ValueError(
                    "Reranking weights must be finite."
                )

            if weight < 0.0:
                raise ValueError(
                    "Reranking weights cannot be negative."
                )

        if (
            self.mathematical_weight
            + self.neural_weight
            <= 0.0
        ):
            raise ValueError(
                "At least one reranking weight must be positive."
            )

        if (
            not isfinite(self.minimum_logit_range)
            or self.minimum_logit_range < 0.0
        ):
            raise ValueError(
                "minimum_logit_range must be finite and non-negative."
            )


# ==========================================================
# Internal candidate
# ==========================================================


@dataclass(slots=True)
class _NeuralCandidate:
    """Prepared neural candidate."""

    hit: InvestigationSearchHit
    pre_neural_rank: int
    mathematical_score: float
    document_text: str
    document_field: str
    token_length: int = 0
    length_bucket: int = 0


# ==========================================================
# Service
# ==========================================================


class NeuralCrossEncoderRerankingService:
    """Local ONNX cross-encoder reranker."""

    METADATA_KEY = "neural_reranking"
    MATHEMATICAL_METADATA_KEY = "mathematical_ranking"

    def __init__(
        self,
        config: NeuralCrossEncoderRerankingConfig | None = None,
        *,
        field_extractor: SearchIndexFieldExtractor | None = None,
    ) -> None:
        self.config = (
            config
            or NeuralCrossEncoderRerankingConfig()
        )

        self.field_extractor = (
            field_extractor
            or SearchIndexFieldExtractor()
        )

        # Lazy runtime.
        self._tokenizer: Any | None = None
        self._session: Any | None = None
        self._numpy: Any | None = None
        self._session_input_names: tuple[str, ...] = ()

        # Last-run status.
        self.last_error: str | None = None
        self.last_duration_seconds: float = 0.0
        self.last_reranked_count: int = 0
        self.last_candidate_count: int = 0
        self.last_loaded: bool = False
        self.last_batch_count: int = 0
        self.last_batch_shapes: list[tuple[int, int]] = []

    # ======================================================
    # Public API
    # ======================================================

    def rerank(
        self,
        *,
        query: InvestigationSearchQuery,
        hits: list[InvestigationSearchHit],
    ) -> list[InvestigationSearchHit]:
        """
        Apply optional neural reranking.

        The method is fail-safe and idempotent. Neural output
        is never recursively treated as the mathematical input.
        """

        if not isinstance(
            query,
            InvestigationSearchQuery,
        ):
            raise TypeError(
                "query must be InvestigationSearchQuery."
            )

        input_hits = list(hits)
        self._reset_runtime_status()

        if not input_hits:
            return []

        if not query.has_text_query:
            return input_hits

        started_at = perf_counter()

        try:
            canonical_hits = self._canonical_order(
                input_hits
            )

            self.last_candidate_count = min(
                self.config.maximum_candidates,
                len(canonical_hits),
            )

            window = canonical_hits[
                : self.last_candidate_count
            ]
            tail = canonical_hits[
                self.last_candidate_count :
            ]

            candidates = self._prepare_candidates(
                window
            )

            if not candidates:
                self.last_duration_seconds = (
                    perf_counter() - started_at
                )
                return canonical_hits

            self._ensure_runtime()

            raw_logits = self._infer_logits(
                query_text=query.query,
                candidates=candidates,
            )

            if len(raw_logits) != len(candidates):
                raise RuntimeError(
                    "Cross-encoder output size does not match candidate count."
                )

            normalized_scores = self._normalize_logits(
                raw_logits
            )

            updates: list[
                tuple[
                    _NeuralCandidate,
                    float,
                    float,
                    float,
                ]
            ] = []

            for (
                candidate,
                raw_logit,
                neural_score,
            ) in zip(
                candidates,
                raw_logits,
                normalized_scores,
            ):
                combined_score = self._combine_scores(
                    mathematical_score=(
                        candidate.mathematical_score
                    ),
                    neural_score=neural_score,
                )

                updates.append(
                    (
                        candidate,
                        raw_logit,
                        neural_score,
                        combined_score,
                    )
                )

            # Mutate only after successful inference/calculation.
            reranked_identity_keys = {
                candidate.hit.identity_key
                for candidate in candidates
            }

            for (
                candidate,
                raw_logit,
                neural_score,
                combined_score,
            ) in updates:
                hit = candidate.hit

                hit.metadata[self.METADATA_KEY] = {
                    "applied": True,
                    "model": self.config.model_identifier,
                    "runtime": "onnxruntime",
                    "provider": "CPUExecutionProvider",
                    "pre_neural_rank": (
                        candidate.pre_neural_rank
                    ),
                    "document_field": (
                        candidate.document_field
                    ),
                    "input_tokens": (
                        candidate.token_length
                    ),
                    "length_bucket": (
                        candidate.length_bucket
                    ),
                    "mathematical_score": (
                        candidate.mathematical_score
                    ),
                    "raw_logit": raw_logit,
                    "normalized_score": neural_score,
                    "combined_score": combined_score,
                    "weights": {
                        "mathematical": (
                            self.config.mathematical_weight
                        ),
                        "neural": (
                            self.config.neural_weight
                        ),
                    },
                }

                hit.scores.rerank = combined_score
                hit.scores.final = combined_score

            # Candidates in the Top-N window without usable text
            # keep their mathematical score.
            for index, hit in enumerate(
                window,
                start=1,
            ):
                if hit.identity_key in reranked_identity_keys:
                    continue

                mathematical_score = self._mathematical_score(
                    hit
                )

                hit.metadata[self.METADATA_KEY] = {
                    "applied": False,
                    "reason": "No usable neural document text.",
                    "model": self.config.model_identifier,
                    "pre_neural_rank": self._pre_neural_rank(
                        hit=hit,
                        fallback=index,
                    ),
                    "mathematical_score": mathematical_score,
                    "combined_score": mathematical_score,
                }

                hit.scores.rerank = mathematical_score
                hit.scores.final = mathematical_score

            # Tail stays mathematical and stays after the
            # neural Top-N window.
            for fallback_rank, hit in enumerate(
                tail,
                start=(self.last_candidate_count + 1),
            ):
                mathematical_score = self._mathematical_score(
                    hit
                )

                hit.metadata[self.METADATA_KEY] = {
                    "applied": False,
                    "reason": "Outside neural candidate window.",
                    "model": self.config.model_identifier,
                    "pre_neural_rank": self._pre_neural_rank(
                        hit=hit,
                        fallback=fallback_rank,
                    ),
                    "mathematical_score": mathematical_score,
                    "combined_score": mathematical_score,
                }

                hit.scores.rerank = mathematical_score
                hit.scores.final = mathematical_score

            reranked_window = list(window)
            reranked_window.sort(
                key=lambda hit: (
                    -self._current_score(hit),
                    self._pre_neural_rank(
                        hit=hit,
                        fallback=10**18,
                    ),
                )
            )

            result = reranked_window + list(tail)

            for rank, hit in enumerate(
                result,
                start=1,
            ):
                neural_data = hit.metadata.get(
                    self.METADATA_KEY
                )

                if isinstance(neural_data, dict):
                    neural_data["post_neural_rank"] = rank

            self.last_reranked_count = len(candidates)
            self.last_duration_seconds = (
                perf_counter() - started_at
            )

            return result

        except Exception as error:
            self.last_error = str(error)
            self.last_duration_seconds = (
                perf_counter() - started_at
            )

            return self._restore_mathematical_state(
                input_hits
            )

    # ======================================================
    # Canonical ordering
    # ======================================================

    def _canonical_order(
        self,
        hits: list[InvestigationSearchHit],
    ) -> list[InvestigationSearchHit]:
        """Recover canonical pre-neural order."""

        existing_ranks: list[
            tuple[InvestigationSearchHit, int]
        ] = []

        for hit in hits:
            data = hit.metadata.get(
                self.METADATA_KEY
            )

            if not isinstance(data, dict):
                return list(hits)

            rank = data.get("pre_neural_rank")

            if not isinstance(rank, int):
                return list(hits)

            existing_ranks.append((hit, rank))

        existing_ranks.sort(
            key=lambda item: item[1]
        )

        return [
            hit
            for hit, _ in existing_ranks
        ]

    # ======================================================
    # Candidate preparation
    # ======================================================

    def _prepare_candidates(
        self,
        hits: list[InvestigationSearchHit],
    ) -> list[_NeuralCandidate]:
        """Convert mathematical Top-N hits into neural pairs."""

        candidates: list[_NeuralCandidate] = []

        for fallback_rank, hit in enumerate(
            hits,
            start=1,
        ):
            document_text, document_field = (
                self._document_text(hit)
            )

            if not document_text:
                continue

            candidates.append(
                _NeuralCandidate(
                    hit=hit,
                    pre_neural_rank=self._pre_neural_rank(
                        hit=hit,
                        fallback=fallback_rank,
                    ),
                    mathematical_score=(
                        self._mathematical_score(hit)
                    ),
                    document_text=document_text,
                    document_field=document_field,
                )
            )

        return candidates

    # ======================================================
    # Neural document representation
    # ======================================================

    def _document_text(
        self,
        hit: InvestigationSearchHit,
    ) -> tuple[str, str]:
        """Build a field-aware neural document representation."""

        fields = self.field_extractor.extract(
            source=hit.source,
            object_type=hit.object_type,
            title=hit.title,
            content=hit.snippet,
        )

        if hit.object_type == "message":
            return self._message_document_text(
                hit=hit,
                fields=fields,
            )

        return self._generic_document_text(
            hit=hit,
            fields=fields,
        )

    def _message_document_text(
        self,
        *,
        hit: InvestigationSearchHit,
        fields: SearchIndexFields,
    ) -> tuple[str, str]:
        """Field-aware neural representation for a message."""

        best_field = self._best_mathematical_field(
            hit
        )

        message_text = (
            fields.message_text
            or self._source_attribute(
                hit.source,
                "text",
            )
            or hit.snippet
        )

        sender = (
            fields.sender
            or self._source_attribute(
                hit.source,
                "sender",
            )
        )

        receiver = (
            fields.receiver
            or self._source_attribute(
                hit.source,
                "receiver",
            )
        )

        chat = (
            fields.chat
            or self._source_attribute(
                hit.source,
                "chat_name",
            )
            or self._source_attribute(
                hit.source,
                "chat",
            )
        )

        external_id = (
            fields.external_id
            or self._source_attribute(
                hit.source,
                "external_id",
            )
        )

        sent_at = (
            fields.sent_at
            or self._source_attribute(
                hit.source,
                "sent_at",
            )
        )

        metadata_text = fields.metadata_text

        if best_field == "message_text":
            return (
                self._truncate_document(message_text),
                "message_text",
            )

        context_mapping = {
            "sender": ("SENDER", sender),
            "receiver": ("RECEIVER", receiver),
            "chat": ("CHAT", chat),
            "external_id": (
                "EXTERNAL_ID",
                external_id,
            ),
            "sent_at": ("SENT_AT", sent_at),
            "metadata": (
                "METADATA",
                metadata_text,
            ),
        }

        context = context_mapping.get(best_field)

        if context is not None:
            label, value = context

            if value:
                parts = [f"{label}: {value}"]

                if message_text:
                    parts.append(
                        "MESSAGE_TEXT: "
                        + message_text
                    )

                return (
                    self._truncate_document(
                        "\n".join(parts)
                    ),
                    best_field,
                )

        if message_text:
            return (
                self._truncate_document(message_text),
                "message_text",
            )

        if sender:
            return (
                self._truncate_document(
                    f"SENDER: {sender}"
                ),
                "sender",
            )

        return "", ""

    def _generic_document_text(
        self,
        *,
        hit: InvestigationSearchHit,
        fields: SearchIndexFields,
    ) -> tuple[str, str]:
        """Neural representation for non-message objects."""

        title = fields.title or hit.title
        content = fields.raw_content or hit.snippet

        if hit.object_type == "entity":
            text = (
                title
                or fields.primary_text
                or content
            )

            return (
                self._truncate_document(text),
                "title" if title else "content",
            )

        parts: list[str] = []

        if title:
            parts.append(title)

        if content and content != title:
            parts.append(content)

        text = "\n\n".join(parts)

        if not text:
            text = fields.primary_text

        return (
            self._truncate_document(text),
            (
                "title+content"
                if title and content
                else (
                    "title"
                    if title
                    else "content"
                )
            ),
        )

    # ======================================================
    # Runtime loading
    # ======================================================

    def _ensure_runtime(self) -> None:
        """Lazily load tokenizer and ONNX model locally."""

        if (
            self._tokenizer is not None
            and self._session is not None
            and self._numpy is not None
        ):
            self.last_loaded = True
            return

        model_directory = self.config.model_directory
        model_path = (
            model_directory
            / self.config.model_filename
        )

        if not model_directory.exists():
            raise FileNotFoundError(
                "Neural reranker model directory does not exist: "
                f"{model_directory}"
            )

        if not model_path.exists():
            raise FileNotFoundError(
                "Neural reranker ONNX model does not exist: "
                f"{model_path}"
            )

        np = importlib.import_module("numpy")
        ort = importlib.import_module("onnxruntime")
        transformers = importlib.import_module(
            "transformers"
        )

        tokenizer_class = getattr(
            transformers,
            "AutoTokenizer",
        )

        tokenizer = tokenizer_class.from_pretrained(
            model_directory,
            local_files_only=True,
        )

        session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )

        providers = session.get_providers()

        if "CPUExecutionProvider" not in providers:
            raise RuntimeError(
                "CPUExecutionProvider is not available for neural reranking."
            )

        input_names = tuple(
            item.name
            for item in session.get_inputs()
        )

        if "input_ids" not in input_names:
            raise RuntimeError(
                "ONNX cross-encoder does not expose input_ids."
            )

        if "attention_mask" not in input_names:
            raise RuntimeError(
                "ONNX cross-encoder does not expose attention_mask."
            )

        self._numpy = np
        self._tokenizer = tokenizer
        self._session = session
        self._session_input_names = input_names
        self.last_loaded = True

    # ======================================================
    # Length-aware inference
    # ======================================================

    def _infer_logits(
        self,
        *,
        query_text: str,
        candidates: list[_NeuralCandidate],
    ) -> list[float]:
        """
        Run length-aware ONNX inference.

        Important performance rule:

        A single 512-token document must not force every short
        candidate in the same batch to be padded to 512 tokens.

        We therefore tokenize once without padding, bucket by
        resulting pair length, pad only inside each bucket, run
        ONNX, and then restore logits to original candidate order.
        """

        if (
            self._tokenizer is None
            or self._session is None
            or self._numpy is None
        ):
            raise RuntimeError(
                "Neural runtime is not loaded."
            )

        if not candidates:
            return []

        queries = [
            query_text
            for _ in candidates
        ]
        documents = [
            candidate.document_text
            for candidate in candidates
        ]

        # Tokenize once without padding. The tokenizer already
        # performs max_length truncation here, so token lengths
        # reflect the exact model input lengths.
        encoded = self._tokenizer(
            queries,
            documents,
            padding=False,
            truncation=True,
            max_length=self.config.max_length,
            add_special_tokens=True,
            return_attention_mask=True,
        )

        input_ids_all = encoded.get("input_ids")
        attention_all = encoded.get("attention_mask")

        if input_ids_all is None:
            raise RuntimeError(
                "Tokenizer did not return input_ids."
            )

        if attention_all is None:
            raise RuntimeError(
                "Tokenizer did not return attention_mask."
            )

        if len(input_ids_all) != len(candidates):
            raise RuntimeError(
                "Tokenizer output size does not match candidate count."
            )

        # boundary -> original candidate indexes
        buckets: dict[int, list[int]] = {}

        for index, token_ids in enumerate(
            input_ids_all
        ):
            token_length = len(token_ids)
            boundary = self._length_bucket(
                token_length
            )

            candidate = candidates[index]
            candidate.token_length = token_length
            candidate.length_bucket = boundary

            buckets.setdefault(
                boundary,
                [],
            ).append(index)

        logits_by_index: list[float | None] = [
            None
            for _ in candidates
        ]

        self.last_batch_shapes = []
        self.last_batch_count = 0

        # Short buckets are processed first. This is not required
        # for correctness but gives predictable low-latency work
        # before expensive long-document buckets.
        for boundary in sorted(buckets):
            bucket_indexes = buckets[boundary]

            for start in range(
                0,
                len(bucket_indexes),
                self.config.batch_size,
            ):
                selected_indexes = bucket_indexes[
                    start : start + self.config.batch_size
                ]

                features = []

                for original_index in selected_indexes:
                    features.append(
                        {
                            "input_ids": (
                                input_ids_all[original_index]
                            ),
                            "attention_mask": (
                                attention_all[original_index]
                            ),
                        }
                    )

                # Pad only this length bucket.
                batch = self._tokenizer.pad(
                    features,
                    padding=True,
                    return_tensors="np",
                )

                inputs: dict[str, Any] = {}

                for name in self._session_input_names:
                    value = batch.get(name)

                    if value is None:
                        continue

                    inputs[name] = self._numpy.asarray(
                        value,
                        dtype=self._numpy.int64,
                    )

                if "input_ids" not in inputs:
                    raise RuntimeError(
                        "Prepared neural batch has no input_ids."
                    )

                if "attention_mask" not in inputs:
                    raise RuntimeError(
                        "Prepared neural batch has no attention_mask."
                    )

                shape = inputs["input_ids"].shape

                if len(shape) != 2:
                    raise RuntimeError(
                        "Cross-encoder input_ids must be 2-dimensional."
                    )

                self.last_batch_shapes.append(
                    (int(shape[0]), int(shape[1]))
                )
                self.last_batch_count += 1

                output = self._session.run(
                    None,
                    inputs,
                )

                if not output:
                    raise RuntimeError(
                        "ONNX cross-encoder returned no outputs."
                    )

                batch_logits = (
                    self._numpy.asarray(output[0])
                    .reshape(-1)
                    .astype(float)
                    .tolist()
                )

                if len(batch_logits) != len(
                    selected_indexes
                ):
                    raise RuntimeError(
                        "ONNX batch output size does not match batch size."
                    )

                for original_index, value in zip(
                    selected_indexes,
                    batch_logits,
                ):
                    logits_by_index[original_index] = float(
                        value
                    )

        if any(
            value is None
            for value in logits_by_index
        ):
            raise RuntimeError(
                "Neural inference did not produce a logit for every candidate."
            )

        return [
            float(value)
            for value in logits_by_index
            if value is not None
        ]

    def _length_bucket(
        self,
        token_length: int,
    ) -> int:
        """Return the configured token-length bucket boundary."""

        normalized = max(
            1,
            min(
                int(token_length),
                self.config.max_length,
            ),
        )

        for boundary in (
            self.config.length_bucket_boundaries
        ):
            if normalized <= boundary:
                return boundary

        # Config validation guarantees the last boundary is at
        # least max_length, so this is only a defensive fallback.
        return self.config.length_bucket_boundaries[-1]

    # ======================================================
    # Logit normalization
    # ======================================================

    def _normalize_logits(
        self,
        logits: list[float],
    ) -> list[float]:
        """Min-max normalize logits inside the rerank window."""

        if not logits:
            return []

        cleaned = [
            float(value)
            for value in logits
        ]

        for value in cleaned:
            if not isfinite(value):
                raise ValueError(
                    "Cross-encoder returned a non-finite logit."
                )

        minimum = min(cleaned)
        maximum = max(cleaned)
        spread = maximum - minimum

        if spread <= self.config.minimum_logit_range:
            return [
                0.5
                for _ in cleaned
            ]

        return [
            self._clamp(
                (value - minimum) / spread
            )
            for value in cleaned
        ]

    # ======================================================
    # Score combination
    # ======================================================

    def _combine_scores(
        self,
        *,
        mathematical_score: float,
        neural_score: float,
    ) -> float:
        """Combine mathematical and neural relevance."""

        mathematical_weight = (
            self.config.mathematical_weight
        )
        neural_weight = self.config.neural_weight
        total_weight = (
            mathematical_weight + neural_weight
        )

        combined = (
            (
                mathematical_score
                * mathematical_weight
            )
            + (
                neural_score
                * neural_weight
            )
        ) / total_weight

        return self._clamp(combined)

    # ======================================================
    # Mathematical score
    # ======================================================

    def _mathematical_score(
        self,
        hit: InvestigationSearchHit,
    ) -> float:
        """Recover immutable mathematical ranking score."""

        previous_neural = hit.metadata.get(
            self.METADATA_KEY
        )

        if isinstance(previous_neural, dict):
            validated = self._optional_score(
                previous_neural.get(
                    "mathematical_score"
                )
            )

            if validated is not None:
                return validated

        mathematical = hit.metadata.get(
            self.MATHEMATICAL_METADATA_KEY
        )

        if isinstance(mathematical, dict):
            validated = self._optional_score(
                mathematical.get("score")
            )

            if validated is not None:
                return validated

        for value in (
            hit.scores.rerank,
            hit.scores.final,
            hit.scores.fusion,
        ):
            validated = self._optional_score(value)

            if validated is not None:
                return validated

        return 0.0

    # ======================================================
    # Mathematical best field
    # ======================================================

    def _best_mathematical_field(
        self,
        hit: InvestigationSearchHit,
    ) -> str:
        """Recover best field selected by mathematical ranking."""

        mathematical = hit.metadata.get(
            self.MATHEMATICAL_METADATA_KEY
        )

        if not isinstance(mathematical, dict):
            return ""

        field_relevance = mathematical.get(
            "field_relevance"
        )

        if not isinstance(field_relevance, dict):
            return ""

        value = field_relevance.get(
            "best_field"
        )

        if not isinstance(value, str):
            return ""

        return value.strip().casefold()

    # ======================================================
    # Rank helpers
    # ======================================================

    def _pre_neural_rank(
        self,
        *,
        hit: InvestigationSearchHit,
        fallback: int,
    ) -> int:
        """Preserve initial mathematical position."""

        data = hit.metadata.get(
            self.METADATA_KEY
        )

        if isinstance(data, dict):
            value = data.get("pre_neural_rank")

            if (
                isinstance(value, int)
                and value >= 1
            ):
                return value

        return max(1, int(fallback))

    @staticmethod
    def _current_score(
        hit: InvestigationSearchHit,
    ) -> float:
        return (
            NeuralCrossEncoderRerankingService
            ._clamp(hit.scores.final)
        )

    # ======================================================
    # Failure restoration
    # ======================================================

    def _restore_mathematical_state(
        self,
        hits: list[InvestigationSearchHit],
    ) -> list[InvestigationSearchHit]:
        """Restore mathematical scores after neural failure."""

        restored = list(hits)

        for hit in restored:
            mathematical_score = self._mathematical_score(
                hit
            )

            hit.scores.rerank = mathematical_score
            hit.scores.final = mathematical_score

            hit.metadata.pop(
                self.METADATA_KEY,
                None,
            )

        restored.sort(
            key=lambda hit: (
                -self._mathematical_score(hit),
                -(
                    hit.scores.fusion
                    if hit.scores.fusion is not None
                    else 0.0
                ),
            )
        )

        return restored

    # ======================================================
    # Source helpers
    # ======================================================

    @staticmethod
    def _source_attribute(
        source: Any | None,
        name: str,
    ) -> str:
        """Resolve a textual source attribute."""

        if source is None:
            return ""

        value = getattr(
            source,
            name,
            None,
        )

        if value is None:
            return ""

        return str(value).strip()

    def _truncate_document(
        self,
        text: str,
    ) -> str:
        """Limit Python-side text before tokenizer truncation."""

        normalized = (text or "").strip()

        if not normalized:
            return ""

        return normalized[
            : self.config.max_document_chars
        ]

    # ======================================================
    # Numerical helpers
    # ======================================================

    @staticmethod
    def _optional_score(
        value: Any,
    ) -> float | None:
        if value is None:
            return None

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None

        if not isfinite(numeric):
            return None

        return (
            NeuralCrossEncoderRerankingService
            ._clamp(numeric)
        )

    @staticmethod
    def _clamp(value: float) -> float:
        if not isfinite(float(value)):
            return 0.0

        return min(
            1.0,
            max(0.0, float(value)),
        )

    # ======================================================
    # Runtime status
    # ======================================================

    def _reset_runtime_status(self) -> None:
        self.last_error = None
        self.last_duration_seconds = 0.0
        self.last_reranked_count = 0
        self.last_candidate_count = 0
        self.last_batch_count = 0
        self.last_batch_shapes = []
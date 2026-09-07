"""
Shared multimodal analytical contracts.

Phase 6.2.

Purpose:

Normalize analytical outputs produced by existing
image / face / similarity / GPS subsystems into one
stable read-only analytical contract.

Existing sources include:

- ImageHashAnalyzer
- ImageFaceAnalyzer
- FaceEmbeddingAnalyzer
- ImageSimilarityAnalyzer
- image EXIF / GPS metadata

Important semantic boundaries:

multimodal signal
    != Evidence confidence

face similarity
    != person identity proof

image similarity
    != duplicate-evidence proof

GPS metadata
    != proof that a person was present

analyzer failure
    != negative analytical conclusion

DB persistence
    != multimodal analysis

This module contains contracts only.

It performs no:

- database access
- database writes
- Evidence creation
- Entity creation
- Relationship creation
- Entity Resolution
- face-memory mutation
- LOCATION creation
"""

from __future__ import annotations

from copy import deepcopy

from dataclasses import (
    dataclass,
    field,
)

from enum import Enum

from math import isfinite

from typing import Any

from uuid import UUID


# ==========================================================
# Signal kind
# ==========================================================


class MultimodalSignalKind(
    str,
    Enum,
):
    """
    Independent analytical channels currently confirmed
    by the Phase 6.1 production-code audit.
    """

    IMAGE_HASH = "image_hash"

    FACE_DETECTION = "face_detection"

    FACE_EMBEDDING = "face_embedding"

    IMAGE_EMBEDDING = "image_embedding"

    OCR_TEXT = "ocr_text"

    AUDIO_TRANSCRIPTION = "audio_transcription"

    VIDEO_TRANSCRIPTION = "video_transcription"

    VIDEO_FRAME_ANALYSIS = "video_frame_analysis"

    IMAGE_SIMILARITY = "image_similarity"

    GPS_METADATA = "gps_metadata"


# ==========================================================
# Scope
# ==========================================================


class MultimodalSignalScope(
    str,
    Enum,
):
    """
    Scope of one analytical signal.

    EVIDENCE:
        one Evidence object.

    EVIDENCE_PAIR:
        analytical comparison between two Evidence objects.
    """

    EVIDENCE = "evidence"

    EVIDENCE_PAIR = "evidence_pair"


# ==========================================================
# Status
# ==========================================================


class MultimodalSignalStatus(
    str,
    Enum,
):
    """
    Execution / availability status.

    Status describes analyzer execution only.

    It is NOT:

    - truth confidence
    - evidence reliability
    - identity confidence
    - suspiciousness
    """

    COMPLETED = "completed"

    UNAVAILABLE = "unavailable"

    SKIPPED = "skipped"

    FAILED = "failed"


# ==========================================================
# Main normalized signal result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class MultimodalSignalResult:
    """
    One normalized analytical result from one multimodal
    source.

    `data` deliberately remains structured instead of being
    collapsed into one score.

    Examples:

        IMAGE_HASH:
            cryptographic hashes
            perceptual hashes

        FACE_DETECTION:
            faces
            face count
            detector metadata

        FACE_EMBEDDING:
            embeddings
            dimensions
            recognizer metadata

        IMAGE_EMBEDDING:
            whole-image semantic embedding
            embedding dimension and model metadata

        IMAGE_SIMILARITY:
            exact_match
            visual_similarity
            perceptual comparisons

        GPS_METADATA:
            latitude
            longitude
            altitude

    No semantic conclusion about criminality, identity,
    evidence reliability or causality is represented here.
    """

    kind: MultimodalSignalKind

    scope: MultimodalSignalScope

    status: MultimodalSignalStatus

    evidence_ids: tuple[
        UUID,
        ...,
    ]

    source: str

    data: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    warnings: tuple[
        str,
        ...,
    ] = ()

    errors: tuple[
        str,
        ...,
    ] = ()

    execution_time: (
        float
        | None
    ) = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        # ======================================================
        # Enum types
        # ======================================================

        if not isinstance(
            self.kind,
            MultimodalSignalKind,
        ):

            raise TypeError(
                "kind must be "
                "MultimodalSignalKind."
            )

        if not isinstance(
            self.scope,
            MultimodalSignalScope,
        ):

            raise TypeError(
                "scope must be "
                "MultimodalSignalScope."
            )

        if not isinstance(
            self.status,
            MultimodalSignalStatus,
        ):

            raise TypeError(
                "status must be "
                "MultimodalSignalStatus."
            )

        # ======================================================
        # Evidence identifiers
        # ======================================================

        if not isinstance(
            self.evidence_ids,
            tuple,
        ):

            raise TypeError(
                "evidence_ids must be tuple."
            )

        for evidence_id in (
            self.evidence_ids
        ):

            if not isinstance(
                evidence_id,
                UUID,
            ):

                raise TypeError(
                    "evidence_ids must contain UUID values."
                )

        if (
            len(
                set(
                    self.evidence_ids
                )
            )
            !=
            len(
                self.evidence_ids
            )
        ):

            raise ValueError(
                "evidence_ids cannot contain duplicates."
            )

        # ======================================================
        # Scope cardinality
        # ======================================================

        if (
            self.scope
            ==
            MultimodalSignalScope.EVIDENCE
        ):

            if (
                len(
                    self.evidence_ids
                )
                !=
                1
            ):

                raise ValueError(
                    "EVIDENCE scope requires exactly "
                    "one Evidence ID."
                )

        elif (
            self.scope
            ==
            MultimodalSignalScope.EVIDENCE_PAIR
        ):

            if (
                len(
                    self.evidence_ids
                )
                !=
                2
            ):

                raise ValueError(
                    "EVIDENCE_PAIR scope requires exactly "
                    "two Evidence IDs."
                )

        # ======================================================
        # Kind ↔ scope semantics
        # ======================================================

        if (
            self.kind
            ==
            MultimodalSignalKind.IMAGE_SIMILARITY
        ):

            if (
                self.scope
                !=
                MultimodalSignalScope.EVIDENCE_PAIR
            ):

                raise ValueError(
                    "IMAGE_SIMILARITY requires "
                    "EVIDENCE_PAIR scope."
                )

        else:

            if (
                self.scope
                !=
                MultimodalSignalScope.EVIDENCE
            ):

                raise ValueError(
                    f"{self.kind.value} requires "
                    "EVIDENCE scope."
                )

        # ======================================================
        # Canonical pair ordering
        # ======================================================

        if (
            self.scope
            ==
            MultimodalSignalScope.EVIDENCE_PAIR
        ):

            canonical_ids = tuple(
                sorted(
                    self.evidence_ids,
                    key=str,
                )
            )

            object.__setattr__(
                self,
                "evidence_ids",
                canonical_ids,
            )

        # ======================================================
        # Source
        # ======================================================

        if (
            not isinstance(
                self.source,
                str,
            )
            or
            not self.source.strip()
        ):

            raise ValueError(
                "source cannot be empty."
            )

        object.__setattr__(
            self,
            "source",
            self.source.strip(),
        )

        # ======================================================
        # Structured data
        # ======================================================

        if not isinstance(
            self.data,
            dict,
        ):

            raise TypeError(
                "data must be dict."
            )

        if not isinstance(
            self.metadata,
            dict,
        ):

            raise TypeError(
                "metadata must be dict."
            )

        # Prevent accidental aliasing with mutable source
        # dictionaries supplied by existing analyzers.
        object.__setattr__(
            self,
            "data",
            deepcopy(
                self.data
            ),
        )

        object.__setattr__(
            self,
            "metadata",
            deepcopy(
                self.metadata
            ),
        )

        # ======================================================
        # Warning / error collections
        # ======================================================

        normalized_warnings = (
            self._normalize_messages(
                self.warnings,
                name="warnings",
            )
        )

        normalized_errors = (
            self._normalize_messages(
                self.errors,
                name="errors",
            )
        )

        object.__setattr__(
            self,
            "warnings",
            normalized_warnings,
        )

        object.__setattr__(
            self,
            "errors",
            normalized_errors,
        )

        # ======================================================
        # Status semantics
        # ======================================================

        if (
            self.status
            ==
            MultimodalSignalStatus.COMPLETED
            and
            self.errors
        ):

            raise ValueError(
                "COMPLETED multimodal signals "
                "cannot contain errors."
            )

        if (
            self.status
            ==
            MultimodalSignalStatus.FAILED
            and
            not self.errors
        ):

            raise ValueError(
                "FAILED multimodal signals must "
                "contain at least one error."
            )

        if (
            self.status
            !=
            MultimodalSignalStatus.COMPLETED
            and
            self.data
        ):

            raise ValueError(
                "Non-completed multimodal signals "
                "cannot contain analytical data."
            )

        # ======================================================
        # Execution time
        # ======================================================

        if (
            self.execution_time
            is not None
        ):

            execution_time = float(
                self.execution_time
            )

            if (
                not isfinite(
                    execution_time
                )
                or
                execution_time < 0.0
            ):

                raise ValueError(
                    "execution_time must be finite "
                    "and non-negative."
                )

            object.__setattr__(
                self,
                "execution_time",
                execution_time,
            )

    # ==========================================================
    # Message normalization
    # ==========================================================

    @staticmethod
    def _normalize_messages(
        values: tuple[
            str,
            ...,
        ],
        *,
        name: str,
    ) -> tuple[
        str,
        ...,
    ]:

        if not isinstance(
            values,
            tuple,
        ):

            raise TypeError(
                f"{name} must be tuple."
            )

        normalized: list[
            str
        ] = []

        for value in values:

            if not isinstance(
                value,
                str,
            ):

                raise TypeError(
                    f"{name} must contain strings."
                )

            value = value.strip()

            if not value:

                continue

            normalized.append(
                value
            )

        return tuple(
            normalized
        )

    # ==========================================================
    # Deterministic analytical identity
    # ==========================================================

    @property
    def signal_id(
        self,
    ) -> str:
        """
        Deterministic analytical identifier.

        This is NOT a database primary key.
        """

        evidence_part = ",".join(
            str(
                evidence_id
            )
            for evidence_id
            in self.evidence_ids
        )

        return (
            f"{self.kind.value}"
            f"|{self.source}"
            f"|{evidence_part}"
        )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def successful(
        self,
    ) -> bool:

        return (
            self.status
            ==
            MultimodalSignalStatus.COMPLETED
        )

    @property
    def evidence_id(
        self,
    ) -> UUID:
        """
        Convenience accessor for single-Evidence signals.
        """

        if (
            self.scope
            !=
            MultimodalSignalScope.EVIDENCE
        ):

            raise ValueError(
                "evidence_id is available only "
                "for EVIDENCE-scoped signals."
            )

        return (
            self.evidence_ids[
                0
            ]
        )

    @property
    def evidence_pair(
        self,
    ) -> tuple[
        UUID,
        UUID,
    ]:
        """
        Convenience accessor for comparison signals.
        """

        if (
            self.scope
            !=
            MultimodalSignalScope.EVIDENCE_PAIR
        ):

            raise ValueError(
                "evidence_pair is available only "
                "for EVIDENCE_PAIR-scoped signals."
            )

        return (
            self.evidence_ids[
                0
            ],
            self.evidence_ids[
                1
            ],
        )

    # ==========================================================
    # Constructors
    # ==========================================================

    @classmethod
    def completed(
        cls,
        *,
        kind: MultimodalSignalKind,
        evidence_ids: tuple[
            UUID,
            ...,
        ],
        source: str,
        data: dict[
            str,
            Any,
        ],
        execution_time: (
            float
            | None
        ) = None,
        warnings: tuple[
            str,
            ...,
        ] = (),
        metadata: dict[
            str,
            Any,
        ]
        | None = None,
    ) -> "MultimodalSignalResult":

        scope = (
            MultimodalSignalScope.EVIDENCE_PAIR
            if (
                kind
                ==
                MultimodalSignalKind.IMAGE_SIMILARITY
            )
            else
            MultimodalSignalScope.EVIDENCE
        )

        return cls(
            kind=kind,
            scope=scope,
            status=(
                MultimodalSignalStatus.COMPLETED
            ),
            evidence_ids=evidence_ids,
            source=source,
            data=data,
            warnings=warnings,
            errors=(),
            execution_time=(
                execution_time
            ),
            metadata=(
                metadata
                or {}
            ),
        )

    @classmethod
    def unavailable(
        cls,
        *,
        kind: MultimodalSignalKind,
        evidence_ids: tuple[
            UUID,
            ...,
        ],
        source: str,
        reason: str,
        metadata: dict[
            str,
            Any,
        ]
        | None = None,
    ) -> "MultimodalSignalResult":

        scope = (
            MultimodalSignalScope.EVIDENCE_PAIR
            if (
                kind
                ==
                MultimodalSignalKind.IMAGE_SIMILARITY
            )
            else
            MultimodalSignalScope.EVIDENCE
        )

        return cls(
            kind=kind,
            scope=scope,
            status=(
                MultimodalSignalStatus.UNAVAILABLE
            ),
            evidence_ids=evidence_ids,
            source=source,
            data={},
            warnings=(
                str(
                    reason
                ),
            ),
            errors=(),
            execution_time=None,
            metadata=(
                metadata
                or {}
            ),
        )

    @classmethod
    def skipped(
        cls,
        *,
        kind: MultimodalSignalKind,
        evidence_ids: tuple[
            UUID,
            ...,
        ],
        source: str,
        reason: str,
        metadata: dict[
            str,
            Any,
        ]
        | None = None,
    ) -> "MultimodalSignalResult":

        scope = (
            MultimodalSignalScope.EVIDENCE_PAIR
            if (
                kind
                ==
                MultimodalSignalKind.IMAGE_SIMILARITY
            )
            else
            MultimodalSignalScope.EVIDENCE
        )

        return cls(
            kind=kind,
            scope=scope,
            status=(
                MultimodalSignalStatus.SKIPPED
            ),
            evidence_ids=evidence_ids,
            source=source,
            data={},
            warnings=(
                str(
                    reason
                ),
            ),
            errors=(),
            execution_time=None,
            metadata=(
                metadata
                or {}
            ),
        )

    @classmethod
    def failed(
        cls,
        *,
        kind: MultimodalSignalKind,
        evidence_ids: tuple[
            UUID,
            ...,
        ],
        source: str,
        error: (
            str
            | Exception
        ),
        execution_time: (
            float
            | None
        ) = None,
        metadata: dict[
            str,
            Any,
        ]
        | None = None,
    ) -> "MultimodalSignalResult":

        error_text = str(
            error
        ).strip()

        if not error_text:

            error_text = (
                type(
                    error
                ).__name__
            )

        scope = (
            MultimodalSignalScope.EVIDENCE_PAIR
            if (
                kind
                ==
                MultimodalSignalKind.IMAGE_SIMILARITY
            )
            else
            MultimodalSignalScope.EVIDENCE
        )

        return cls(
            kind=kind,
            scope=scope,
            status=(
                MultimodalSignalStatus.FAILED
            ),
            evidence_ids=evidence_ids,
            source=source,
            data={},
            warnings=(),
            errors=(
                error_text,
            ),
            execution_time=(
                execution_time
            ),
            metadata=(
                metadata
                or {}
            ),
        )
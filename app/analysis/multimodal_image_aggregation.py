"""
Image analytical aggregation.

Phase 6.3.

Adapts already computed ImageAnalysisResult objects into
the shared Phase 6 multimodal analytical contract.

Supported image-analysis channels:

- IMAGE_HASH
- FACE_DETECTION
- FACE_EMBEDDING
- IMAGE_EMBEDDING

This module deliberately does NOT execute image analyzers.

It therefore performs no:

- image loading
- hash calculation
- face detection
- face embedding generation
- whole-image embedding generation
- Evidence metadata update
- database access
- database writes
- face-memory mutation
- Entity creation
- identity inference

Existing ImageAnalysisResult payloads remain intact inside
MultimodalSignalResult.data.

Important:

ImageAnalysisResult
    ↓
normalization only
    ↓
MultimodalSignalResult

No analytical score fusion is performed.
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
)

from typing import Mapping

from uuid import UUID

from app.analysis.images.image_analysis_result import (
    ImageAnalysisResult,
)

from app.analysis.multimodal_contracts import (
    MultimodalSignalKind,
    MultimodalSignalResult,
    MultimodalSignalScope,
    MultimodalSignalStatus,
)


# ==========================================================
# Supported single-image analytical channels
# ==========================================================


IMAGE_ANALYTICAL_SIGNAL_KINDS: tuple[
    MultimodalSignalKind,
    ...,
] = (
    MultimodalSignalKind.IMAGE_HASH,
    MultimodalSignalKind.FACE_DETECTION,
    MultimodalSignalKind.FACE_EMBEDDING,
    MultimodalSignalKind.IMAGE_EMBEDDING,
    MultimodalSignalKind.OCR_TEXT,
)


# ==========================================================
# Complete aggregation result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class MultimodalImageAggregationResult:
    """
    Normalized multimodal signals for one image Evidence.

    Every signal retains its own source payload and status.

    No combined score is created.
    """

    evidence_id: UUID

    signals: tuple[
        MultimodalSignalResult,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.evidence_id,
            UUID,
        ):

            raise TypeError(
                "evidence_id must be UUID."
            )

        if not isinstance(
            self.signals,
            tuple,
        ):

            raise TypeError(
                "signals must be tuple."
            )

        seen_kinds: set[
            MultimodalSignalKind
        ] = set()

        for signal in self.signals:

            if not isinstance(
                signal,
                MultimodalSignalResult,
            ):

                raise TypeError(
                    "signals must contain "
                    "MultimodalSignalResult objects."
                )

            if (
                signal.kind
                not in
                IMAGE_ANALYTICAL_SIGNAL_KINDS
            ):

                raise ValueError(
                    "Image aggregation contains "
                    "unsupported multimodal signal kind."
                )

            if (
                signal.scope
                !=
                MultimodalSignalScope.EVIDENCE
            ):

                raise ValueError(
                    "Image aggregation accepts only "
                    "single-Evidence signals."
                )

            if (
                signal.evidence_id
                !=
                self.evidence_id
            ):

                raise ValueError(
                    "Image aggregation contains signal "
                    "for another Evidence object."
                )

            if signal.kind in seen_kinds:

                raise ValueError(
                    "Duplicate image analytical signal kind."
                )

            seen_kinds.add(
                signal.kind
            )

        expected_order = tuple(
            kind
            for kind
            in IMAGE_ANALYTICAL_SIGNAL_KINDS
            if kind in seen_kinds
        )

        actual_order = tuple(
            signal.kind
            for signal
            in self.signals
        )

        if (
            actual_order
            !=
            expected_order
        ):

            raise ValueError(
                "Image analytical signals are not "
                "in canonical order."
            )

    # ==========================================================
    # Counts
    # ==========================================================

    @property
    def signal_count(
        self,
    ) -> int:

        return len(
            self.signals
        )

    @property
    def completed_count(
        self,
    ) -> int:

        return sum(
            1
            for signal
            in self.signals
            if (
                signal.status
                ==
                MultimodalSignalStatus.COMPLETED
            )
        )

    @property
    def unavailable_count(
        self,
    ) -> int:

        return sum(
            1
            for signal
            in self.signals
            if (
                signal.status
                ==
                MultimodalSignalStatus.UNAVAILABLE
            )
        )

    @property
    def skipped_count(
        self,
    ) -> int:

        return sum(
            1
            for signal
            in self.signals
            if (
                signal.status
                ==
                MultimodalSignalStatus.SKIPPED
            )
        )

    @property
    def failed_count(
        self,
    ) -> int:

        return sum(
            1
            for signal
            in self.signals
            if (
                signal.status
                ==
                MultimodalSignalStatus.FAILED
            )
        )

    # ==========================================================
    # Lookup
    # ==========================================================

    def get_signal(
        self,
        kind: MultimodalSignalKind,
    ) -> MultimodalSignalResult:
        """
        Return one image analytical signal.
        """

        if not isinstance(
            kind,
            MultimodalSignalKind,
        ):

            raise TypeError(
                "kind must be MultimodalSignalKind."
            )

        for signal in self.signals:

            if signal.kind == kind:

                return signal

        raise KeyError(
            "Image analytical signal not found."
        )

    def get_optional_signal(
        self,
        kind: MultimodalSignalKind,
    ) -> (
        MultimodalSignalResult
        | None
    ):
        """
        Return one signal or None when the corresponding
        analyzer was not part of this aggregation.
        """

        try:

            return self.get_signal(
                kind
            )

        except KeyError:

            return None


# ==========================================================
# Aggregation service
# ==========================================================


class MultimodalImageAggregationService:
    """
    Pure adapter between the existing image-analysis engine
    and Phase 6 multimodal contracts.

    It never executes an analyzer itself.
    """

    SUPPORTED_KINDS = (
        IMAGE_ANALYTICAL_SIGNAL_KINDS
    )

    # ==========================================================
    # Complete aggregation
    # ==========================================================

    def aggregate(
        self,
        *,
        evidence_id: UUID,
        results: Mapping[
            MultimodalSignalKind,
            ImageAnalysisResult,
        ],
    ) -> MultimodalImageAggregationResult:
        """
        Normalize multiple already-computed image results.

        `results` explicitly associates each existing
        ImageAnalysisResult with its semantic Phase 6 channel.

        Explicit mapping is intentional:

        we do NOT guess semantics from analyzer-name strings.
        """

        if not isinstance(
            evidence_id,
            UUID,
        ):

            raise TypeError(
                "evidence_id must be UUID."
            )

        if not isinstance(
            results,
            Mapping,
        ):

            raise TypeError(
                "results must be Mapping."
            )

        normalized: list[
            MultimodalSignalResult
        ] = []

        for kind in (
            self.SUPPORTED_KINDS
        ):

            if kind not in results:

                continue

            normalized.append(
                self.adapt(
                    evidence_id=(
                        evidence_id
                    ),
                    kind=kind,
                    result=results[
                        kind
                    ],
                )
            )

        # Reject keys that are not supported rather than
        # silently dropping them.
        unsupported = (
            set(
                results.keys()
            )
            -
            set(
                self.SUPPORTED_KINDS
            )
        )

        if unsupported:

            raise ValueError(
                "Unsupported image analytical "
                f"signal kinds: {unsupported}"
            )

        return (
            MultimodalImageAggregationResult(
                evidence_id=evidence_id,
                signals=tuple(
                    normalized
                ),
            )
        )

    # ==========================================================
    # One ImageAnalysisResult
    # ==========================================================

    def adapt(
        self,
        *,
        evidence_id: UUID,
        kind: MultimodalSignalKind,
        result: ImageAnalysisResult,
    ) -> MultimodalSignalResult:
        """
        Convert one existing ImageAnalysisResult into one
        Phase 6 MultimodalSignalResult.
        """

        if not isinstance(
            evidence_id,
            UUID,
        ):

            raise TypeError(
                "evidence_id must be UUID."
            )

        if not isinstance(
            kind,
            MultimodalSignalKind,
        ):

            raise TypeError(
                "kind must be MultimodalSignalKind."
            )

        if (
            kind
            not in
            self.SUPPORTED_KINDS
        ):

            raise ValueError(
                "Unsupported image analytical signal kind."
            )

        if not isinstance(
            result,
            ImageAnalysisResult,
        ):

            raise TypeError(
                "result must be ImageAnalysisResult."
            )

        status = (
            self._normalize_status(
                result
            )
        )

        source = str(
            result.analyzer
        ).strip()

        if not source:

            raise ValueError(
                "ImageAnalysisResult analyzer "
                "cannot be empty."
            )

        warnings = tuple(
            str(
                warning
            )
            for warning
            in result.warnings
        )

        errors = tuple(
            str(
                error
            )
            for error
            in result.errors
        )

        metadata = dict(
            result.metadata
        )

        metadata[
            "source_contract"
        ] = "ImageAnalysisResult"

        metadata[
            "phase"
        ] = "6.3"

        # ======================================================
        # Completed
        # ======================================================

        if (
            status
            ==
            MultimodalSignalStatus.COMPLETED
        ):

            return (
                MultimodalSignalResult(
                    kind=kind,
                    scope=(
                        MultimodalSignalScope.EVIDENCE
                    ),
                    status=status,
                    evidence_ids=(
                        evidence_id,
                    ),
                    source=source,
                    data=dict(
                        result.data
                    ),
                    warnings=warnings,
                    errors=(),
                    execution_time=(
                        result.execution_time
                    ),
                    metadata=metadata,
                )
            )

        # ======================================================
        # Failed
        # ======================================================

        if (
            status
            ==
            MultimodalSignalStatus.FAILED
        ):

            if not errors:

                errors = (
                    "Image analyzer failed without "
                    "an explicit error message.",
                )

            return (
                MultimodalSignalResult(
                    kind=kind,
                    scope=(
                        MultimodalSignalScope.EVIDENCE
                    ),
                    status=status,
                    evidence_ids=(
                        evidence_id,
                    ),
                    source=source,
                    data={},
                    warnings=warnings,
                    errors=errors,
                    execution_time=(
                        result.execution_time
                    ),
                    metadata=metadata,
                )
            )

        # ======================================================
        # Unavailable / skipped
        # ======================================================

        return (
            MultimodalSignalResult(
                kind=kind,
                scope=(
                    MultimodalSignalScope.EVIDENCE
                ),
                status=status,
                evidence_ids=(
                    evidence_id,
                ),
                source=source,
                data={},
                warnings=warnings,
                errors=errors,
                execution_time=(
                    result.execution_time
                ),
                metadata=metadata,
            )
        )

    # ==========================================================
    # ImageAnalysisStatus adapter
    # ==========================================================

    @staticmethod
    def _normalize_status(
        result: ImageAnalysisResult,
    ) -> MultimodalSignalStatus:
        """
        Normalize the existing ImageAnalysisStatus contract.

        We intentionally use its public enum value/name
        rather than coupling this module to internal numeric
        representation.
        """

        status = result.status

        candidates: list[
            str
        ] = []

        raw_value = getattr(
            status,
            "value",
            None,
        )

        if raw_value is not None:

            candidates.append(
                str(
                    raw_value
                )
                .strip()
                .lower()
            )

        raw_name = getattr(
            status,
            "name",
            None,
        )

        if raw_name is not None:

            candidates.append(
                str(
                    raw_name
                )
                .strip()
                .lower()
            )

        candidates.append(
            str(
                status
            )
            .strip()
            .lower()
        )

        aliases = {
            "completed": (
                MultimodalSignalStatus.COMPLETED
            ),
            "complete": (
                MultimodalSignalStatus.COMPLETED
            ),
            "success": (
                MultimodalSignalStatus.COMPLETED
            ),
            "successful": (
                MultimodalSignalStatus.COMPLETED
            ),
            "ok": (
                MultimodalSignalStatus.COMPLETED
            ),
            "unavailable": (
                MultimodalSignalStatus.UNAVAILABLE
            ),
            "skipped": (
                MultimodalSignalStatus.SKIPPED
            ),
            "skip": (
                MultimodalSignalStatus.SKIPPED
            ),
            "failed": (
                MultimodalSignalStatus.FAILED
            ),
            "failure": (
                MultimodalSignalStatus.FAILED
            ),
            "error": (
                MultimodalSignalStatus.FAILED
            ),
        }

        for candidate in candidates:

            # Handles strings such as:
            #
            # ImageAnalysisStatus.COMPLETED

            short_value = (
                candidate
                .split(
                    "."
                )[-1]
            )

            normalized = (
                aliases.get(
                    short_value
                )
            )

            if normalized is not None:

                return normalized

        raise ValueError(
            "Unsupported ImageAnalysisResult status: "
            f"{status!r}"
        )
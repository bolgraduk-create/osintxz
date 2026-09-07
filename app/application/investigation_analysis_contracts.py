"""
Application-level contracts for investigation analysis orchestration.

This module defines the immutable request, stage, progress and result
contracts used by InvestigationAnalysisOrchestrator.

Architecture boundaries:
- pure Python only
- no Qt / desktop UI dependencies
- no database writes
- no analytical algorithms
- no AI execution
- no persistence
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Mapping,
    Protocol,
)
from uuid import UUID


if TYPE_CHECKING:

    from app.services.investigation_unified_analytical_context_service import (
        InvestigationUnifiedAnalyticalContext,
    )


# ==========================================================
# Stage definitions
# ==========================================================


class InvestigationAnalysisStage(
    str,
    Enum,
):
    """
    Canonical stages of one investigation analysis run.
    """

    CASE_VALIDATION = "case_validation"

    ENTITY_RESOLUTION = "entity_resolution"
    EVIDENCE = "evidence"

    GRAPH = "graph"
    TEMPORAL = "temporal"

    ANOMALY = "anomaly"
    CLUSTERING = "clustering"

    MULTIMODAL = "multimodal"

    RAG = "rag"

    UNIFIED_CONTEXT = "unified_context"


CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER: tuple[
    InvestigationAnalysisStage,
    ...,
] = (
    InvestigationAnalysisStage.CASE_VALIDATION,
    InvestigationAnalysisStage.ENTITY_RESOLUTION,
    InvestigationAnalysisStage.EVIDENCE,
    InvestigationAnalysisStage.GRAPH,
    InvestigationAnalysisStage.TEMPORAL,
    InvestigationAnalysisStage.ANOMALY,
    InvestigationAnalysisStage.CLUSTERING,
    InvestigationAnalysisStage.MULTIMODAL,
    InvestigationAnalysisStage.RAG,
    InvestigationAnalysisStage.UNIFIED_CONTEXT,
)


DEFAULT_INVESTIGATION_ANALYSIS_STAGES: tuple[
    InvestigationAnalysisStage,
    ...,
] = (
    CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER
)


INVESTIGATION_ANALYSIS_STAGE_DEPENDENCIES: Mapping[
    InvestigationAnalysisStage,
    tuple[
        InvestigationAnalysisStage,
        ...,
    ],
] = MappingProxyType(
    {
        InvestigationAnalysisStage.ANOMALY: (
            InvestigationAnalysisStage.GRAPH,
            InvestigationAnalysisStage.TEMPORAL,
        ),
        InvestigationAnalysisStage.CLUSTERING: (
            InvestigationAnalysisStage.GRAPH,
            InvestigationAnalysisStage.TEMPORAL,
        ),
    }
)


# ==========================================================
# Stage status
# ==========================================================


class InvestigationAnalysisStageStatus(
    str,
    Enum,
):
    """
    Final outcome of one executed analysis stage.
    """

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ==========================================================
# Overall analysis status
# ==========================================================


class InvestigationAnalysisStatus(
    str,
    Enum,
):
    """
    Final outcome of one orchestrator run.
    """

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ==========================================================
# Progress event type
# ==========================================================


class InvestigationAnalysisProgressEventType(
    str,
    Enum,
):
    """
    Machine-readable progress event type.
    """

    ANALYSIS_STARTED = "analysis_started"
    STAGE_STARTED = "stage_started"
    STAGE_FINISHED = "stage_finished"
    ANALYSIS_FINISHED = "analysis_finished"


# ==========================================================
# Request
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationAnalysisRequest:
    """
    Immutable request for one orchestrated investigation analysis.

    requested_stages=None means the standard full analysis pipeline.

    Stage ordering, dependency expansion and UUID normalization are
    responsibilities of the orchestrator.
    """

    case_id: str | UUID

    question: str | None = None

    requested_stages: (
        tuple[
            InvestigationAnalysisStage,
            ...,
        ]
        | None
    ) = None

    metadata: Mapping[
        str,
        Any,
    ] | None = None

    def __post_init__(
        self,
    ) -> None:
        """
        Validate only contract-level invariants.
        """

        if isinstance(
            self.case_id,
            str,
        ):

            normalized_case_id = (
                self.case_id.strip()
            )

            if not normalized_case_id:

                raise ValueError(
                    "case_id cannot be empty."
                )

            object.__setattr__(
                self,
                "case_id",
                normalized_case_id,
            )

        elif not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be a string or UUID."
            )

        if self.question is not None:

            normalized_question = (
                str(
                    self.question
                )
                .strip()
            )

            object.__setattr__(
                self,
                "question",
                (
                    normalized_question
                    or None
                ),
            )

        if (
            self.requested_stages
            is not None
        ):

            if not isinstance(
                self.requested_stages,
                tuple,
            ):

                raise TypeError(
                    "requested_stages must be "
                    "a tuple or None."
                )

            if not self.requested_stages:

                raise ValueError(
                    "requested_stages cannot be empty."
                )

            for stage in self.requested_stages:

                if not isinstance(
                    stage,
                    InvestigationAnalysisStage,
                ):

                    raise TypeError(
                        "requested_stages must contain "
                        "InvestigationAnalysisStage values."
                    )

        if self.metadata is not None:

            if not isinstance(
                self.metadata,
                Mapping,
            ):

                raise TypeError(
                    "metadata must be a mapping or None."
                )

            object.__setattr__(
                self,
                "metadata",
                MappingProxyType(
                    dict(
                        self.metadata
                    )
                ),
            )


# ==========================================================
# Stage error
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationAnalysisStageError:
    """
    Safe structured error information for one failed stage.

    Technical tracebacks belong in application logs and are
    intentionally not part of this contract.
    """

    error_type: str
    message: str

    def __post_init__(
        self,
    ) -> None:

        normalized_error_type = str(
            self.error_type
            or ""
        ).strip()

        normalized_message = str(
            self.message
            or ""
        ).strip()

        if not normalized_error_type:

            raise ValueError(
                "error_type cannot be empty."
            )

        if not normalized_message:

            raise ValueError(
                "message cannot be empty."
            )

        object.__setattr__(
            self,
            "error_type",
            normalized_error_type,
        )

        object.__setattr__(
            self,
            "message",
            normalized_message,
        )


# ==========================================================
# Stage result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationAnalysisStageResult:
    """
    Immutable final result of one analysis stage.

    result stores the original production result object without
    converting it into an untyped dictionary.
    """

    stage: InvestigationAnalysisStage

    status: InvestigationAnalysisStageStatus

    duration_seconds: float = 0.0

    result: object | None = None

    warnings: tuple[
        str,
        ...,
    ] = ()

    error: (
        InvestigationAnalysisStageError
        | None
    ) = None

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.stage,
            InvestigationAnalysisStage,
        ):

            raise TypeError(
                "stage must be "
                "InvestigationAnalysisStage."
            )

        if not isinstance(
            self.status,
            InvestigationAnalysisStageStatus,
        ):

            raise TypeError(
                "status must be "
                "InvestigationAnalysisStageStatus."
            )

        normalized_duration = float(
            self.duration_seconds
        )

        if normalized_duration < 0.0:

            raise ValueError(
                "duration_seconds cannot be negative."
            )

        object.__setattr__(
            self,
            "duration_seconds",
            normalized_duration,
        )

        normalized_warnings = tuple(
            str(
                warning
            ).strip()
            for warning in self.warnings
            if str(
                warning
            ).strip()
        )

        object.__setattr__(
            self,
            "warnings",
            normalized_warnings,
        )

        if (
            self.status
            == InvestigationAnalysisStageStatus.FAILED
        ):

            if self.error is None:

                raise ValueError(
                    "FAILED stage requires an error."
                )

        elif self.error is not None:

            raise ValueError(
                "Only FAILED stage may contain an error."
            )


# ==========================================================
# Analysis result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationAnalysisResult:
    """
    Immutable runtime result of one complete orchestrator run.

    This object is not an ORM model and does not imply persistence.
    """

    case_id: UUID

    status: InvestigationAnalysisStatus

    stage_results: tuple[
        InvestigationAnalysisStageResult,
        ...,
    ]

    unified_context: (
        InvestigationUnifiedAnalyticalContext
        | None
    ) = None

    duration_seconds: float = 0.0

    warnings: tuple[
        str,
        ...,
    ] = ()

    metadata: Mapping[
        str,
        Any,
    ] | None = None

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.status,
            InvestigationAnalysisStatus,
        ):

            raise TypeError(
                "status must be "
                "InvestigationAnalysisStatus."
            )

        if not isinstance(
            self.stage_results,
            tuple,
        ):

            raise TypeError(
                "stage_results must be a tuple."
            )

        seen_stages: set[
            InvestigationAnalysisStage
        ] = set()

        for stage_result in self.stage_results:

            if not isinstance(
                stage_result,
                InvestigationAnalysisStageResult,
            ):

                raise TypeError(
                    "stage_results must contain "
                    "InvestigationAnalysisStageResult values."
                )

            if (
                stage_result.stage
                in seen_stages
            ):

                raise ValueError(
                    "stage_results cannot contain "
                    "duplicate stages."
                )

            seen_stages.add(
                stage_result.stage
            )

        normalized_duration = float(
            self.duration_seconds
        )

        if normalized_duration < 0.0:

            raise ValueError(
                "duration_seconds cannot be negative."
            )

        object.__setattr__(
            self,
            "duration_seconds",
            normalized_duration,
        )

        normalized_warnings = tuple(
            str(
                warning
            ).strip()
            for warning in self.warnings
            if str(
                warning
            ).strip()
        )

        object.__setattr__(
            self,
            "warnings",
            normalized_warnings,
        )

        if self.metadata is not None:

            if not isinstance(
                self.metadata,
                Mapping,
            ):

                raise TypeError(
                    "metadata must be a mapping or None."
                )

            object.__setattr__(
                self,
                "metadata",
                MappingProxyType(
                    dict(
                        self.metadata
                    )
                ),
            )

    def get_stage(
        self,
        stage: InvestigationAnalysisStage,
    ) -> InvestigationAnalysisStageResult | None:
        """
        Return the result of one stage.
        """

        for stage_result in self.stage_results:

            if stage_result.stage == stage:

                return stage_result

        return None

    def successful(
        self,
    ) -> bool:
        """
        Return True only for a completely successful run.
        """

        return (
            self.status
            == InvestigationAnalysisStatus.SUCCESS
        )

    def has_partial_result(
        self,
    ) -> bool:
        """
        Return True when the run produced a usable normal result.
        """

        return self.status in {
            InvestigationAnalysisStatus.SUCCESS,
            InvestigationAnalysisStatus.PARTIAL,
        }

    def successful_stage_count(
        self,
    ) -> int:
        """
        Count successfully completed stages.
        """

        return sum(
            1
            for item in self.stage_results
            if (
                item.status
                == InvestigationAnalysisStageStatus.SUCCESS
            )
        )

    def failed_stage_count(
        self,
    ) -> int:
        """
        Count failed stages.
        """

        return sum(
            1
            for item in self.stage_results
            if (
                item.status
                == InvestigationAnalysisStageStatus.FAILED
            )
        )

    def skipped_stage_count(
        self,
    ) -> int:
        """
        Count skipped stages.
        """

        return sum(
            1
            for item in self.stage_results
            if (
                item.status
                == InvestigationAnalysisStageStatus.SKIPPED
            )
        )

    def cancelled_stage_count(
        self,
    ) -> int:
        """
        Count cancelled stages.
        """

        return sum(
            1
            for item in self.stage_results
            if (
                item.status
                == InvestigationAnalysisStageStatus.CANCELLED
            )
        )


# ==========================================================
# Progress
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationAnalysisProgressEvent:
    """
    Lightweight progress event emitted by the orchestrator.

    The application layer remains UI-framework independent.
    """

    case_id: UUID

    event_type: (
        InvestigationAnalysisProgressEventType
    )

    stage: (
        InvestigationAnalysisStage
        | None
    ) = None

    stage_status: (
        InvestigationAnalysisStageStatus
        | None
    ) = None

    stage_index: int = 0
    stage_count: int = 0

    message: str = ""

    metadata: Mapping[
        str,
        Any,
    ] | None = None

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.event_type,
            InvestigationAnalysisProgressEventType,
        ):

            raise TypeError(
                "event_type must be "
                "InvestigationAnalysisProgressEventType."
            )

        normalized_index = int(
            self.stage_index
        )

        normalized_count = int(
            self.stage_count
        )

        if normalized_index < 0:

            raise ValueError(
                "stage_index cannot be negative."
            )

        if normalized_count < 0:

            raise ValueError(
                "stage_count cannot be negative."
            )

        if (
            normalized_count > 0
            and normalized_index
            > normalized_count
        ):

            raise ValueError(
                "stage_index cannot exceed stage_count."
            )

        object.__setattr__(
            self,
            "stage_index",
            normalized_index,
        )

        object.__setattr__(
            self,
            "stage_count",
            normalized_count,
        )

        object.__setattr__(
            self,
            "message",
            str(
                self.message
                or ""
            ).strip(),
        )

        if (
            self.event_type
            == InvestigationAnalysisProgressEventType.STAGE_STARTED
        ):

            if self.stage is None:

                raise ValueError(
                    "STAGE_STARTED requires a stage."
                )

            if self.stage_status is not None:

                raise ValueError(
                    "STAGE_STARTED cannot contain "
                    "a final stage_status."
                )

        elif (
            self.event_type
            == InvestigationAnalysisProgressEventType.STAGE_FINISHED
        ):

            if self.stage is None:

                raise ValueError(
                    "STAGE_FINISHED requires a stage."
                )

            if self.stage_status is None:

                raise ValueError(
                    "STAGE_FINISHED requires stage_status."
                )

        else:

            if self.stage is not None:

                raise ValueError(
                    "Analysis-level progress events "
                    "cannot contain a stage."
                )

            if self.stage_status is not None:

                raise ValueError(
                    "Analysis-level progress events "
                    "cannot contain stage_status."
                )

        if self.metadata is not None:

            if not isinstance(
                self.metadata,
                Mapping,
            ):

                raise TypeError(
                    "metadata must be a mapping or None."
                )

            object.__setattr__(
                self,
                "metadata",
                MappingProxyType(
                    dict(
                        self.metadata
                    )
                ),
            )

    def progress_fraction(
        self,
    ) -> float:
        """
        Return normalized progress in the [0.0, 1.0] range.
        """

        if self.stage_count <= 0:

            return 0.0

        return min(
            1.0,
            max(
                0.0,
                self.stage_index
                / self.stage_count,
            ),
        )


InvestigationAnalysisProgressCallback = Callable[
    [
        InvestigationAnalysisProgressEvent,
    ],
    None,
]


# ==========================================================
# Cancellation
# ==========================================================


class InvestigationAnalysisCancellationToken(
    Protocol,
):
    """
    Framework-independent cooperative cancellation contract.
    """

    def is_cancelled(
        self,
    ) -> bool:
        """
        Return True when cancellation has been requested.
        """

        ...


# ==========================================================
# Public exports
# ==========================================================


__all__ = [
    "CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER",
    "DEFAULT_INVESTIGATION_ANALYSIS_STAGES",
    "INVESTIGATION_ANALYSIS_STAGE_DEPENDENCIES",
    "InvestigationAnalysisCancellationToken",
    "InvestigationAnalysisProgressCallback",
    "InvestigationAnalysisProgressEvent",
    "InvestigationAnalysisProgressEventType",
    "InvestigationAnalysisRequest",
    "InvestigationAnalysisResult",
    "InvestigationAnalysisStage",
    "InvestigationAnalysisStageError",
    "InvestigationAnalysisStageResult",
    "InvestigationAnalysisStageStatus",
    "InvestigationAnalysisStatus",
]

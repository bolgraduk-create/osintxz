"""
Video frame analysis service.

Block 8 — Multimodal Analysis / Video Frame Analysis.

Architecture:

video file
    ↓
VideoFrameAnalysisService
    ↓
PyAV temporal sampling
    ↓
temporary PNG frames
    ↓
ImageAnalysisPipeline
    ├── image_embeddings
    └── ocr
    ↓
per-frame analytical results
    ↓
MultimodalSignalKind.VIDEO_FRAME_ANALYSIS


Important boundaries:

frame similarity
    != identity

OCR text
    != verified fact

image embedding
    != Evidence confidence

video frame signal
    != proof of an event


The service performs no database access or persistence.
Temporary extracted frames are deleted after analysis.
"""

from __future__ import annotations

import math

import tempfile

from pathlib import (
    Path,
)

from time import (
    perf_counter,
)

from typing import (
    Any,
)

from uuid import (
    UUID,
)

import av

from app.analysis.images.image_analysis_context import (
    ImageAnalysisContext,
)

from app.analysis.images.image_analysis_pipeline import (
    ImageAnalysisPipeline,
)

from app.analysis.multimodal_contracts import (
    MultimodalSignalKind,
    MultimodalSignalResult,
    MultimodalSignalScope,
    MultimodalSignalStatus,
)


# ==========================================================
# Defaults
# ==========================================================


DEFAULT_VIDEO_FRAME_CACHE_DIR = Path(
    "storage/cache/video_frame_analysis"
)

DEFAULT_VIDEO_FRAME_ANALYZERS: tuple[
    str,
    ...,
] = (
    "image_embeddings",
    "ocr",
)

DEFAULT_MAX_FRAMES = 4

DEFAULT_SAMPLE_INTERVAL_SECONDS = 10.0


# ==========================================================
# Service
# ==========================================================


class VideoFrameAnalysisService:
    """
    Extract a small representative set of video frames
    and reuse the existing image-analysis pipeline.
    """

    def __init__(
        self,
        image_pipeline: (
            ImageAnalysisPipeline
            |
            None
        ) = None,
    ) -> None:

        self.image_pipeline = (
            image_pipeline
            or
            ImageAnalysisPipeline()
        )

    # ======================================================
    # Analysis
    # ======================================================

    def analyze(
        self,
        video_path: str | Path,
        *,
        max_frames: int = DEFAULT_MAX_FRAMES,
        sample_interval_seconds: float = (
            DEFAULT_SAMPLE_INTERVAL_SECONDS
        ),
        analyzers: tuple[
            str,
            ...,
        ] = DEFAULT_VIDEO_FRAME_ANALYZERS,
        cache_dir: str | Path = (
            DEFAULT_VIDEO_FRAME_CACHE_DIR
        ),
        image_options: (
            dict[
                str,
                Any,
            ]
            |
            None
        ) = None,
    ) -> dict[str, Any]:
        """
        Analyze representative frames from one video.

        Sampling strategy:

        - determine video duration when available;
        - estimate how many temporal samples are useful;
        - cap samples at `max_frames`;
        - choose uniform midpoint timestamps;
        - analyze only those frames.

        For containers without usable duration metadata,
        sequential interval sampling is used as fallback.
        """

        started_at = (
            perf_counter()
        )

        # ==================================================
        # Validate input
        # ==================================================

        path = Path(
            video_path
        )

        if not path.exists():

            return self._failed_result(
                error=(
                    "Video file does not exist: "
                    f"{path}"
                ),
                execution_time=(
                    perf_counter()
                    -
                    started_at
                ),
            )

        if not path.is_file():

            return self._failed_result(
                error=(
                    "Video path is not a file: "
                    f"{path}"
                ),
                execution_time=(
                    perf_counter()
                    -
                    started_at
                ),
            )

        try:

            normalized_max_frames = (
                self._normalize_max_frames(
                    max_frames
                )
            )

            normalized_interval = (
                self._normalize_interval(
                    sample_interval_seconds
                )
            )

            normalized_analyzers = (
                self._normalize_analyzers(
                    analyzers
                )
            )

        except Exception as error:

            return self._failed_result(
                error=str(
                    error
                ),
                execution_time=(
                    perf_counter()
                    -
                    started_at
                ),
            )

        cache_root = Path(
            cache_dir
        )

        cache_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        options = {
            "image_embedding_cache_dir": (
                "storage/cache/fastembed_models"
            ),
            "image_embedding_local_files_only": (
                True
            ),
            "ocr_profile": "cyrillic",
        }

        if image_options:

            options.update(
                image_options
            )

        # ==================================================
        # Open video
        # ==================================================

        try:

            container = av.open(
                str(
                    path
                )
            )

        except Exception as error:

            return self._failed_result(
                error=(
                    "Video could not be opened: "
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
                execution_time=(
                    perf_counter()
                    -
                    started_at
                ),
            )

        try:

            video_streams = list(
                container.streams.video
            )

            if not video_streams:

                return self._failed_result(
                    error=(
                        "Video contains no video stream."
                    ),
                    execution_time=(
                        perf_counter()
                        -
                        started_at
                    ),
                )

            stream = video_streams[
                0
            ]

            duration_seconds = (
                self._resolve_duration(
                    container=container,
                    stream=stream,
                )
            )

        finally:

            container.close()

        # ==================================================
        # Extract + analyze
        # ==================================================

        frames: list[
            dict[
                str,
                Any,
            ]
        ] = []

        warnings: list[
            str
        ] = []

        with tempfile.TemporaryDirectory(
            prefix="video_frames_",
            dir=str(
                cache_root
            ),
        ) as temporary_directory:

            temporary_path = Path(
                temporary_directory
            )

            if (
                duration_seconds
                is not None
                and
                duration_seconds
                >
                0.0
            ):

                target_times = (
                    self._build_target_times(
                        duration_seconds=(
                            duration_seconds
                        ),
                        max_frames=(
                            normalized_max_frames
                        ),
                        interval_seconds=(
                            normalized_interval
                        ),
                    )
                )

                sampling_strategy = (
                    "uniform_time_midpoints"
                )

                extracted = (
                    self._extract_at_times(
                        path=path,
                        target_times=(
                            target_times
                        ),
                    )
                )

            else:

                sampling_strategy = (
                    "sequential_interval_fallback"
                )

                warnings.append(
                    (
                        "Video duration was unavailable; "
                        "sequential interval sampling "
                        "was used."
                    )
                )

                extracted = (
                    self._extract_sequential(
                        path=path,
                        max_frames=(
                            normalized_max_frames
                        ),
                        interval_seconds=(
                            normalized_interval
                        ),
                    )
                )

            for index, item in enumerate(
                extracted
            ):

                frame = item[
                    "frame"
                ]

                timestamp_seconds = item[
                    "timestamp_seconds"
                ]

                frame_path = (
                    temporary_path
                    /
                    f"frame_{index:04d}.png"
                )

                try:

                    image = (
                        frame
                        .to_image()
                        .convert(
                            "RGB"
                        )
                    )

                    image.save(
                        frame_path,
                        format="PNG",
                    )

                except Exception as error:

                    warnings.append(
                        (
                            "Frame "
                            f"{index} could not be "
                            "serialized: "
                            f"{type(error).__name__}: "
                            f"{error}"
                        )
                    )

                    continue

                context = (
                    ImageAnalysisContext(
                        image_path=(
                            frame_path
                        ),
                        options=dict(
                            options
                        ),
                    )
                )

                analytical_results: dict[
                    str,
                    Any,
                ] = {}

                for analyzer_name in (
                    normalized_analyzers
                ):

                    try:

                        analytical_results[
                            analyzer_name
                        ] = (
                            self.image_pipeline
                            .analyze(
                                analyzer_name,
                                context,
                            )
                        )

                    except Exception as error:

                        analytical_results[
                            analyzer_name
                        ] = {
                            "analyzer": (
                                analyzer_name
                            ),
                            "status": "failed",
                            "successful": False,
                            "data": {},
                            "warnings": [],
                            "errors": [
                                (
                                    f"{type(error).__name__}: "
                                    f"{error}"
                                )
                            ],
                        }

                frames.append(
                    {
                        "index": index,
                        "timestamp_seconds": (
                            timestamp_seconds
                        ),
                        "pts": (
                            item.get(
                                "pts"
                            )
                        ),
                        "width": (
                            frame.width
                        ),
                        "height": (
                            frame.height
                        ),
                        "analyses": (
                            analytical_results
                        ),
                    }
                )

        # ==================================================
        # Result
        # ==================================================

        if not frames:

            return self._failed_result(
                error=(
                    "No video frames could be "
                    "extracted for analysis."
                ),
                execution_time=(
                    perf_counter()
                    -
                    started_at
                ),
                metadata={
                    "source_path": str(
                        path
                    ),
                    "sampling_strategy": (
                        sampling_strategy
                    ),
                },
            )

        execution_time = (
            perf_counter()
            -
            started_at
        )

        return {
            "status": "completed",
            "data": {
                "frame_count": len(
                    frames
                ),
                "max_frames": (
                    normalized_max_frames
                ),
                "sample_interval_seconds": (
                    normalized_interval
                ),
                "duration_seconds": (
                    duration_seconds
                ),
                "sampling_strategy": (
                    sampling_strategy
                ),
                "analyzers": list(
                    normalized_analyzers
                ),
                "frames": frames,
            },
            "warnings": warnings,
            "errors": [],
            "execution_time": (
                execution_time
            ),
            "metadata": {
                "source_path": str(
                    path
                ),
                "backend": "pyav",
                "image_pipeline": (
                    "ImageAnalysisPipeline"
                ),
                "temporary_frames": True,
                "temporary_frames_persisted": (
                    False
                ),
                "database_access": False,
            },
        }

    # ======================================================
    # Duration
    # ======================================================

    @staticmethod
    def _resolve_duration(
        *,
        container: Any,
        stream: Any,
    ) -> float | None:

        if (
            stream.duration
            is not None
            and
            stream.time_base
            is not None
        ):

            try:

                value = (
                    float(
                        stream.duration
                    )
                    *
                    float(
                        stream.time_base
                    )
                )

                if value > 0.0:

                    return value

            except (
                TypeError,
                ValueError,
            ):

                pass

        if (
            container.duration
            is not None
        ):

            try:

                value = (
                    float(
                        container.duration
                    )
                    /
                    float(
                        av.time_base
                    )
                )

                if value > 0.0:

                    return value

            except (
                TypeError,
                ValueError,
            ):

                pass

        return None

    # ======================================================
    # Uniform sampling
    # ======================================================

    @staticmethod
    def _build_target_times(
        *,
        duration_seconds: float,
        max_frames: int,
        interval_seconds: float,
    ) -> tuple[
        float,
        ...,
    ]:

        estimated_count = max(
            1,
            math.ceil(
                duration_seconds
                /
                interval_seconds
            ),
        )

        count = min(
            max_frames,
            estimated_count,
        )

        segment_size = (
            duration_seconds
            /
            count
        )

        return tuple(
            (
                index
                +
                0.5
            )
            *
            segment_size
            for index
            in range(
                count
            )
        )

    # ======================================================
    # Seek-based extraction
    # ======================================================

    @staticmethod
    def _extract_at_times(
        *,
        path: Path,
        target_times: tuple[
            float,
            ...,
        ],
    ) -> list[
        dict[
            str,
            Any,
        ]
    ]:

        results: list[
            dict[
                str,
                Any,
            ]
        ] = []

        seen_pts: set[
            int
        ] = set()

        container = av.open(
            str(
                path
            )
        )

        try:

            stream = list(
                container.streams.video
            )[
                0
            ]

            time_base = float(
                stream.time_base
            )

            for target_seconds in (
                target_times
            ):

                target_pts = int(
                    target_seconds
                    /
                    time_base
                )

                container.seek(
                    target_pts,
                    stream=stream,
                    backward=True,
                    any_frame=False,
                )

                selected = None

                for frame in container.decode(
                    video=0
                ):

                    if frame.pts is None:

                        continue

                    timestamp = (
                        float(
                            frame.pts
                        )
                        *
                        time_base
                    )

                    selected = (
                        frame,
                        timestamp,
                    )

                    if (
                        timestamp
                        >=
                        target_seconds
                    ):

                        break

                if selected is None:

                    continue

                frame, timestamp = (
                    selected
                )

                pts = frame.pts

                if (
                    pts is not None
                    and
                    pts in seen_pts
                ):

                    continue

                if pts is not None:

                    seen_pts.add(
                        pts
                    )

                results.append(
                    {
                        "frame": frame,
                        "timestamp_seconds": (
                            timestamp
                        ),
                        "pts": pts,
                    }
                )

        finally:

            container.close()

        return results

    # ======================================================
    # Fallback sequential extraction
    # ======================================================

    @staticmethod
    def _extract_sequential(
        *,
        path: Path,
        max_frames: int,
        interval_seconds: float,
    ) -> list[
        dict[
            str,
            Any,
        ]
    ]:

        results: list[
            dict[
                str,
                Any,
            ]
        ] = []

        container = av.open(
            str(
                path
            )
        )

        try:

            stream = list(
                container.streams.video
            )[
                0
            ]

            time_base = (
                float(
                    stream.time_base
                )
                if (
                    stream.time_base
                    is not None
                )
                else
                None
            )

            next_timestamp = 0.0

            for frame in container.decode(
                video=0
            ):

                if (
                    len(
                        results
                    )
                    >=
                    max_frames
                ):

                    break

                if (
                    frame.pts is not None
                    and
                    time_base is not None
                ):

                    timestamp = (
                        float(
                            frame.pts
                        )
                        *
                        time_base
                    )

                elif frame.time is not None:

                    timestamp = float(
                        frame.time
                    )

                else:

                    timestamp = 0.0

                if (
                    results
                    and
                    timestamp
                    <
                    next_timestamp
                ):

                    continue

                results.append(
                    {
                        "frame": frame,
                        "timestamp_seconds": (
                            timestamp
                        ),
                        "pts": frame.pts,
                    }
                )

                next_timestamp = (
                    timestamp
                    +
                    interval_seconds
                )

        finally:

            container.close()

        return results

    # ======================================================
    # Multimodal bridge
    # ======================================================

    def to_multimodal_signal(
        self,
        *,
        evidence_id: UUID,
        result: dict[str, Any],
    ) -> MultimodalSignalResult:

        if not isinstance(
            evidence_id,
            UUID,
        ):

            raise TypeError(
                "evidence_id must be UUID."
            )

        if not isinstance(
            result,
            dict,
        ):

            raise TypeError(
                "result must be dict."
            )

        status_value = str(
            result.get(
                "status",
                "failed",
            )
        ).strip().lower()

        status_map = {
            "completed": (
                MultimodalSignalStatus.COMPLETED
            ),
            "unavailable": (
                MultimodalSignalStatus.UNAVAILABLE
            ),
            "skipped": (
                MultimodalSignalStatus.SKIPPED
            ),
            "failed": (
                MultimodalSignalStatus.FAILED
            ),
        }

        status = status_map.get(
            status_value,
            MultimodalSignalStatus.FAILED,
        )

        data = result.get(
            "data",
            {},
        )

        warnings = result.get(
            "warnings",
            [],
        )

        errors = result.get(
            "errors",
            [],
        )

        metadata = result.get(
            "metadata",
            {},
        )

        execution_time = result.get(
            "execution_time"
        )

        try:

            execution_time = (
                float(
                    execution_time
                )
                if execution_time
                is not None
                else
                None
            )

        except (
            TypeError,
            ValueError,
        ):

            execution_time = None

        return MultimodalSignalResult(
            kind=(
                MultimodalSignalKind
                .VIDEO_FRAME_ANALYSIS
            ),
            scope=(
                MultimodalSignalScope
                .EVIDENCE
            ),
            status=status,
            evidence_ids=(
                evidence_id,
            ),
            source=(
                "VideoFrameAnalysisService"
            ),
            data=(
                dict(
                    data
                )
                if (
                    status
                    ==
                    MultimodalSignalStatus.COMPLETED
                    and
                    isinstance(
                        data,
                        dict,
                    )
                )
                else
                {}
            ),
            warnings=tuple(
                str(
                    value
                )
                for value
                in warnings
            ),
            errors=tuple(
                str(
                    value
                )
                for value
                in errors
            ),
            execution_time=(
                execution_time
            ),
            metadata=(
                dict(
                    metadata
                )
                if isinstance(
                    metadata,
                    dict,
                )
                else
                {}
            ),
        )

    # ======================================================
    # Validation
    # ======================================================

    @staticmethod
    def _normalize_max_frames(
        value: Any,
    ) -> int:

        if (
            isinstance(
                value,
                bool,
            )
            or
            not isinstance(
                value,
                int,
            )
            or
            value
            <
            1
        ):

            raise ValueError(
                "max_frames must be "
                "a positive integer."
            )

        return value

    @staticmethod
    def _normalize_interval(
        value: Any,
    ) -> float:

        if isinstance(
            value,
            bool,
        ):

            raise TypeError(
                "sample_interval_seconds "
                "must be numeric."
            )

        try:

            result = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "sample_interval_seconds "
                "must be numeric."
            ) from error

        if not math.isfinite(
            result
        ):

            raise ValueError(
                "sample_interval_seconds "
                "must be finite."
            )

        if result <= 0.0:

            raise ValueError(
                "sample_interval_seconds "
                "must be greater than zero."
            )

        return result

    @staticmethod
    def _normalize_analyzers(
        value: Any,
    ) -> tuple[
        str,
        ...,
    ]:

        if not isinstance(
            value,
            tuple,
        ):

            raise TypeError(
                "analyzers must be tuple[str, ...]."
            )

        normalized: list[
            str
        ] = []

        seen: set[
            str
        ] = set()

        for analyzer in value:

            if not isinstance(
                analyzer,
                str,
            ):

                raise TypeError(
                    "analyzers must contain "
                    "strings."
                )

            name = (
                analyzer
                .strip()
                .lower()
            )

            if not name:

                raise ValueError(
                    "Analyzer name cannot be empty."
                )

            if name in seen:

                continue

            seen.add(
                name
            )

            normalized.append(
                name
            )

        if not normalized:

            raise ValueError(
                "At least one frame analyzer "
                "is required."
            )

        return tuple(
            normalized
        )

    # ======================================================
    # Failure
    # ======================================================

    @staticmethod
    def _failed_result(
        *,
        error: str,
        execution_time: float,
        metadata: (
            dict[
                str,
                Any,
            ]
            |
            None
        ) = None,
    ) -> dict[str, Any]:

        return {
            "status": "failed",
            "data": {},
            "warnings": [],
            "errors": [
                str(
                    error
                )
            ],
            "execution_time": (
                execution_time
            ),
            "metadata": (
                metadata
                or
                {}
            ),
        }
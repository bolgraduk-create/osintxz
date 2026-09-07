"""
Video processor.

Block 8 — Multimodal Analysis.

Responsible for:

- basic video-file inspection
- local speech transcription from the video audio track
- transcription language detection
- transcription timestamps
- representative video-frame extraction
- image embedding analysis on sampled frames
- OCR analysis on sampled frames

Architecture:

video file
    ↓
VideoProcessor
    ├── FileProcessor
    │
    ├── VideoTranscriptionService
    │       ↓
    │   AudioTranscriptionService
    │       ↓
    │   PyAV
    │       ↓
    │   faster-whisper / CTranslate2
    │
    └── VideoFrameAnalysisService
            ↓
        PyAV temporal sampling
            ↓
        ImageAnalysisPipeline
            ├── image_embeddings
            └── OCR


Future stages may add:

- detailed container metadata
- codec detection
- scene detection
- richer visual event analysis

Video inspection remains valid if transcription or frame
analysis fails. Analytical failures are preserved in their
own nested result and exposed as warnings.

Does not access the database.
"""

from __future__ import annotations

import math
import mimetypes

from pathlib import (
    Path,
)

from typing import (
    Any,
)

from app.analysis.video_frame_analysis_service import (
    DEFAULT_MAX_FRAMES,
    DEFAULT_SAMPLE_INTERVAL_SECONDS,
    DEFAULT_VIDEO_FRAME_ANALYZERS,
    VideoFrameAnalysisService,
)

from app.analysis.video_transcription_service import (
    VideoTranscriptionService,
)

from app.processing.base_processor import (
    BaseProcessor,
)

from app.processing.file_processor import (
    FileProcessor,
)


class VideoProcessor(
    BaseProcessor,
):
    """
    Process video files and execute enabled
    multimodal video analysis.
    """

    SUPPORTED_EXTENSIONS = {
        ".mp4",
        ".mkv",
        ".mov",
        ".avi",
        ".webm",
        ".m4v",
        ".mpeg",
        ".mpg",
        ".wmv",
    }

    def __init__(
        self,
        file_processor: FileProcessor | None = None,
        *,
        transcription_service: (
            VideoTranscriptionService
            |
            None
        ) = None,
        frame_analysis_service: (
            VideoFrameAnalysisService
            |
            None
        ) = None,

        # --------------------------------------------------
        # Transcription
        # --------------------------------------------------

        enable_transcription: bool = True,
        transcription_language: str | None = None,
        transcription_model_name: str = "small",
        transcription_local_files_only: bool = True,
        transcription_word_timestamps: bool = True,
        transcription_vad_filter: bool = True,
        transcription_beam_size: int = 5,

        # --------------------------------------------------
        # Frame analysis
        # --------------------------------------------------

        enable_frame_analysis: bool = True,
        frame_analysis_max_frames: int = (
            DEFAULT_MAX_FRAMES
        ),
        frame_analysis_sample_interval_seconds: float = (
            DEFAULT_SAMPLE_INTERVAL_SECONDS
        ),
        frame_analysis_analyzers: tuple[
            str,
            ...,
        ] = DEFAULT_VIDEO_FRAME_ANALYZERS,
        frame_analysis_image_options: (
            dict[
                str,
                Any,
            ]
            |
            None
        ) = None,
    ) -> None:

        # ==================================================
        # Dependencies
        # ==================================================

        self.file_processor = (
            file_processor
            or
            FileProcessor()
        )

        self.transcription_service = (
            transcription_service
            or
            VideoTranscriptionService()
        )

        self.frame_analysis_service = (
            frame_analysis_service
            or
            VideoFrameAnalysisService()
        )

        # ==================================================
        # Transcription validation
        # ==================================================

        if not isinstance(
            enable_transcription,
            bool,
        ):

            raise TypeError(
                "enable_transcription must be bool."
            )

        if not isinstance(
            transcription_local_files_only,
            bool,
        ):

            raise TypeError(
                "transcription_local_files_only "
                "must be bool."
            )

        if not isinstance(
            transcription_word_timestamps,
            bool,
        ):

            raise TypeError(
                "transcription_word_timestamps "
                "must be bool."
            )

        if not isinstance(
            transcription_vad_filter,
            bool,
        ):

            raise TypeError(
                "transcription_vad_filter "
                "must be bool."
            )

        if (
            isinstance(
                transcription_beam_size,
                bool,
            )
            or
            not isinstance(
                transcription_beam_size,
                int,
            )
            or
            transcription_beam_size
            <
            1
        ):

            raise ValueError(
                "transcription_beam_size must "
                "be a positive integer."
            )

        # ==================================================
        # Frame-analysis validation
        # ==================================================

        if not isinstance(
            enable_frame_analysis,
            bool,
        ):

            raise TypeError(
                "enable_frame_analysis must be bool."
            )

        if (
            isinstance(
                frame_analysis_max_frames,
                bool,
            )
            or
            not isinstance(
                frame_analysis_max_frames,
                int,
            )
            or
            frame_analysis_max_frames
            <
            1
        ):

            raise ValueError(
                "frame_analysis_max_frames must "
                "be a positive integer."
            )

        if isinstance(
            frame_analysis_sample_interval_seconds,
            bool,
        ):

            raise TypeError(
                "frame_analysis_sample_interval_seconds "
                "must be numeric."
            )

        try:

            normalized_interval = float(
                frame_analysis_sample_interval_seconds
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                "frame_analysis_sample_interval_seconds "
                "must be numeric."
            ) from error

        if (
            not math.isfinite(
                normalized_interval
            )
            or
            normalized_interval
            <=
            0.0
        ):

            raise ValueError(
                "frame_analysis_sample_interval_seconds "
                "must be finite and greater than zero."
            )

        if not isinstance(
            frame_analysis_analyzers,
            tuple,
        ):

            raise TypeError(
                "frame_analysis_analyzers must "
                "be tuple[str, ...]."
            )

        normalized_analyzers: list[
            str
        ] = []

        seen_analyzers: set[
            str
        ] = set()

        for analyzer_name in (
            frame_analysis_analyzers
        ):

            if not isinstance(
                analyzer_name,
                str,
            ):

                raise TypeError(
                    "frame_analysis_analyzers must "
                    "contain strings."
                )

            normalized_name = (
                analyzer_name
                .strip()
                .lower()
            )

            if not normalized_name:

                raise ValueError(
                    "Frame analyzer name "
                    "cannot be empty."
                )

            if (
                normalized_name
                in
                seen_analyzers
            ):

                continue

            seen_analyzers.add(
                normalized_name
            )

            normalized_analyzers.append(
                normalized_name
            )

        if not normalized_analyzers:

            raise ValueError(
                "At least one frame analyzer "
                "must be configured."
            )

        if (
            frame_analysis_image_options
            is not None
            and
            not isinstance(
                frame_analysis_image_options,
                dict,
            )
        ):

            raise TypeError(
                "frame_analysis_image_options "
                "must be dict or None."
            )

        # ==================================================
        # Configuration
        # ==================================================

        self.enable_transcription = (
            enable_transcription
        )

        self.transcription_language = (
            transcription_language
        )

        self.transcription_model_name = (
            transcription_model_name
        )

        self.transcription_local_files_only = (
            transcription_local_files_only
        )

        self.transcription_word_timestamps = (
            transcription_word_timestamps
        )

        self.transcription_vad_filter = (
            transcription_vad_filter
        )

        self.transcription_beam_size = (
            transcription_beam_size
        )

        self.enable_frame_analysis = (
            enable_frame_analysis
        )

        self.frame_analysis_max_frames = (
            frame_analysis_max_frames
        )

        self.frame_analysis_sample_interval_seconds = (
            normalized_interval
        )

        self.frame_analysis_analyzers = tuple(
            normalized_analyzers
        )

        self.frame_analysis_image_options = (
            dict(
                frame_analysis_image_options
            )
            if (
                frame_analysis_image_options
                is not None
            )
            else
            {}
        )

    # ======================================================
    # Processing
    # ======================================================

    def process(
        self,
        data: str | Path,
    ) -> dict[str, Any]:
        """
        Inspect and analyze one local video file.
        """

        # ==================================================
        # Existing file-processing layer
        # ==================================================

        file_metadata = (
            self.file_processor.process(
                data
            )
        )

        extension = str(
            file_metadata.get(
                "extension",
                "",
            )
        ).lower()

        if (
            extension
            not in
            self.SUPPORTED_EXTENSIONS
        ):

            raise ValueError(
                "Unsupported video extension: "
                f"{extension or 'unknown'}"
            )

        file_path = Path(
            file_metadata[
                "path"
            ]
        )

        mime_type, _ = (
            mimetypes.guess_type(
                file_path.name
            )
        )

        # ==================================================
        # Base result
        # ==================================================

        result: dict[
            str,
            Any,
        ] = {
            **file_metadata,
            "processor": (
                self.__class__.__name__
            ),
            "category": "video",
            "mime_type": (
                mime_type
                or
                "application/octet-stream"
            ),
            "supported": True,

            # --------------------------------------------------
            # Basic video metadata
            # --------------------------------------------------

            "duration_seconds": None,
            "width": None,
            "height": None,
            "frame_rate": None,
            "video_codec": None,
            "audio_codec": None,

            # --------------------------------------------------
            # Video transcription
            # --------------------------------------------------

            "transcription_enabled": (
                self.enable_transcription
            ),
            "transcription_status": "skipped",
            "transcript_text": "",
            "transcription_language": None,
            "transcription_language_probability": (
                None
            ),
            "transcription_segment_count": 0,
            "transcription_segments": [],
            "transcription": None,

            # --------------------------------------------------
            # Video frame analysis
            # --------------------------------------------------

            "frame_analysis_enabled": (
                self.enable_frame_analysis
            ),
            "frame_analysis_status": "skipped",
            "frame_analysis_frame_count": 0,
            "frame_analysis_sampling_strategy": None,
            "frame_analysis_analyzers": list(
                self.frame_analysis_analyzers
            ),
            "frame_analysis_frames": [],
            "frame_analysis": None,

            # --------------------------------------------------
            # Processing
            # --------------------------------------------------

            "processing_status": "completed",
            "warnings": [],
        }

        # ==================================================
        # Transcription
        # ==================================================

        if self.enable_transcription:

            transcription = (
                self.transcription_service
                .transcribe(
                    file_path,
                    language=(
                        self.transcription_language
                    ),
                    model_name=(
                        self.transcription_model_name
                    ),
                    local_files_only=(
                        self
                        .transcription_local_files_only
                    ),
                    beam_size=(
                        self.transcription_beam_size
                    ),
                    vad_filter=(
                        self.transcription_vad_filter
                    ),
                    word_timestamps=(
                        self
                        .transcription_word_timestamps
                    ),
                )
            )

            transcription_status = str(
                transcription.get(
                    "status",
                    "failed",
                )
            ).strip().lower()

            transcription_data = (
                transcription.get(
                    "data",
                    {},
                )
            )

            if not isinstance(
                transcription_data,
                dict,
            ):

                transcription_data = {}

            result[
                "transcription"
            ] = transcription

            result[
                "transcription_status"
            ] = transcription_status

            if (
                transcription_status
                ==
                "completed"
            ):

                result[
                    "transcript_text"
                ] = str(
                    transcription_data.get(
                        "text",
                        "",
                    )
                ).strip()

                result[
                    "transcription_language"
                ] = transcription_data.get(
                    "language"
                )

                result[
                    "transcription_language_probability"
                ] = transcription_data.get(
                    "language_probability"
                )

                result[
                    "transcription_segment_count"
                ] = transcription_data.get(
                    "segment_count",
                    0,
                )

                transcription_segments = (
                    transcription_data.get(
                        "segments",
                        [],
                    )
                )

                if isinstance(
                    transcription_segments,
                    list,
                ):

                    result[
                        "transcription_segments"
                    ] = transcription_segments

                duration = (
                    transcription_data.get(
                        "duration_seconds"
                    )
                )

                if duration is not None:

                    result[
                        "duration_seconds"
                    ] = duration

            self._append_analysis_diagnostics(
                result=result,
                prefix="Video transcription",
                analytical_result=(
                    transcription
                ),
            )

        else:

            result[
                "warnings"
            ].append(
                "Video transcription is disabled."
            )

        # ==================================================
        # Frame analysis
        # ==================================================

        if self.enable_frame_analysis:

            frame_analysis = (
                self.frame_analysis_service
                .analyze(
                    file_path,
                    max_frames=(
                        self.frame_analysis_max_frames
                    ),
                    sample_interval_seconds=(
                        self
                        .frame_analysis_sample_interval_seconds
                    ),
                    analyzers=(
                        self.frame_analysis_analyzers
                    ),
                    image_options=dict(
                        self
                        .frame_analysis_image_options
                    ),
                )
            )

            frame_analysis_status = str(
                frame_analysis.get(
                    "status",
                    "failed",
                )
            ).strip().lower()

            frame_analysis_data = (
                frame_analysis.get(
                    "data",
                    {},
                )
            )

            if not isinstance(
                frame_analysis_data,
                dict,
            ):

                frame_analysis_data = {}

            result[
                "frame_analysis"
            ] = frame_analysis

            result[
                "frame_analysis_status"
            ] = frame_analysis_status

            if (
                frame_analysis_status
                ==
                "completed"
            ):

                result[
                    "frame_analysis_frame_count"
                ] = frame_analysis_data.get(
                    "frame_count",
                    0,
                )

                result[
                    "frame_analysis_sampling_strategy"
                ] = frame_analysis_data.get(
                    "sampling_strategy"
                )

                frame_results = (
                    frame_analysis_data.get(
                        "frames",
                        [],
                    )
                )

                if isinstance(
                    frame_results,
                    list,
                ):

                    result[
                        "frame_analysis_frames"
                    ] = frame_results

                if (
                    result[
                        "duration_seconds"
                    ]
                    is None
                ):

                    duration = (
                        frame_analysis_data.get(
                            "duration_seconds"
                        )
                    )

                    if duration is not None:

                        result[
                            "duration_seconds"
                        ] = duration

            self._append_analysis_diagnostics(
                result=result,
                prefix="Video frame analysis",
                analytical_result=(
                    frame_analysis
                ),
            )

        else:

            result[
                "warnings"
            ].append(
                "Video frame analysis is disabled."
            )

        return result

    # ======================================================
    # Diagnostics
    # ======================================================

    @staticmethod
    def _append_analysis_diagnostics(
        *,
        result: dict[str, Any],
        prefix: str,
        analytical_result: dict[str, Any],
    ) -> None:
        """
        Preserve analytical warnings/errors without turning
        the whole file-processing result into a failure.
        """

        warnings = analytical_result.get(
            "warnings",
            [],
        )

        errors = analytical_result.get(
            "errors",
            [],
        )

        if isinstance(
            warnings,
            (
                list,
                tuple,
            ),
        ):

            result[
                "warnings"
            ].extend(
                str(
                    warning
                )
                for warning
                in warnings
            )

        status = str(
            analytical_result.get(
                "status",
                "",
            )
        ).strip().lower()

        if (
            status
            !=
            "completed"
            and
            isinstance(
                errors,
                (
                    list,
                    tuple,
                ),
            )
        ):

            result[
                "warnings"
            ].extend(
                (
                    f"{prefix}: "
                    +
                    str(
                        error
                    )
                )
                for error
                in errors
            )

    # ======================================================
    # Metadata
    # ======================================================

    def metadata(
        self,
    ) -> dict[str, Any]:

        return {
            "name": (
                self.__class__.__name__
            ),
            "category": "video",
            "supported_extensions": sorted(
                self.SUPPORTED_EXTENSIONS
            ),

            "transcription": {
                "enabled": (
                    self.enable_transcription
                ),
                "backend": (
                    "faster-whisper"
                ),
                "runtime": (
                    "ctranslate2"
                ),
                "decoder": "pyav",
                "model": (
                    self.transcription_model_name
                ),
                "language": (
                    self.transcription_language
                    or
                    "auto"
                ),
                "local_files_only": (
                    self
                    .transcription_local_files_only
                ),
                "word_timestamps": (
                    self
                    .transcription_word_timestamps
                ),
                "vad_filter": (
                    self.transcription_vad_filter
                ),
                "beam_size": (
                    self.transcription_beam_size
                ),
            },

            "frame_analysis": {
                "enabled": (
                    self.enable_frame_analysis
                ),
                "backend": "pyav",
                "image_pipeline": (
                    "ImageAnalysisPipeline"
                ),
                "sampling": (
                    "uniform_time_midpoints"
                ),
                "max_frames": (
                    self.frame_analysis_max_frames
                ),
                "sample_interval_seconds": (
                    self
                    .frame_analysis_sample_interval_seconds
                ),
                "analyzers": list(
                    self.frame_analysis_analyzers
                ),
                "temporary_frames_persisted": (
                    False
                ),
            },

            "database_access": False,
        }
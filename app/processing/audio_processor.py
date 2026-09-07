"""
Audio processor.

Block 8 — Multimodal Analysis / Audio Transcription.

Responsible for:

- basic audio file inspection
- local speech transcription
- transcription language detection
- segment timestamps
- word timestamps

Future audio analysis may add:

- codec extraction
- waveform generation
- speaker diarization
- acoustic fingerprinting

Architecture:

audio file
    ↓
AudioProcessor
    ├── FileProcessor
    │       ↓
    │   file metadata
    │
    └── AudioTranscriptionService
            ↓
        faster-whisper
            ↓
        CTranslate2 / CPU INT8
            ↓
        transcript + language + segments


This processor does not access the database.

Transcription failure does not invalidate the underlying
audio-file inspection result. Its own status is preserved
inside the `transcription` field.
"""

from __future__ import annotations

import mimetypes

from pathlib import (
    Path,
)

from typing import (
    Any,
)

from app.analysis.audio_transcription_service import (
    AudioTranscriptionService,
)

from app.processing.base_processor import (
    BaseProcessor,
)

from app.processing.file_processor import (
    FileProcessor,
)


class AudioProcessor(
    BaseProcessor,
):
    """
    Process audio files and prepare application-ready data.

    The public `process(data)` contract is preserved.

    Transcription is enabled by default because Block 8 now
    provides the required local runtime. It may still be
    disabled explicitly when only lightweight inspection is
    desired.
    """

    SUPPORTED_EXTENSIONS = {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".ogg",
        ".oga",
        ".flac",
        ".opus",
        ".wma",
    }

    def __init__(
        self,
        file_processor: FileProcessor | None = None,
        *,
        transcription_service: (
            AudioTranscriptionService
            |
            None
        ) = None,
        enable_transcription: bool = True,
        transcription_language: str | None = None,
        transcription_model_name: str = "small",
        transcription_local_files_only: bool = True,
        transcription_word_timestamps: bool = True,
        transcription_vad_filter: bool = True,
        transcription_beam_size: int = 5,
    ) -> None:

        self.file_processor = (
            file_processor
            or FileProcessor()
        )

        self.transcription_service = (
            transcription_service
            or AudioTranscriptionService()
        )

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

    # ======================================================
    # Processing
    # ======================================================

    def process(
        self,
        data: str | Path,
    ) -> dict[str, Any]:
        """
        Inspect and optionally transcribe one audio file.
        """

        # ==================================================
        # Existing file-processing contract
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
                "Unsupported audio extension: "
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
            "category": "audio",
            "mime_type": (
                mime_type
                or
                "application/octet-stream"
            ),
            "supported": True,
            "duration_seconds": None,
            "audio_codec": None,
            "bit_rate": None,
            "sample_rate": None,
            "channels": None,
            "transcription_enabled": (
                self.enable_transcription
            ),
            "transcription_status": (
                "skipped"
            ),
            "transcript_text": "",
            "transcription_language": None,
            "transcription_language_probability": (
                None
            ),
            "transcription_segment_count": 0,
            "transcription_segments": [],
            "transcription": None,
            "processing_status": "completed",
            "warnings": [],
        }

        # ==================================================
        # Lightweight mode
        # ==================================================

        if not self.enable_transcription:

            result[
                "warnings"
            ].append(
                (
                    "Audio transcription is "
                    "disabled."
                )
            )

            return result

        # ==================================================
        # Local transcription
        # ==================================================

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
                {}
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

        # ==================================================
        # Successful transcription
        # ==================================================

        if (
            transcription_status
            ==
            "completed"
        ):

            transcript_text = str(
                transcription_data.get(
                    "text",
                    "",
                )
            ).strip()

            result[
                "transcript_text"
            ] = transcript_text

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

            segments = (
                transcription_data.get(
                    "segments",
                    [],
                )
            )

            if isinstance(
                segments,
                list,
            ):

                result[
                    "transcription_segments"
                ] = segments

            duration = (
                transcription_data.get(
                    "duration_seconds"
                )
            )

            if duration is not None:

                result[
                    "duration_seconds"
                ] = duration

        # ==================================================
        # Preserve transcription diagnostics
        # ==================================================

        transcription_warnings = (
            transcription.get(
                "warnings",
                [],
            )
        )

        transcription_errors = (
            transcription.get(
                "errors",
                [],
            )
        )

        if isinstance(
            transcription_warnings,
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
                in transcription_warnings
            )

        if (
            transcription_status
            !=
            "completed"
        ):

            if isinstance(
                transcription_errors,
                (
                    list,
                    tuple,
                ),
            ):

                result[
                    "warnings"
                ].extend(
                    (
                        "Audio transcription: "
                        +
                        str(
                            error
                        )
                    )
                    for error
                    in transcription_errors
                )

        return result

    # ======================================================
    # Metadata
    # ======================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return processor capabilities.
        """

        return {
            "name": (
                self.__class__.__name__
            ),
            "category": "audio",
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
                    self
                    .transcription_vad_filter
                ),
                "beam_size": (
                    self.transcription_beam_size
                ),
            },
            "database_access": False,
        }
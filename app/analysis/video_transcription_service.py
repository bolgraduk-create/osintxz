"""
Local video speech transcription service.

Block 8 — Multimodal Analysis / Video Transcription.

This service deliberately reuses AudioTranscriptionService.

Architecture:

video file
    ↓
VideoTranscriptionService
    ↓
AudioTranscriptionService
    ↓
PyAV media decoding
    ↓
faster-whisper
    ↓
CTranslate2 / CPU INT8
    ↓
text + language + segments
    ↓
MultimodalSignalKind.VIDEO_TRANSCRIPTION


Important:

Video transcription
    != speaker identification

Video transcription
    != verified factual statement

Language probability
    != Evidence confidence

The service performs no database writes.
"""

from __future__ import annotations

from pathlib import (
    Path,
)

from typing import (
    Any,
)

from uuid import (
    UUID,
)

from app.analysis.audio_transcription_service import (
    AudioTranscriptionService,
    DEFAULT_WHISPER_CACHE_DIR,
    DEFAULT_WHISPER_COMPUTE_TYPE,
    DEFAULT_WHISPER_DEVICE,
    DEFAULT_WHISPER_MODEL,
)

from app.analysis.multimodal_contracts import (
    MultimodalSignalKind,
    MultimodalSignalResult,
    MultimodalSignalScope,
    MultimodalSignalStatus,
)


class VideoTranscriptionService:
    """
    Transcribe the audio track of a local video file.

    No second speech-recognition backend is introduced.
    """

    def __init__(
        self,
        audio_transcription_service: (
            AudioTranscriptionService
            |
            None
        ) = None,
    ) -> None:

        self.audio_transcription_service = (
            audio_transcription_service
            or
            AudioTranscriptionService()
        )

    # ======================================================
    # Transcription
    # ======================================================

    def transcribe(
        self,
        video_path: str | Path,
        *,
        language: str | None = None,
        model_name: str = DEFAULT_WHISPER_MODEL,
        cache_dir: str | Path = (
            DEFAULT_WHISPER_CACHE_DIR
        ),
        device: str = DEFAULT_WHISPER_DEVICE,
        compute_type: str = (
            DEFAULT_WHISPER_COMPUTE_TYPE
        ),
        local_files_only: bool = True,
        beam_size: int = 5,
        vad_filter: bool = True,
        word_timestamps: bool = True,
    ) -> dict[str, Any]:
        """
        Transcribe the audio stream contained in a video.
        """

        path = Path(
            video_path
        )

        result = (
            self.audio_transcription_service
            .transcribe(
                path,
                language=language,
                model_name=model_name,
                cache_dir=cache_dir,
                device=device,
                compute_type=compute_type,
                local_files_only=(
                    local_files_only
                ),
                beam_size=beam_size,
                vad_filter=vad_filter,
                word_timestamps=(
                    word_timestamps
                ),
            )
        )

        # Preserve the original transcription result while
        # marking the analytical source as video media.

        metadata = result.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):

            metadata = {}

        result = {
            **result,
            "metadata": {
                **metadata,
                "media_type": "video",
                "transcription_service": (
                    "VideoTranscriptionService"
                ),
                "delegated_backend": (
                    "AudioTranscriptionService"
                ),
            },
        }

        return result

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

        raw_data = result.get(
            "data",
            {},
        )

        raw_warnings = result.get(
            "warnings",
            [],
        )

        raw_errors = result.get(
            "errors",
            [],
        )

        raw_metadata = result.get(
            "metadata",
            {},
        )

        execution_time = result.get(
            "execution_time"
        )

        if (
            execution_time
            is not None
        ):

            try:

                execution_time = float(
                    execution_time
                )

            except (
                TypeError,
                ValueError,
            ):

                execution_time = None

        return MultimodalSignalResult(
            kind=(
                MultimodalSignalKind
                .VIDEO_TRANSCRIPTION
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
                "VideoTranscriptionService"
            ),
            data=(
                dict(
                    raw_data
                )
                if (
                    status
                    ==
                    MultimodalSignalStatus.COMPLETED
                )
                else
                {}
            ),
            warnings=tuple(
                str(
                    value
                )
                for value
                in raw_warnings
            ),
            errors=tuple(
                str(
                    value
                )
                for value
                in raw_errors
            ),
            execution_time=(
                execution_time
            ),
            metadata=(
                dict(
                    raw_metadata
                )
                if isinstance(
                    raw_metadata,
                    dict,
                )
                else
                {}
            ),
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
            "media_type": "video",
            "backend": "faster-whisper",
            "runtime": "ctranslate2",
            "decoder": "pyav",
            "reuses_audio_transcription": True,
            "database_access": False,
        }
"""
Local audio transcription service.

Block 8 — Multimodal Analysis / Audio Transcription.

Architecture:

Audio file
    ↓
AudioTranscriptionService
    ↓
faster-whisper
    ↓
CTranslate2 / CPU INT8
    ↓
text
language
segments
timestamps
word timestamps
    ↓
MultimodalSignalResult


Semantic boundaries:

transcribed text
    != verified factual statement

language probability
    != Evidence confidence

speech recognition
    != speaker identification

transcription
    != Entity Resolution
"""

from __future__ import annotations

from math import (
    isfinite,
)

from pathlib import (
    Path,
)

from threading import (
    RLock,
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

from app.analysis.multimodal_contracts import (
    MultimodalSignalKind,
    MultimodalSignalResult,
    MultimodalSignalScope,
    MultimodalSignalStatus,
)


# ==========================================================
# Defaults
# ==========================================================


DEFAULT_WHISPER_MODEL = "small"

DEFAULT_WHISPER_CACHE_DIR = Path(
    "storage/cache/faster_whisper"
)

DEFAULT_WHISPER_DEVICE = "cpu"

DEFAULT_WHISPER_COMPUTE_TYPE = "int8"


# ==========================================================
# Service
# ==========================================================


class AudioTranscriptionService:
    """
    Perform local speech-to-text transcription.

    Models are loaded lazily and cached process-wide.
    """

    _model_cache: dict[
        tuple[
            str,
            str,
            str,
            str,
            bool,
        ],
        Any,
    ] = {}

    _model_lock = RLock()

    _inference_lock = RLock()

    # ======================================================
    # Public transcription API
    # ======================================================

    def transcribe(
        self,
        audio_path: str | Path,
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
        Transcribe one local audio file.

        `language=None` enables automatic language detection.
        """

        started_at = perf_counter()

        # ==================================================
        # Validate path
        # ==================================================

        path = Path(
            audio_path
        )

        if not path.exists():

            return self._failed_result(
                error=(
                    "Audio file does not exist: "
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
                    "Audio path is not a file: "
                    f"{path}"
                ),
                execution_time=(
                    perf_counter()
                    -
                    started_at
                ),
            )

        # ==================================================
        # Validate options
        # ==================================================

        try:

            normalized_language = (
                self._normalize_language(
                    language
                )
            )

            normalized_model_name = (
                self._normalize_nonempty_string(
                    model_name,
                    field_name="model_name",
                )
            )

            normalized_device = (
                self._normalize_nonempty_string(
                    device,
                    field_name="device",
                )
            )

            normalized_compute_type = (
                self._normalize_nonempty_string(
                    compute_type,
                    field_name="compute_type",
                )
            )

            normalized_cache_dir = Path(
                cache_dir
            )

            if not isinstance(
                local_files_only,
                bool,
            ):

                raise TypeError(
                    "local_files_only must be bool."
                )

            if (
                isinstance(
                    beam_size,
                    bool,
                )
                or
                not isinstance(
                    beam_size,
                    int,
                )
                or
                beam_size
                <
                1
            ):

                raise ValueError(
                    "beam_size must be a positive integer."
                )

            if not isinstance(
                vad_filter,
                bool,
            ):

                raise TypeError(
                    "vad_filter must be bool."
                )

            if not isinstance(
                word_timestamps,
                bool,
            ):

                raise TypeError(
                    "word_timestamps must be bool."
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

        # ==================================================
        # Model
        # ==================================================

        try:

            model = self._get_model(
                model_name=(
                    normalized_model_name
                ),
                cache_dir=(
                    normalized_cache_dir
                ),
                device=(
                    normalized_device
                ),
                compute_type=(
                    normalized_compute_type
                ),
                local_files_only=(
                    local_files_only
                ),
            )

        except Exception as error:

            return {
                "status": "unavailable",
                "data": {},
                "warnings": [
                    (
                        "Whisper model could not "
                        "be loaded."
                    )
                ],
                "errors": [
                    (
                        f"{type(error).__name__}: "
                        f"{error}"
                    )
                ],
                "execution_time": (
                    perf_counter()
                    -
                    started_at
                ),
                "metadata": self._metadata(
                    model_name=(
                        normalized_model_name
                    ),
                    cache_dir=(
                        normalized_cache_dir
                    ),
                    device=(
                        normalized_device
                    ),
                    compute_type=(
                        normalized_compute_type
                    ),
                    local_files_only=(
                        local_files_only
                    ),
                ),
            }

        # ==================================================
        # Language validation
        # ==================================================

        if (
            normalized_language
            is not None
        ):

            supported_languages = set(
                model.supported_languages
            )

            if (
                normalized_language
                not in
                supported_languages
            ):

                return self._failed_result(
                    error=(
                        "Unsupported transcription "
                        "language: "
                        f"{normalized_language}"
                    ),
                    execution_time=(
                        perf_counter()
                        -
                        started_at
                    ),
                    metadata=self._metadata(
                        model_name=(
                            normalized_model_name
                        ),
                        cache_dir=(
                            normalized_cache_dir
                        ),
                        device=(
                            normalized_device
                        ),
                        compute_type=(
                            normalized_compute_type
                        ),
                        local_files_only=(
                            local_files_only
                        ),
                    ),
                )

        # ==================================================
        # Real inference
        # ==================================================

        try:

            with self._inference_lock:

                segments_iterator, info = (
                    model.transcribe(
                        str(
                            path
                        ),
                        language=(
                            normalized_language
                        ),
                        beam_size=(
                            beam_size
                        ),
                        vad_filter=(
                            vad_filter
                        ),
                        word_timestamps=(
                            word_timestamps
                        ),
                    )
                )

                raw_segments = tuple(
                    segments_iterator
                )

        except Exception as error:

            return self._failed_result(
                error=(
                    "Audio transcription failed: "
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
                execution_time=(
                    perf_counter()
                    -
                    started_at
                ),
                metadata=self._metadata(
                    model_name=(
                        normalized_model_name
                    ),
                    cache_dir=(
                        normalized_cache_dir
                    ),
                    device=(
                        normalized_device
                    ),
                    compute_type=(
                        normalized_compute_type
                    ),
                    local_files_only=(
                        local_files_only
                    ),
                ),
            )

        # ==================================================
        # Normalize segments
        # ==================================================

        segments: list[
            dict[
                str,
                Any,
            ]
        ] = []

        for raw_segment in raw_segments:

            segment_text = str(
                getattr(
                    raw_segment,
                    "text",
                    "",
                )
            ).strip()

            start = self._optional_float(
                getattr(
                    raw_segment,
                    "start",
                    None,
                )
            )

            end = self._optional_float(
                getattr(
                    raw_segment,
                    "end",
                    None,
                )
            )

            words: list[
                dict[
                    str,
                    Any,
                ]
            ] = []

            raw_words = getattr(
                raw_segment,
                "words",
                None,
            )

            if raw_words is not None:

                for raw_word in raw_words:

                    word_text = str(
                        getattr(
                            raw_word,
                            "word",
                            "",
                        )
                    ).strip()

                    if not word_text:

                        continue

                    words.append(
                        {
                            "text": word_text,
                            "start": (
                                self._optional_float(
                                    getattr(
                                        raw_word,
                                        "start",
                                        None,
                                    )
                                )
                            ),
                            "end": (
                                self._optional_float(
                                    getattr(
                                        raw_word,
                                        "end",
                                        None,
                                    )
                                )
                            ),
                            "probability": (
                                self._optional_float(
                                    getattr(
                                        raw_word,
                                        "probability",
                                        None,
                                    )
                                )
                            ),
                        }
                    )

            segments.append(
                {
                    "id": getattr(
                        raw_segment,
                        "id",
                        None,
                    ),
                    "start": start,
                    "end": end,
                    "text": segment_text,
                    "avg_logprob": (
                        self._optional_float(
                            getattr(
                                raw_segment,
                                "avg_logprob",
                                None,
                            )
                        )
                    ),
                    "no_speech_prob": (
                        self._optional_float(
                            getattr(
                                raw_segment,
                                "no_speech_prob",
                                None,
                            )
                        )
                    ),
                    "words": words,
                }
            )

        # ==================================================
        # Combined transcript
        # ==================================================

        text = " ".join(
            segment[
                "text"
            ]
            for segment
            in segments
            if segment[
                "text"
            ]
        ).strip()

        warnings: list[str] = []

        if not text:

            warnings.append(
                (
                    "Transcription completed, "
                    "but no speech text was detected."
                )
            )

        detected_language = (
            getattr(
                info,
                "language",
                None,
            )
        )

        language_probability = (
            self._optional_float(
                getattr(
                    info,
                    "language_probability",
                    None,
                )
            )
        )

        duration = (
            self._optional_float(
                getattr(
                    info,
                    "duration",
                    None,
                )
            )
        )

        duration_after_vad = (
            self._optional_float(
                getattr(
                    info,
                    "duration_after_vad",
                    None,
                )
            )
        )

        execution_time = (
            perf_counter()
            -
            started_at
        )

        return {
            "status": "completed",
            "data": {
                "text": text,
                "language": (
                    detected_language
                ),
                "language_probability": (
                    language_probability
                ),
                "duration_seconds": (
                    duration
                ),
                "duration_after_vad_seconds": (
                    duration_after_vad
                ),
                "segment_count": len(
                    segments
                ),
                "segments": segments,
                "word_timestamps": (
                    word_timestamps
                ),
            },
            "warnings": warnings,
            "errors": [],
            "execution_time": (
                execution_time
            ),
            "metadata": {
                **self._metadata(
                    model_name=(
                        normalized_model_name
                    ),
                    cache_dir=(
                        normalized_cache_dir
                    ),
                    device=(
                        normalized_device
                    ),
                    compute_type=(
                        normalized_compute_type
                    ),
                    local_files_only=(
                        local_files_only
                    ),
                ),
                "source_path": str(
                    path
                ),
                "requested_language": (
                    normalized_language
                    or "auto"
                ),
                "beam_size": (
                    beam_size
                ),
                "vad_filter": (
                    vad_filter
                ),
            },
        }

    # ======================================================
    # Multimodal bridge
    # ======================================================

    def to_multimodal_signal(
        self,
        *,
        evidence_id: UUID,
        result: dict[str, Any],
    ) -> MultimodalSignalResult:
        """
        Convert transcription output into the shared
        multimodal analytical contract.
        """

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

        execution_time = (
            self._optional_float(
                result.get(
                    "execution_time"
                )
            )
        )

        return MultimodalSignalResult(
            kind=(
                MultimodalSignalKind
                .AUDIO_TRANSCRIPTION
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
                "AudioTranscriptionService"
            ),
            data=(
                dict(
                    raw_data
                )
                if status
                ==
                MultimodalSignalStatus.COMPLETED
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
            metadata=dict(
                raw_metadata
            ),
        )

    # ======================================================
    # Model cache
    # ======================================================

    @classmethod
    def _get_model(
        cls,
        *,
        model_name: str,
        cache_dir: Path,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> Any:

        cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        cache_key = (
            model_name,
            str(
                cache_dir.resolve()
            ),
            device,
            compute_type,
            local_files_only,
        )

        cached = cls._model_cache.get(
            cache_key
        )

        if cached is not None:

            return cached

        with cls._model_lock:

            cached = cls._model_cache.get(
                cache_key
            )

            if cached is not None:

                return cached

            from faster_whisper import (
                WhisperModel,
            )

            model = WhisperModel(
                model_name,
                device=device,
                compute_type=(
                    compute_type
                ),
                download_root=str(
                    cache_dir
                ),
                local_files_only=(
                    local_files_only
                ),
            )

            cls._model_cache[
                cache_key
            ] = model

            return model

    # ======================================================
    # Helpers
    # ======================================================

    @staticmethod
    def _normalize_language(
        value: str | None,
    ) -> str | None:

        if value is None:

            return None

        if not isinstance(
            value,
            str,
        ):

            raise TypeError(
                "language must be str or None."
            )

        normalized = (
            value
            .strip()
            .lower()
        )

        if not normalized:

            return None

        if normalized == "auto":

            return None

        return normalized

    @staticmethod
    def _normalize_nonempty_string(
        value: Any,
        *,
        field_name: str,
    ) -> str:

        if not isinstance(
            value,
            str,
        ):

            raise TypeError(
                f"{field_name} must be str."
            )

        normalized = (
            value.strip()
        )

        if not normalized:

            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return normalized

    @staticmethod
    def _optional_float(
        value: Any,
    ) -> float | None:

        if value is None:

            return None

        try:

            result = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

        if not isfinite(
            result
        ):

            return None

        return result

    @staticmethod
    def _metadata(
        *,
        model_name: str,
        cache_dir: Path,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> dict[str, Any]:

        return {
            "backend": "faster-whisper",
            "runtime": "ctranslate2",
            "decoder": "pyav",
            "model": model_name,
            "device": device,
            "compute_type": (
                compute_type
            ),
            "cache_dir": str(
                cache_dir
            ),
            "local_files_only": (
                local_files_only
            ),
            "network_required": False,
            "database_access": False,
        }

    @staticmethod
    def _failed_result(
        *,
        error: str,
        execution_time: float,
        metadata: (
            dict[str, Any]
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
                or {}
            ),
        }
"""
Investigation-level multimodal analysis bridge.

Connects already-produced image/audio/video analytical outputs to the
shared multimodal contracts used by InvestigationAnalysisOrchestrator.

Architectural boundaries:
- read-only with respect to ORM/database state
- does not import/copy media files
- does not create Evidence/Entity/Relationship objects
- does not rerun media models merely because a case is analyzed
- ignores non-media evidence
- preserves existing MultimodalSignalResult production contracts
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.analysis.audio_transcription_service import AudioTranscriptionService
from app.analysis.images.image_analysis_result import (
    ImageAnalysisResult,
    ImageAnalysisStatus,
)
from app.analysis.multimodal_contracts import (
    MultimodalSignalKind,
    MultimodalSignalResult,
)
from app.analysis.multimodal_image_aggregation import (
    MultimodalImageAggregationService,
)
from app.analysis.video_frame_analysis_service import VideoFrameAnalysisService
from app.analysis.video_transcription_service import VideoTranscriptionService
from app.models.evidence import Evidence, EvidenceType
from app.services.evidence_service import EvidenceService


@dataclass(frozen=True, slots=True)
class InvestigationMultimodalAnalysisResult:
    """Typed case-level result for the orchestrated multimodal stage."""

    case_id: UUID
    media_evidence_count: int
    analyzed_evidence_count: int
    skipped_evidence_count: int
    signals: tuple[MultimodalSignalResult, ...]
    warnings: tuple[str, ...] = ()


class InvestigationMultimodalAnalysisService:
    """
    Read-only adapter over existing multimodal production outputs.

    Media processing/transcription/frame analysis happens in the existing
    processing layer. This service only normalizes results already stored in
    Evidence metadata, so a normal Analyze run cannot accidentally rerun
    expensive media models or mutate evidence metadata.
    """

    _IMAGE_KIND_BY_ANALYZER: dict[str, MultimodalSignalKind] = {
        "hashes": MultimodalSignalKind.IMAGE_HASH,
        "faces": MultimodalSignalKind.FACE_DETECTION,
        "face_embeddings": MultimodalSignalKind.FACE_EMBEDDING,
        "image_embeddings": MultimodalSignalKind.IMAGE_EMBEDDING,
        "ocr": MultimodalSignalKind.OCR_TEXT,
    }

    def __init__(
        self,
        *,
        evidence_service: EvidenceService,
        image_aggregation_service: MultimodalImageAggregationService,
        audio_transcription_service: AudioTranscriptionService,
        video_transcription_service: VideoTranscriptionService,
        video_frame_analysis_service: VideoFrameAnalysisService,
    ) -> None:
        self.evidence_service = evidence_service
        self.image_aggregation_service = image_aggregation_service
        self.audio_transcription_service = audio_transcription_service
        self.video_transcription_service = video_transcription_service
        self.video_frame_analysis_service = video_frame_analysis_service

    def analyze_case(
        self,
        case_id: str | UUID,
    ) -> InvestigationMultimodalAnalysisResult:
        case_uuid = self._normalize_uuid(case_id)
        evidence_items = tuple(
            self.evidence_service.get_case_evidence(case_uuid)
        )

        media_items = tuple(
            evidence
            for evidence in evidence_items
            if evidence.evidence_type
            in {
                EvidenceType.IMAGE,
                EvidenceType.AUDIO,
                EvidenceType.VIDEO,
            }
        )

        if not media_items:
            return InvestigationMultimodalAnalysisResult(
                case_id=case_uuid,
                media_evidence_count=0,
                analyzed_evidence_count=0,
                skipped_evidence_count=0,
                signals=(),
                warnings=(),
            )

        signals: list[MultimodalSignalResult] = []
        warnings: list[str] = []
        analyzed = 0
        skipped = 0

        for evidence in media_items:
            metadata = self._parse_metadata(evidence.metadata_json)
            evidence_signals = self._signals_for_evidence(
                evidence=evidence,
                metadata=metadata,
            )

            if evidence_signals:
                analyzed += 1
                signals.extend(evidence_signals)
            else:
                skipped += 1
                warnings.append(
                    "No stored multimodal analytical output is available "
                    f"for evidence {evidence.id} ({evidence.evidence_type.value})."
                )

        return InvestigationMultimodalAnalysisResult(
            case_id=case_uuid,
            media_evidence_count=len(media_items),
            analyzed_evidence_count=analyzed,
            skipped_evidence_count=skipped,
            signals=tuple(signals),
            warnings=self._deduplicate(warnings),
        )

    def _signals_for_evidence(
        self,
        *,
        evidence: Evidence,
        metadata: dict[str, Any],
    ) -> tuple[MultimodalSignalResult, ...]:
        if evidence.evidence_type is EvidenceType.IMAGE:
            return self._image_signals(evidence=evidence, metadata=metadata)
        if evidence.evidence_type is EvidenceType.AUDIO:
            return self._audio_signals(evidence=evidence, metadata=metadata)
        if evidence.evidence_type is EvidenceType.VIDEO:
            return self._video_signals(evidence=evidence, metadata=metadata)
        return ()

    def _image_signals(
        self,
        *,
        evidence: Evidence,
        metadata: dict[str, Any],
    ) -> tuple[MultimodalSignalResult, ...]:
        image_analysis = metadata.get("image_analysis")
        if not isinstance(image_analysis, dict):
            return ()

        adapted: list[MultimodalSignalResult] = []
        for analyzer_name, kind in self._IMAGE_KIND_BY_ANALYZER.items():
            raw = image_analysis.get(analyzer_name)
            if not isinstance(raw, dict):
                continue
            result = self._image_result_from_dict(
                analyzer_name=analyzer_name,
                raw=raw,
            )
            adapted.append(
                self.image_aggregation_service.adapt(
                    evidence_id=evidence.id,
                    kind=kind,
                    result=result,
                )
            )
        return tuple(adapted)

    def _audio_signals(
        self,
        *,
        evidence: Evidence,
        metadata: dict[str, Any],
    ) -> tuple[MultimodalSignalResult, ...]:
        processing = self._processing_metadata(metadata)
        transcription = processing.get("transcription")
        if not isinstance(transcription, dict):
            return ()
        return (
            self.audio_transcription_service.to_multimodal_signal(
                evidence_id=evidence.id,
                result=transcription,
            ),
        )

    def _video_signals(
        self,
        *,
        evidence: Evidence,
        metadata: dict[str, Any],
    ) -> tuple[MultimodalSignalResult, ...]:
        processing = self._processing_metadata(metadata)
        results: list[MultimodalSignalResult] = []

        transcription = processing.get("transcription")
        if isinstance(transcription, dict):
            results.append(
                self.video_transcription_service.to_multimodal_signal(
                    evidence_id=evidence.id,
                    result=transcription,
                )
            )

        frame_analysis = processing.get("frame_analysis")
        if isinstance(frame_analysis, dict):
            results.append(
                self.video_frame_analysis_service.to_multimodal_signal(
                    evidence_id=evidence.id,
                    result=frame_analysis,
                )
            )

        return tuple(results)

    @staticmethod
    def _processing_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        direct = metadata.get("processing_metadata")
        if isinstance(direct, dict):
            return direct

        processing = metadata.get("processing")
        if isinstance(processing, dict):
            nested = processing.get("metadata")
            if isinstance(nested, dict):
                return nested
        return {}

    @staticmethod
    def _image_result_from_dict(
        *,
        analyzer_name: str,
        raw: dict[str, Any],
    ) -> ImageAnalysisResult:
        status_value = str(raw.get("status", "failed")).strip().lower()
        try:
            status = ImageAnalysisStatus(status_value)
        except ValueError:
            status = ImageAnalysisStatus.FAILED

        data = raw.get("data")
        warnings = raw.get("warnings")
        errors = raw.get("errors")
        metadata = raw.get("metadata")

        return ImageAnalysisResult(
            analyzer=str(raw.get("analyzer") or analyzer_name),
            status=status,
            data=dict(data) if isinstance(data, dict) else {},
            warnings=[str(v) for v in warnings] if isinstance(warnings, list) else [],
            errors=[str(v) for v in errors] if isinstance(errors, list) else [],
            execution_time=max(0.0, float(raw.get("execution_time") or 0.0)),
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
        )

    @staticmethod
    def _parse_metadata(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _normalize_uuid(value: str | UUID) -> UUID:
        if isinstance(value, UUID):
            return value
        return UUID(str(value).strip())

    @staticmethod
    def _deduplicate(values: list[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(v.strip() for v in values if v.strip()))


__all__ = [
    "InvestigationMultimodalAnalysisResult",
    "InvestigationMultimodalAnalysisService",
]

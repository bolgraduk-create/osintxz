"""
Image analysis service.

Coordinates image analysis for stored evidence.

Responsibilities:

- load image evidence
- parse existing evidence metadata
- build ImageAnalysisContext
- execute one or more image analyzers
- merge analysis results into metadata_json
- preserve existing processing metadata
- update evidence through EvidenceService

Does NOT:

- commit or rollback transactions
- access repositories directly
- interact with desktop widgets
- modify original evidence files
- contain analyzer-specific algorithms
"""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any
from uuid import UUID

from app.analysis.images import (
    ImageAnalysisContext,
    ImageAnalysisPipeline,
)

from app.models.evidence import (
    Evidence,
    EvidenceType,
)

from app.services.evidence_service import (
    EvidenceService,
)


class ImageAnalysisService:
    """
    Application service for image-evidence analysis.
    """

    def __init__(
        self,
        evidence_service: EvidenceService,
        pipeline: ImageAnalysisPipeline | None = None,
    ) -> None:
        """
        Initialize service dependencies.
        """

        self.evidence_service = evidence_service

        self.pipeline = (
            pipeline
            or ImageAnalysisPipeline()
        )

    # ==========================================================
    # Public analysis API
    # ==========================================================

    def analyze(
        self,
        evidence_id: str | UUID,
        analyzer_name: str,
        *,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute one analyzer for image evidence and save its result.
        """

        evidence = self._require_image_evidence(
            evidence_id
        )

        metadata = self._parse_metadata(
            evidence.metadata_json
        )

        context = self._build_context(
            evidence=evidence,
            metadata=metadata,
            options=options,
        )

        result = self.pipeline.analyze(
            analyzer_name=analyzer_name,
            context=context,
        )

        updated_metadata = self._merge_analysis_result(
            metadata=metadata,
            analyzer_name=analyzer_name,
            result=result,
        )

        updated_evidence = (
            self.evidence_service.update_metadata(
                evidence_id=evidence.id,
                metadata_json=self._encode_metadata(
                    updated_metadata
                ),
            )
        )

        if updated_evidence is None:

            raise RuntimeError(
                "Evidence disappeared while saving "
                "the image-analysis result."
            )

        return {
            "evidence_id": str(
                evidence.id
            ),
            "case_id": str(
                evidence.case_id
            ),
            "analyzer": analyzer_name,
            "result": result,
            "metadata": updated_metadata,
        }

    def calculate_hashes(
        self,
        evidence_id: str | UUID,
        *,
        hash_size: int = 16,
    ) -> dict[str, Any]:
        """
        Calculate and store cryptographic and visual hashes.
        """

        return self.analyze(
            evidence_id=evidence_id,
            analyzer_name="hashes",
            options={
                "hash_size": hash_size,
            },
        )


    def detect_faces(
        self,
        evidence_id: str | UUID,
        *,
        score_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
    ) -> dict[str, Any]:
        """
        Detect face regions and facial landmarks
        using the configured face detector.
        """

        return self.analyze(
            evidence_id=evidence_id,
            analyzer_name="faces",
            options={
                "score_threshold": score_threshold,
                "nms_threshold": nms_threshold,
                "top_k": top_k,
            },
        )

    def generate_face_embeddings(
        self,
        evidence_id: str | UUID,
    ) -> dict[str, Any]:
        """
        Generate and store SFace embeddings
        for previously detected faces.
        """

        return self.analyze(
            evidence_id=evidence_id,
            analyzer_name="face_embeddings",
        )

    def analyze_many(
        self,
        evidence_id: str | UUID,
        analyzer_names: list[str],
        *,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute selected analyzers and save all results.
        """

        evidence = self._require_image_evidence(
            evidence_id
        )

        metadata = self._parse_metadata(
            evidence.metadata_json
        )

        context = self._build_context(
            evidence=evidence,
            metadata=metadata,
            options=options,
        )

        pipeline_result = (
            self.pipeline.analyze_many(
                analyzers=analyzer_names,
                context=context,
            )
        )

        results = pipeline_result.get(
            "results",
            {},
        )

        if not isinstance(
            results,
            dict,
        ):

            results = {}

        updated_metadata = dict(
            metadata
        )

        for analyzer_name, result in results.items():

            if not isinstance(
                result,
                dict,
            ):

                continue

            updated_metadata = (
                self._merge_analysis_result(
                    metadata=updated_metadata,
                    analyzer_name=str(
                        analyzer_name
                    ),
                    result=result,
                )
            )

        updated_metadata[
            "image_analysis_pipeline"
        ] = {
            "metadata": pipeline_result.get(
                "metadata",
                {},
            ),
        }

        updated_evidence = (
            self.evidence_service.update_metadata(
                evidence_id=evidence.id,
                metadata_json=self._encode_metadata(
                    updated_metadata
                ),
            )
        )

        if updated_evidence is None:

            raise RuntimeError(
                "Evidence disappeared while saving "
                "image-analysis results."
            )

        return {
            "evidence_id": str(
                evidence.id
            ),
            "case_id": str(
                evidence.case_id
            ),
            "results": results,
            "pipeline_metadata": (
                pipeline_result.get(
                    "metadata",
                    {},
                )
            ),
            "metadata": updated_metadata,
        }

    def analyze_all(
        self,
        evidence_id: str | UUID,
        *,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute all registered image analyzers.
        """

        evidence = self._require_image_evidence(
            evidence_id
        )

        metadata = self._parse_metadata(
            evidence.metadata_json
        )

        context = self._build_context(
            evidence=evidence,
            metadata=metadata,
            options=options,
        )

        pipeline_result = (
            self.pipeline.analyze_all(
                context
            )
        )

        results = pipeline_result.get(
            "results",
            {},
        )

        if not isinstance(
            results,
            dict,
        ):

            results = {}

        updated_metadata = dict(
            metadata
        )

        for analyzer_name, result in results.items():

            if not isinstance(
                result,
                dict,
            ):

                continue

            updated_metadata = (
                self._merge_analysis_result(
                    metadata=updated_metadata,
                    analyzer_name=str(
                        analyzer_name
                    ),
                    result=result,
                )
            )

        updated_metadata[
            "image_analysis_pipeline"
        ] = {
            "metadata": pipeline_result.get(
                "metadata",
                {},
            ),
        }

        updated_evidence = (
            self.evidence_service.update_metadata(
                evidence_id=evidence.id,
                metadata_json=self._encode_metadata(
                    updated_metadata
                ),
            )
        )

        if updated_evidence is None:

            raise RuntimeError(
                "Evidence disappeared while saving "
                "the complete image analysis."
            )

        return {
            "evidence_id": str(
                evidence.id
            ),
            "case_id": str(
                evidence.case_id
            ),
            "results": results,
            "pipeline_metadata": (
                pipeline_result.get(
                    "metadata",
                    {},
                )
            ),
            "metadata": updated_metadata,
        }

    # ==========================================================
    # Evidence
    # ==========================================================

    def _require_image_evidence(
        self,
        evidence_id: str | UUID,
    ) -> Evidence:
        """
        Return validated image evidence.
        """

        normalized_id = self._normalize_uuid(
            evidence_id,
            field_name="evidence_id",
        )

        evidence = (
            self.evidence_service.get_evidence(
                normalized_id
            )
        )

        if evidence is None:

            raise LookupError(
                "Image evidence was not found: "
                f"{normalized_id}"
            )

        if (
            evidence.evidence_type
            != EvidenceType.IMAGE
        ):

            raise ValueError(
                "Image analysis requires evidence "
                "with type IMAGE."
            )

        if not evidence.file_path:

            raise ValueError(
                "Image evidence does not contain "
                "a file path."
            )

        image_path = Path(
            evidence.file_path
        ).expanduser()

        if not image_path.is_file():

            raise FileNotFoundError(
                "Image evidence file does not exist: "
                f"{image_path}"
            )

        return evidence

    # ==========================================================
    # Context
    # ==========================================================

    def _build_context(
        self,
        *,
        evidence: Evidence,
        metadata: dict[str, Any],
        options: dict[str, Any] | None,
    ) -> ImageAnalysisContext:
        """
        Build an analyzer context from stored evidence.
        """

        preview_path = self._find_preview_path(
            metadata
        )

        return ImageAnalysisContext.create(
            image_path=evidence.file_path,
            preview_path=preview_path,
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            mime_type=evidence.mime_type,
            metadata=metadata,
            options=options,
        )

    @classmethod
    def _find_preview_path(
        cls,
        metadata: dict[str, Any],
    ) -> str | None:
        """
        Find a generated compatible preview in metadata.
        """

        processing_metadata = (
            cls._processing_metadata(
                metadata
            )
        )

        preview = processing_metadata.get(
            "preview"
        )

        if isinstance(
            preview,
            dict,
        ):

            path = cls._normalized_path_value(
                preview.get(
                    "preview_path"
                )
                or preview.get(
                    "path"
                )
            )

            if path:

                return path

        path = cls._normalized_path_value(
            processing_metadata.get(
                "preview_path"
            )
            or metadata.get(
                "preview_path"
            )
        )

        if path:

            return path

        return None

    @staticmethod
    def _processing_metadata(
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Return normalized processing metadata.
        """

        processing_metadata = metadata.get(
            "processing_metadata"
        )

        if isinstance(
            processing_metadata,
            dict,
        ):

            return processing_metadata

        processing = metadata.get(
            "processing"
        )

        if isinstance(
            processing,
            dict,
        ):

            nested_metadata = processing.get(
                "metadata"
            )

            if isinstance(
                nested_metadata,
                dict,
            ):

                return nested_metadata

        return {}

    # ==========================================================
    # Result merging
    # ==========================================================

    @classmethod
    def _merge_analysis_result(
        cls,
        *,
        metadata: dict[str, Any],
        analyzer_name: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Merge one analyzer result without deleting prior metadata.
        """

        updated_metadata = dict(
            metadata
        )

        image_analysis = updated_metadata.get(
            "image_analysis"
        )

        if not isinstance(
            image_analysis,
            dict,
        ):

            image_analysis = {}

        normalized_name = str(
            analyzer_name
        ).strip().lower()

        image_analysis[
            normalized_name
        ] = result

        updated_metadata[
            "image_analysis"
        ] = image_analysis

        if normalized_name == "hashes":

            cls._merge_hash_result(
                metadata=updated_metadata,
                result=result,
            )

        return updated_metadata

    @staticmethod
    def _merge_hash_result(
        *,
        metadata: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """
        Store hashes in both structured and compatibility fields.
        """

        result_data = result.get(
            "data"
        )

        if not isinstance(
            result_data,
            dict,
        ):

            result_data = {}

        metadata["hashes"] = dict(
            result_data
        )

        compatibility_mapping = {
            "md5": "md5",
            "sha1": "sha1",
            "sha256": "sha256",
            "sha512": "sha512",
            "average_hash": "average_hash",
            "difference_hash": "difference_hash",
            "perceptual_hash": "phash",
            "wavelet_hash": "wavelet_hash",
            "color_hash": "color_hash",
        }

        for source_key, destination_key in (
            compatibility_mapping.items()
        ):

            value = result_data.get(
                source_key
            )

            if value is not None:

                metadata[
                    destination_key
                ] = value

    # ==========================================================
    # Metadata serialization
    # ==========================================================

    @staticmethod
    def _parse_metadata(
        metadata_json: str | None,
    ) -> dict[str, Any]:
        """
        Decode metadata_json safely.
        """

        if not metadata_json:

            return {}

        try:

            decoded = json.loads(
                metadata_json
            )

        except (
            TypeError,
            json.JSONDecodeError,
        ) as error:

            raise ValueError(
                "Evidence metadata_json contains "
                "invalid JSON."
            ) from error

        if not isinstance(
            decoded,
            dict,
        ):

            raise ValueError(
                "Evidence metadata_json must contain "
                "a JSON object."
            )

        return decoded

    @staticmethod
    def _encode_metadata(
        metadata: dict[str, Any],
    ) -> str:
        """
        Encode metadata for Evidence.metadata_json.
        """

        return json.dumps(
            metadata,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
            default=str,
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _normalize_uuid(
        value: str | UUID,
        *,
        field_name: str,
    ) -> UUID:
        """
        Normalize a UUID identifier.
        """

        if isinstance(
            value,
            UUID,
        ):

            return value

        try:

            return UUID(
                str(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                f"{field_name} must contain "
                "a valid UUID."
            ) from error

    @staticmethod
    def _normalized_path_value(
        value: Any,
    ) -> str | None:
        """
        Return a usable existing file path.
        """

        if value is None:

            return None

        normalized = str(
            value
        ).strip()

        if not normalized:

            return None

        path = Path(
            normalized
        ).expanduser()

        if not path.is_file():

            return None

        return str(
            path.resolve()
        )

    # ==========================================================
    # Information
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return service and pipeline information.
        """

        return {
            "type": "image_analysis_service",
            "pipeline": (
                self.pipeline.metadata()
            ),
        }
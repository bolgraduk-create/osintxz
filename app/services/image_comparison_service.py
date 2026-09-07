"""
Image comparison service.

Coordinates comparison of two image evidence items.

Architecture:

Evidence A + Evidence B
        ↓
ImageComparisonService
        ↓
Existing hashes?
    ┌───────┴────────┐
    │                │
   yes               no
    │                │
    │        ImageAnalysisService
    │                │
    └───────┬────────┘
            ↓
ImageSimilarityAnalyzer
            ↓
Unified comparison result

Responsibilities:

- load two evidence records
- validate image evidence
- reuse existing image hashes
- calculate missing hashes automatically
- compare image fingerprints
- return a unified comparison result

Does NOT:

- commit or rollback transactions
- interact with desktop widgets
- modify original evidence files
- implement hashing algorithms
- implement similarity-search across a case
"""

from __future__ import annotations

import json

from typing import Any
from uuid import UUID

from app.analysis.images import (
    ImageSimilarityAnalyzer,
)

from app.models.evidence import (
    Evidence,
    EvidenceType,
)

from app.services.evidence_service import (
    EvidenceService,
)

from app.services.image_analysis_service import (
    ImageAnalysisService,
)


class ImageComparisonService:
    """
    Application service for comparing two image
    evidence records.
    """

    def __init__(
        self,
        evidence_service: EvidenceService,
        image_analysis_service: ImageAnalysisService,
        similarity_analyzer: (
            ImageSimilarityAnalyzer
            | None
        ) = None,
    ) -> None:

        self.evidence_service = (
            evidence_service
        )

        self.image_analysis_service = (
            image_analysis_service
        )

        self.similarity_analyzer = (
            similarity_analyzer
            or ImageSimilarityAnalyzer()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def compare(
        self,
        evidence_id_a: str | UUID,
        evidence_id_b: str | UUID,
        *,
        calculate_missing: bool = True,
    ) -> dict[str, Any]:
        """
        Compare two image evidence records.
        """

        normalized_id_a = self._normalize_uuid(
            evidence_id_a,
            field_name="evidence_id_a",
        )

        normalized_id_b = self._normalize_uuid(
            evidence_id_b,
            field_name="evidence_id_b",
        )

        if normalized_id_a == normalized_id_b:

            raise ValueError(
                "Two different evidence records "
                "must be selected for comparison."
            )

        evidence_a = self._require_image_evidence(
            normalized_id_a
        )

        evidence_b = self._require_image_evidence(
            normalized_id_b
        )

        if (
            evidence_a.case_id
            != evidence_b.case_id
        ):

            raise ValueError(
                "Image comparison currently requires "
                "both evidence records to belong to "
                "the same investigation."
            )

        hashes_a, calculated_a = (
            self._get_hashes(
                evidence=evidence_a,
                calculate_missing=(
                    calculate_missing
                ),
            )
        )

        hashes_b, calculated_b = (
            self._get_hashes(
                evidence=evidence_b,
                calculate_missing=(
                    calculate_missing
                ),
            )
        )

        comparison = (
            self.similarity_analyzer.compare(
                hashes_a,
                hashes_b,
            )
        )

        return {
            "case_id": str(
                evidence_a.case_id
            ),
            "evidence_a": (
                self._evidence_summary(
                    evidence_a
                )
            ),
            "evidence_b": (
                self._evidence_summary(
                    evidence_b
                )
            ),
            "hashes_calculated": {
                "evidence_a": (
                    calculated_a
                ),
                "evidence_b": (
                    calculated_b
                ),
            },
            "comparison": comparison,
        }

    # ==========================================================
    # Hash retrieval
    # ==========================================================

    def _get_hashes(
        self,
        *,
        evidence: Evidence,
        calculate_missing: bool,
    ) -> tuple[
        dict[str, Any],
        bool,
    ]:
        """
        Return hashes for one evidence record.

        Existing stored hashes are reused whenever
        possible.
        """

        metadata = self._parse_metadata(
            evidence.metadata_json
        )

        hashes = self._extract_hashes(
            metadata
        )

        if self._has_usable_hashes(
            hashes
        ):

            return (
                hashes,
                False,
            )

        if not calculate_missing:

            raise ValueError(
                "Image hashes have not been "
                "calculated for evidence: "
                f"{evidence.id}"
            )

        analysis = (
            self.image_analysis_service
            .calculate_hashes(
                evidence_id=evidence.id,
            )
        )

        hashes = self._extract_hashes_from_analysis(
            analysis
        )

        if not self._has_usable_hashes(
            hashes
        ):

            raise RuntimeError(
                "Hash analysis completed but did "
                "not return usable image hashes for "
                f"evidence {evidence.id}."
            )

        return (
            hashes,
            True,
        )

    # ==========================================================
    # Hash extraction
    # ==========================================================

    @classmethod
    def _extract_hashes(
        cls,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Extract stored hashes from metadata.

        Supports both the current structured format
        and compatibility fields.
        """

        hashes: dict[
            str,
            Any,
        ] = {}

        stored_hashes = metadata.get(
            "hashes"
        )

        if isinstance(
            stored_hashes,
            dict,
        ):

            hashes.update(
                stored_hashes
            )

        image_analysis = metadata.get(
            "image_analysis"
        )

        if isinstance(
            image_analysis,
            dict,
        ):

            hash_analysis = (
                image_analysis.get(
                    "hashes"
                )
            )

            if isinstance(
                hash_analysis,
                dict,
            ):

                data = hash_analysis.get(
                    "data"
                )

                if isinstance(
                    data,
                    dict,
                ):

                    hashes.update(
                        data
                    )

        compatibility_keys = (
            "md5",
            "sha1",
            "sha256",
            "sha512",
            "average_hash",
            "difference_hash",
            "perceptual_hash",
            "phash",
            "wavelet_hash",
            "color_hash",
        )

        for key in compatibility_keys:

            value = metadata.get(
                key
            )

            if (
                value is not None
                and key not in hashes
            ):

                hashes[
                    key
                ] = value

        return hashes

    @classmethod
    def _extract_hashes_from_analysis(
        cls,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Extract hashes from ImageAnalysisService result.
        """

        result = analysis.get(
            "result"
        )

        if isinstance(
            result,
            dict,
        ):

            data = result.get(
                "data"
            )

            if isinstance(
                data,
                dict,
            ):

                return dict(
                    data
                )

        metadata = analysis.get(
            "metadata"
        )

        if isinstance(
            metadata,
            dict,
        ):

            return cls._extract_hashes(
                metadata
            )

        return {}

    @staticmethod
    def _has_usable_hashes(
        hashes: dict[str, Any],
    ) -> bool:
        """
        Determine whether enough hashes exist
        to perform a useful comparison.
        """

        perceptual_keys = (
            "perceptual_hash",
            "phash",
            "difference_hash",
            "average_hash",
            "wavelet_hash",
        )

        return any(
            bool(
                hashes.get(
                    key
                )
            )
            for key
            in perceptual_keys
        )

    # ==========================================================
    # Evidence
    # ==========================================================

    def _require_image_evidence(
        self,
        evidence_id: UUID,
    ) -> Evidence:
        """
        Load and validate image evidence.
        """

        evidence = (
            self.evidence_service
            .get_evidence(
                evidence_id
            )
        )

        if evidence is None:

            raise LookupError(
                "Evidence was not found: "
                f"{evidence_id}"
            )

        if (
            evidence.evidence_type
            != EvidenceType.IMAGE
        ):

            raise ValueError(
                "Image comparison requires "
                "IMAGE evidence."
            )

        return evidence

    # ==========================================================
    # Evidence summary
    # ==========================================================

    @staticmethod
    def _evidence_summary(
        evidence: Evidence,
    ) -> dict[str, Any]:
        """
        Build a compact evidence description.
        """

        return {
            "id": str(
                evidence.id
            ),
            "case_id": str(
                evidence.case_id
            ),
            "title": (
                evidence.title
            ),
            "value": (
                evidence.value
            ),
            "file_path": (
                evidence.file_path
            ),
            "mime_type": (
                evidence.mime_type
            ),
            "sha256": (
                evidence.sha256
            ),
        }

    # ==========================================================
    # Metadata
    # ==========================================================

    @staticmethod
    def _parse_metadata(
        metadata_json: str | None,
    ) -> dict[str, Any]:
        """
        Decode evidence metadata safely.
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
                "Evidence metadata_json must "
                "contain a JSON object."
            )

        return decoded

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
        Normalize UUID input.
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

    # ==========================================================
    # Information
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return service information.
        """

        return {
            "type": (
                "image_comparison_service"
            ),
            "similarity_analyzer": (
                self.similarity_analyzer
                .metadata()
            ),
        }
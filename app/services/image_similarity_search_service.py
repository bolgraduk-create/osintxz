"""
Image similarity search service.

Searches for images similar to one selected image
inside the same investigation.

Architecture:

Selected image evidence
        ↓
ImageSimilaritySearchService
        ↓
EvidenceService
        ↓
All IMAGE evidence in current case
        ↓
ImageComparisonService
        ↓
Sorted similarity matches

Responsibilities:

- validate selected image evidence
- load image evidence from the same investigation
- exclude the selected image
- compare candidate images
- rank candidates by visual similarity
- return unified search results

Does NOT:

- commit or rollback transactions
- interact with desktop widgets
- implement image hashing algorithms
- implement similarity algorithms
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.evidence import (
    Evidence,
    EvidenceType,
)

from app.services.evidence_service import (
    EvidenceService,
)

from app.services.image_comparison_service import (
    ImageComparisonService,
)


class ImageSimilaritySearchService:
    """
    Search for visually similar images inside
    one investigation.
    """

    def __init__(
        self,
        evidence_service: EvidenceService,
        image_comparison_service: ImageComparisonService,
    ) -> None:

        self.evidence_service = (
            evidence_service
        )

        self.image_comparison_service = (
            image_comparison_service
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def search(
        self,
        evidence_id: str | UUID,
        *,
        minimum_similarity: float = 0.0,
        limit: int | None = None,
        calculate_missing: bool = True,
    ) -> dict[str, Any]:
        """
        Find images similar to the selected image
        inside the same investigation.
        """

        normalized_id = self._normalize_uuid(
            evidence_id,
            field_name="evidence_id",
        )

        source_evidence = (
            self._require_image_evidence(
                normalized_id
            )
        )

        normalized_minimum = (
            self._normalize_similarity(
                minimum_similarity
            )
        )

        normalized_limit = (
            self._normalize_limit(
                limit
            )
        )

        case_evidence = (
            self.evidence_service
            .get_case_evidence(
                source_evidence.case_id
            )
        )

        candidates = [
            evidence
            for evidence
            in case_evidence
            if (
                evidence.id
                != source_evidence.id
                and evidence.evidence_type
                == EvidenceType.IMAGE
                and getattr(
                    evidence,
                    "deleted_at",
                    None,
                )
                is None
            )
        ]

        matches: list[
            dict[str, Any]
        ] = []

        skipped: list[
            dict[str, Any]
        ] = []

        for candidate in candidates:

            try:

                comparison_result = (
                    self.image_comparison_service
                    .compare(
                        source_evidence.id,
                        candidate.id,
                        calculate_missing=(
                            calculate_missing
                        ),
                    )
                )

                comparison = (
                    comparison_result.get(
                        "comparison",
                        {},
                    )
                )

                if not isinstance(
                    comparison,
                    dict,
                ):

                    comparison = {}

                visual_similarity = (
                    self._normalize_result_similarity(
                        comparison.get(
                            "visual_similarity"
                        )
                    )
                )

                if (
                    visual_similarity
                    < normalized_minimum
                ):

                    continue

                candidate_summary = (
                    comparison_result.get(
                        "evidence_b",
                        {},
                    )
                )

                if not isinstance(
                    candidate_summary,
                    dict,
                ):

                    candidate_summary = (
                        self._evidence_summary(
                            candidate
                        )
                    )

                matches.append(
                    {
                        "evidence": (
                            candidate_summary
                        ),
                        "visual_similarity": (
                            visual_similarity
                        ),
                        "classification": str(
                            comparison.get(
                                "classification",
                                "unknown",
                            )
                            or "unknown"
                        ),
                        "exact_match": bool(
                            comparison.get(
                                "exact_match",
                                False,
                            )
                        ),
                        "comparison": (
                            comparison
                        ),
                        "hashes_calculated": (
                            comparison_result.get(
                                "hashes_calculated",
                                {},
                            )
                        ),
                    }
                )

            except Exception as exc:

                skipped.append(
                    {
                        "evidence": (
                            self._evidence_summary(
                                candidate
                            )
                        ),
                        "error": str(
                            exc
                        ),
                    }
                )

        matches.sort(
            key=lambda item: (
                float(
                    item.get(
                        "visual_similarity",
                        0.0,
                    )
                    or 0.0
                ),
                bool(
                    item.get(
                        "exact_match",
                        False,
                    )
                ),
            ),
            reverse=True,
        )

        total_matches = len(
            matches
        )

        if normalized_limit is not None:

            matches = matches[
                :normalized_limit
            ]

        return {
            "case_id": str(
                source_evidence.case_id
            ),
            "source_evidence": (
                self._evidence_summary(
                    source_evidence
                )
            ),
            "candidate_count": len(
                candidates
            ),
            "match_count": (
                total_matches
            ),
            "returned_count": len(
                matches
            ),
            "minimum_similarity": (
                normalized_minimum
            ),
            "matches": (
                matches
            ),
            "skipped": (
                skipped
            ),
        }

    # ==========================================================
    # Evidence
    # ==========================================================

    def _require_image_evidence(
        self,
        evidence_id: UUID,
    ) -> Evidence:
        """
        Load and validate source image evidence.
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
                "Image similarity search requires "
                "IMAGE evidence."
            )

        if (
            getattr(
                evidence,
                "deleted_at",
                None,
            )
            is not None
        ):

            raise ValueError(
                "Deleted image evidence cannot "
                "be used for similarity search."
            )

        return evidence

    # ==========================================================
    # Result helpers
    # ==========================================================

    @staticmethod
    def _evidence_summary(
        evidence: Evidence,
    ) -> dict[str, Any]:
        """
        Build compact evidence description.
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

    @staticmethod
    def _normalize_result_similarity(
        value: Any,
    ) -> float:
        """
        Convert analyzer similarity to percentage.

        ImageSimilarityAnalyzer uses a 0-100 scale.
        """

        try:

            similarity = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

        return max(
            0.0,
            min(
                similarity,
                100.0,
            ),
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _normalize_similarity(
        value: float,
    ) -> float:
        """
        Validate minimum similarity percentage.
        """

        try:

            normalized = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                "minimum_similarity must "
                "be numeric."
            ) from error

        if not (
            0.0
            <= normalized
            <= 100.0
        ):

            raise ValueError(
                "minimum_similarity must be "
                "between 0.0 and 100.0."
            )

        return normalized

    @staticmethod
    def _normalize_limit(
        value: int | None,
    ) -> int | None:
        """
        Validate optional result limit.
        """

        if value is None:

            return None

        if isinstance(
            value,
            bool,
        ):

            raise ValueError(
                "limit must be an integer."
            )

        try:

            normalized = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                "limit must be an integer."
            ) from error

        if normalized <= 0:

            raise ValueError(
                "limit must be greater "
                "than zero."
            )

        return normalized

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
                "image_similarity_search_service"
            ),
            "scope": (
                "investigation"
            ),
            "similarity_scale": (
                "0-100"
            ),
        }
"""
Read-only case-level Evidence analysis boundary.

This service connects the investigation Analyze pipeline to the
existing Evidence analytical layer without creating a second scoring
implementation.

The current ORM Evidence model reliably exposes the Evidence inventory
and its Source relationship. Therefore this boundary can safely run the
existing SourceReliabilityScoringService for those real Source objects.

Generic proposition rows are not persisted directly by the Evidence ORM.
M024 therefore reconstructs only the subset that is explicitly preserved
by extraction provenance + EvidenceEntity links. Arbitrary title/value
text is still never promoted into confidence inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.evidence.source_reliability import (
    SourceReliabilityBreakdown,
    SourceReliabilityScoringService,
)
from app.application.investigation_evidence_confidence_service import (
    InvestigationEvidenceConfidenceService,
)
from app.services.evidence_service import (
    EvidenceService,
)


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationEvidenceItemAnalysisResult:
    """
    Read-only analytical result for one stored Evidence object.

    source_reliability is calculated by the approved Evidence Layer
    SourceReliabilityScoringService. It may be None only when the
    Evidence object does not expose a usable Source relationship.
    """

    evidence: object

    source_reliability: (
        SourceReliabilityBreakdown
        | None
    )

    warnings: tuple[
        str,
        ...,
    ] = ()

    def has_source_reliability(
        self,
    ) -> bool:
        return (
            self.source_reliability
            is not None
        )


@dataclass(
    frozen=True,
    slots=True,
)
class InvestigationEvidenceAnalysisResult:
    """
    Immutable read-only Evidence analysis for one case.

    Important:

    - evidence contains the original ORM Evidence objects;
    - item_results contains analytical results produced by existing
      Evidence Layer services;
    - proposition_confidence_results contains only propositions reconstructed
      from real persisted provenance observations;
    - no Evidence mutation or database write is performed here.
    """

    case_id: UUID

    evidence: tuple[
        object,
        ...,
    ]

    item_results: tuple[
        InvestigationEvidenceItemAnalysisResult,
        ...,
    ]

    proposition_confidence_results: tuple[
        object,
        ...,
    ] = ()

    warnings: tuple[
        str,
        ...,
    ] = ()

    def evidence_count(
        self,
    ) -> int:
        return len(
            self.evidence
        )

    def analyzed_evidence_count(
        self,
    ) -> int:
        return sum(
            1
            for item
            in self.item_results
            if item.has_source_reliability()
        )

    def has_evidence(
        self,
    ) -> bool:
        return bool(
            self.evidence
        )

    def has_proposition_confidence(
        self,
    ) -> bool:
        return bool(
            self.proposition_confidence_results
        )


class InvestigationEvidenceAnalysisService:
    """
    Run the available read-only Evidence analysis for one case.

    This application boundary delegates scoring to the existing
    Evidence Layer. It does not contain its own confidence formula.
    """

    def __init__(
        self,
        *,
        evidence_service: EvidenceService,
        source_reliability_scoring_service: (
            SourceReliabilityScoringService
        ),
        evidence_confidence_service: (
            InvestigationEvidenceConfidenceService
            | None
        ) = None,
    ) -> None:

        self.evidence_service = (
            evidence_service
        )

        self.source_reliability_scoring_service = (
            source_reliability_scoring_service
        )

        self.evidence_confidence_service = (
            evidence_confidence_service
        )

    def analyze_case(
        self,
        case_id: str | UUID,
    ) -> InvestigationEvidenceAnalysisResult:
        """
        Analyze the real Evidence inventory available for one case.

        The same Source reliability result is reused when several
        Evidence objects belong to the same Source, so one Analyze run
        does not repeat identical Source reliability calculations.
        """

        case_uuid = (
            self._normalize_case_id(
                case_id
            )
        )

        evidence = tuple(
            self.evidence_service
            .get_case_evidence(
                case_uuid
            )
        )

        source_reliability_cache: dict[
            str,
            SourceReliabilityBreakdown,
        ] = {}

        item_results: list[
            InvestigationEvidenceItemAnalysisResult
        ] = []

        warnings: list[
            str
        ] = []

        for evidence_item in evidence:

            source = getattr(
                evidence_item,
                "source",
                None,
            )

            if source is None:

                warning = (
                    "Evidence object does not expose a Source; "
                    "source reliability was not calculated."
                )

                item_results.append(
                    InvestigationEvidenceItemAnalysisResult(
                        evidence=evidence_item,
                        source_reliability=None,
                        warnings=(warning,),
                    )
                )

                warnings.append(
                    warning
                )

                continue

            source_key = (
                self._source_cache_key(
                    source
                )
            )

            source_reliability = (
                source_reliability_cache.get(
                    source_key
                )
            )

            if source_reliability is None:

                source_reliability = (
                    self
                    .source_reliability_scoring_service
                    .score(
                        source
                    )
                )

                source_reliability_cache[
                    source_key
                ] = source_reliability

            item_results.append(
                InvestigationEvidenceItemAnalysisResult(
                    evidence=evidence_item,
                    source_reliability=(
                        source_reliability
                    ),
                )
            )

        proposition_confidence_results: tuple[
            object,
            ...,
        ] = ()

        if self.evidence_confidence_service is not None:

            confidence_analysis = (
                self.evidence_confidence_service
                .analyze(
                    case_id=case_uuid,
                    evidence=evidence,
                    source_reliability_by_source_key=(
                        source_reliability_cache
                    ),
                )
            )

            proposition_confidence_results = (
                confidence_analysis.propositions
            )

            warnings.extend(
                confidence_analysis.warnings
            )

        elif evidence:

            warnings.append(
                "Proposition-level Evidence Confidence adapter is "
                "not configured for this caller."
            )

        return (
            InvestigationEvidenceAnalysisResult(
                case_id=case_uuid,
                evidence=evidence,
                item_results=tuple(
                    item_results
                ),
                proposition_confidence_results=(
                    proposition_confidence_results
                ),
                warnings=tuple(
                    self._deduplicate_warnings(
                        warnings
                    )
                ),
            )
        )

    @staticmethod
    def _source_cache_key(
        source: object,
    ) -> str:

        source_id = getattr(
            source,
            "id",
            None,
        )

        if source_id is not None:
            return str(
                source_id
            )

        return (
            f"object:{id(source)}"
        )

    @staticmethod
    def _deduplicate_warnings(
        warnings: list[str],
    ) -> list[str]:

        seen: set[str] = set()
        result: list[str] = []

        for warning in warnings:

            if warning in seen:
                continue

            seen.add(
                warning
            )

            result.append(
                warning
            )

        return result

    @staticmethod
    def _normalize_case_id(
        case_id: str | UUID,
    ) -> UUID:

        if isinstance(
            case_id,
            UUID,
        ):
            return case_id

        normalized = str(
            case_id
            or ""
        ).strip()

        if not normalized:
            raise ValueError(
                "case_id cannot be empty."
            )

        try:
            return UUID(
                normalized
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:

            raise ValueError(
                "case_id must contain a valid UUID."
            ) from exc


__all__ = [
    "InvestigationEvidenceItemAnalysisResult",
    "InvestigationEvidenceAnalysisResult",
    "InvestigationEvidenceAnalysisService",
]

"""
Evidence source independence analysis.

Evaluates whether distinct Evidence objects originate
from genuinely independent sources.

Responsibilities:

- compare Evidence provenance pairwise
- detect same-source dependency
- detect shared-origin dependency
- detect shared-lineage dependency
- detect identical-content dependency
- distinguish verified independence from unknown origin
- calculate independence coverage
- return conservative independence score
- remain deterministic and database-independent

Does NOT:

- assume different source IDs are independent
- calculate source reliability
- calculate corroboration
- calculate contradiction strength
- calculate final evidence confidence
- access the database
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from enum import Enum

import json

from typing import (
    Any,
    Iterable,
)

from uuid import UUID


# ==========================================================
# Relation
# ==========================================================


class EvidenceSourceRelation(
    str,
    Enum,
):
    """
    Relationship between the origins of two
    Evidence objects.

    INDEPENDENT:
        Available provenance explicitly supports
        distinct origins.

    DEPENDENT:
        Available provenance indicates shared origin,
        same source, shared lineage or duplicate content.

    UNKNOWN:
        Available information is insufficient to
        establish either independence or dependency.
    """

    INDEPENDENT = "independent"

    DEPENDENT = "dependent"

    UNKNOWN = "unknown"


# ==========================================================
# Observation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceSourceIndependenceObservation:
    """
    Provenance descriptor for one Evidence object.

    origin_key:
        Explicit stable identifier of the primary
        information origin.

        Examples:

            "telegram_export:abc123"
            "document:sha256:..."
            "website:capture:..."
            "osint_result:connector:item:..."

        Different source_id values alone are NOT enough.

    lineage_keys:
        Identifiers of known parent / ancestor sources.

        Shared lineage implies dependency.

    content_fingerprint:
        Stable fingerprint of the underlying content.

        Equal content fingerprints imply duplicate or
        derivative Evidence and therefore dependency
        for corroboration purposes.

    source_type:
        Context only. It does NOT determine independence.
    """

    evidence_id: UUID

    source_id: UUID

    source_type: str | None = None

    origin_key: str | None = None

    lineage_keys: tuple[
        str,
        ...,
    ] = ()

    content_fingerprint: str | None = None

    details: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.evidence_id,
            UUID,
        ):

            raise TypeError(
                "evidence_id must be UUID."
            )

        if not isinstance(
            self.source_id,
            UUID,
        ):

            raise TypeError(
                "source_id must be UUID."
            )

        if (
            self.source_type is not None
            and not str(
                self.source_type
            ).strip()
        ):

            raise ValueError(
                "source_type cannot be empty."
            )

        if (
            self.origin_key is not None
            and not str(
                self.origin_key
            ).strip()
        ):

            raise ValueError(
                "origin_key cannot be empty."
            )

        if (
            self.content_fingerprint
            is not None
            and not str(
                self.content_fingerprint
            ).strip()
        ):

            raise ValueError(
                "content_fingerprint "
                "cannot be empty."
            )

        if not isinstance(
            self.lineage_keys,
            tuple,
        ):

            raise TypeError(
                "lineage_keys must be a tuple."
            )

        for key in self.lineage_keys:

            if not isinstance(
                key,
                str,
            ):

                raise TypeError(
                    "lineage_keys must contain "
                    "strings."
                )

            if not key.strip():

                raise ValueError(
                    "lineage_keys cannot "
                    "contain empty values."
                )

        if not isinstance(
            self.details,
            dict,
        ):

            raise TypeError(
                "details must be a dictionary."
            )


# ==========================================================
# Pair result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceSourceIndependencePair:
    """
    Pairwise source-independence result.

    score:

        1.0 -> verified independent
        0.0 -> verified dependent
        None -> unknown

    Unknown is deliberately NOT represented as 0.5.
    """

    first_evidence_id: UUID

    second_evidence_id: UUID

    first_source_id: UUID

    second_source_id: UUID

    relation: EvidenceSourceRelation

    score: float | None

    reason_code: str

    reason: str

    shared_lineage_keys: tuple[
        str,
        ...,
    ] = ()

    details: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    @property
    def is_evaluated(
        self,
    ) -> bool:

        return (
            self.score
            is not None
        )

    @property
    def is_independent(
        self,
    ) -> bool:

        return (
            self.relation
            ==
            EvidenceSourceRelation
            .INDEPENDENT
        )

    @property
    def is_dependent(
        self,
    ) -> bool:

        return (
            self.relation
            ==
            EvidenceSourceRelation
            .DEPENDENT
        )

    @property
    def is_unknown(
        self,
    ) -> bool:

        return (
            self.relation
            ==
            EvidenceSourceRelation
            .UNKNOWN
        )


# ==========================================================
# Breakdown
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceSourceIndependenceBreakdown:
    """
    Explainable independence analysis.

    independence_score:
        Mean score of EVALUATED pair relations only.

        Independent = 1
        Dependent   = 0

        UNKNOWN pairs do not directly lower this score.

    coverage_score:
        Fraction of all Evidence pairs whose relation
        could actually be evaluated.

    conservative_independence_score:

        independence_score
        *
        coverage_score

    This value is intentionally conservative and will
    be the safest independence component for later
    Evidence Confidence aggregation.
    """

    independence_score: float

    coverage_score: float

    conservative_independence_score: float

    pairs: tuple[
        EvidenceSourceIndependencePair,
        ...,
    ] = ()

    input_observation_count: int = 0

    evidence_count: int = 0

    duplicate_observation_count: int = 0

    total_pair_count: int = 0

    evaluated_pair_count: int = 0

    independent_pair_count: int = 0

    dependent_pair_count: int = 0

    unknown_pair_count: int = 0

    same_source_pair_count: int = 0

    shared_origin_pair_count: int = 0

    shared_lineage_pair_count: int = 0

    shared_fingerprint_pair_count: int = 0

    @property
    def has_evaluated_relations(
        self,
    ) -> bool:

        return (
            self.evaluated_pair_count
            >
            0
        )

    @property
    def fully_observed(
        self,
    ) -> bool:

        return (
            self.total_pair_count
            >
            0
            and
            self.evaluated_pair_count
            ==
            self.total_pair_count
        )

    @property
    def has_verified_independence(
        self,
    ) -> bool:

        return (
            self.independent_pair_count
            >
            0
        )

    @property
    def has_verified_dependency(
        self,
    ) -> bool:

        return (
            self.dependent_pair_count
            >
            0
        )


# ==========================================================
# Service
# ==========================================================


class EvidenceSourceIndependenceService:
    """
    Evaluate source independence conservatively.

    Priority of pairwise rules:

        1. same source_id
        2. same content fingerprint
        3. shared lineage
        4. same explicit origin
        5. different explicit origins
        6. unknown

    Strong dependency evidence therefore overrides
    weaker assumptions about source separation.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def analyze(
        self,
        observations: Iterable[
            EvidenceSourceIndependenceObservation
        ],
    ) -> EvidenceSourceIndependenceBreakdown:
        """
        Analyze source independence between Evidence
        objects.
        """

        observation_list = list(
            observations
        )

        for observation in observation_list:

            if not isinstance(
                observation,
                EvidenceSourceIndependenceObservation,
            ):

                raise TypeError(
                    "observations must contain only "
                    "EvidenceSourceIndependenceObservation "
                    "objects."
                )

        (
            prepared,
            duplicate_observation_count,
        ) = self._prepare_observations(
            observation_list
        )

        evidence_count = len(
            prepared
        )

        pairs: list[
            EvidenceSourceIndependencePair
        ] = []

        # ======================================================
        # Pairwise comparison
        # ======================================================

        for first_index in range(
            evidence_count
        ):

            for second_index in range(
                first_index + 1,
                evidence_count,
            ):

                pairs.append(
                    self._compare(
                        prepared[
                            first_index
                        ],
                        prepared[
                            second_index
                        ],
                    )
                )

        pairs.sort(
            key=lambda pair: (
                str(
                    pair.first_evidence_id
                ),
                str(
                    pair.second_evidence_id
                ),
            )
        )

        total_pair_count = len(
            pairs
        )

        evaluated_pairs = [
            pair
            for pair
            in pairs
            if pair.is_evaluated
        ]

        independent_pairs = [
            pair
            for pair
            in pairs
            if pair.is_independent
        ]

        dependent_pairs = [
            pair
            for pair
            in pairs
            if pair.is_dependent
        ]

        unknown_pairs = [
            pair
            for pair
            in pairs
            if pair.is_unknown
        ]

        # ======================================================
        # Independence among evaluated pairs
        # ======================================================

        if not evaluated_pairs:

            independence_score = 0.0

        else:

            independence_score = (
                sum(
                    float(
                        pair.score
                    )
                    for pair
                    in evaluated_pairs
                    if pair.score
                    is not None
                )
                /
                len(
                    evaluated_pairs
                )
            )

        # ======================================================
        # Coverage
        # ======================================================

        if total_pair_count <= 0:

            coverage_score = 0.0

        else:

            coverage_score = (
                len(
                    evaluated_pairs
                )
                /
                total_pair_count
            )

        conservative_score = (
            independence_score
            *
            coverage_score
        )

        return (
            EvidenceSourceIndependenceBreakdown(
                independence_score=(
                    self._clamp(
                        independence_score
                    )
                ),
                coverage_score=(
                    self._clamp(
                        coverage_score
                    )
                ),
                conservative_independence_score=(
                    self._clamp(
                        conservative_score
                    )
                ),
                pairs=tuple(
                    pairs
                ),
                input_observation_count=(
                    len(
                        observation_list
                    )
                ),
                evidence_count=(
                    evidence_count
                ),
                duplicate_observation_count=(
                    duplicate_observation_count
                ),
                total_pair_count=(
                    total_pair_count
                ),
                evaluated_pair_count=(
                    len(
                        evaluated_pairs
                    )
                ),
                independent_pair_count=(
                    len(
                        independent_pairs
                    )
                ),
                dependent_pair_count=(
                    len(
                        dependent_pairs
                    )
                ),
                unknown_pair_count=(
                    len(
                        unknown_pairs
                    )
                ),
                same_source_pair_count=(
                    self._reason_count(
                        pairs,
                        "same_source",
                    )
                ),
                shared_origin_pair_count=(
                    self._reason_count(
                        pairs,
                        "shared_origin",
                    )
                ),
                shared_lineage_pair_count=(
                    self._reason_count(
                        pairs,
                        "shared_lineage",
                    )
                ),
                shared_fingerprint_pair_count=(
                    self._reason_count(
                        pairs,
                        "shared_content_fingerprint",
                    )
                ),
            )
        )

    # ==========================================================
    # Pair comparison
    # ==========================================================

    def _compare(
        self,
        first: EvidenceSourceIndependenceObservation,
        second: EvidenceSourceIndependenceObservation,
    ) -> EvidenceSourceIndependencePair:
        """
        Compare provenance of two distinct Evidence
        objects.
        """

        (
            first,
            second,
        ) = self._ordered_pair(
            first,
            second,
        )

        # ======================================================
        # 1. Same Source
        # ======================================================

        if (
            first.source_id
            ==
            second.source_id
        ):

            return self._pair(
                first=first,
                second=second,
                relation=(
                    EvidenceSourceRelation
                    .DEPENDENT
                ),
                score=0.0,
                reason_code="same_source",
                reason=(
                    "Evidence objects originate from "
                    "the same Source record."
                ),
            )

        # ======================================================
        # 2. Same content fingerprint
        #
        # Copies of identical underlying content must not
        # count as independent corroboration.
        # ======================================================

        first_fingerprint = (
            self._normalize_fingerprint(
                first.content_fingerprint
            )
        )

        second_fingerprint = (
            self._normalize_fingerprint(
                second.content_fingerprint
            )
        )

        if (
            first_fingerprint
            and
            second_fingerprint
            and
            first_fingerprint
            ==
            second_fingerprint
        ):

            return self._pair(
                first=first,
                second=second,
                relation=(
                    EvidenceSourceRelation
                    .DEPENDENT
                ),
                score=0.0,
                reason_code=(
                    "shared_content_fingerprint"
                ),
                reason=(
                    "Evidence objects share the same "
                    "content fingerprint."
                ),
                details={
                    "content_fingerprint": (
                        first_fingerprint
                    ),
                },
            )

        # ======================================================
        # 3. Shared lineage
        # ======================================================

        first_lineage = {
            self._normalize_key(
                key
            )
            for key
            in first.lineage_keys
            if self._normalize_key(
                key
            )
        }

        second_lineage = {
            self._normalize_key(
                key
            )
            for key
            in second.lineage_keys
            if self._normalize_key(
                key
            )
        }

        shared_lineage = tuple(
            sorted(
                first_lineage
                &
                second_lineage
            )
        )

        if shared_lineage:

            return self._pair(
                first=first,
                second=second,
                relation=(
                    EvidenceSourceRelation
                    .DEPENDENT
                ),
                score=0.0,
                reason_code=(
                    "shared_lineage"
                ),
                reason=(
                    "Evidence objects share known "
                    "provenance lineage."
                ),
                shared_lineage_keys=(
                    shared_lineage
                ),
            )

        # ======================================================
        # 4. Explicit origin
        # ======================================================

        first_origin = (
            self._normalize_key(
                first.origin_key
            )
        )

        second_origin = (
            self._normalize_key(
                second.origin_key
            )
        )

        if (
            first_origin
            and
            second_origin
        ):

            if (
                first_origin
                ==
                second_origin
            ):

                return self._pair(
                    first=first,
                    second=second,
                    relation=(
                        EvidenceSourceRelation
                        .DEPENDENT
                    ),
                    score=0.0,
                    reason_code=(
                        "shared_origin"
                    ),
                    reason=(
                        "Evidence objects share the "
                        "same explicit primary origin."
                    ),
                    details={
                        "origin_key": (
                            first_origin
                        ),
                    },
                )

            return self._pair(
                first=first,
                second=second,
                relation=(
                    EvidenceSourceRelation
                    .INDEPENDENT
                ),
                score=1.0,
                reason_code=(
                    "distinct_verified_origins"
                ),
                reason=(
                    "Evidence objects have distinct "
                    "explicit primary origins."
                ),
                details={
                    "first_origin_key": (
                        first_origin
                    ),
                    "second_origin_key": (
                        second_origin
                    ),
                },
            )

        # ======================================================
        # 5. Different source IDs alone are insufficient
        # ======================================================

        return self._pair(
            first=first,
            second=second,
            relation=(
                EvidenceSourceRelation
                .UNKNOWN
            ),
            score=None,
            reason_code=(
                "origin_relationship_unknown"
            ),
            reason=(
                "Source records are different, but "
                "available provenance is insufficient "
                "to establish independence."
            ),
        )

    # ==========================================================
    # Observation preparation
    # ==========================================================

    def _prepare_observations(
        self,
        observations: list[
            EvidenceSourceIndependenceObservation
        ],
    ) -> tuple[
        list[
            EvidenceSourceIndependenceObservation
        ],
        int,
    ]:
        """
        Deduplicate Evidence descriptors.

        Repeated descriptors for the same Evidence are
        merged conservatively.

        Conflicting provenance information for the same
        Evidence raises an error instead of silently
        choosing one version.
        """

        grouped: dict[
            UUID,
            list[
                EvidenceSourceIndependenceObservation
            ],
        ] = {}

        for observation in observations:

            grouped.setdefault(
                observation.evidence_id,
                [],
            ).append(
                observation
            )

        result: list[
            EvidenceSourceIndependenceObservation
        ] = []

        duplicate_count = 0

        for evidence_id in sorted(
            grouped,
            key=str,
        ):

            group = grouped[
                evidence_id
            ]

            duplicate_count += (
                len(
                    group
                )
                -
                1
            )

            source_ids = {
                item.source_id
                for item
                in group
            }

            if len(
                source_ids
            ) != 1:

                raise ValueError(
                    "Conflicting source_id values "
                    "for the same Evidence object."
                )

            source_type = (
                self._merge_optional_value(
                    [
                        item.source_type
                        for item
                        in group
                    ],
                    field_name="source_type",
                )
            )

            origin_key = (
                self._merge_optional_value(
                    [
                        item.origin_key
                        for item
                        in group
                    ],
                    field_name="origin_key",
                )
            )

            fingerprint = (
                self._merge_optional_value(
                    [
                        item.content_fingerprint
                        for item
                        in group
                    ],
                    field_name=(
                        "content_fingerprint"
                    ),
                    normalizer=(
                        self._normalize_fingerprint
                    ),
                )
            )

            lineage = tuple(
                sorted(
                    {
                        normalized
                        for item
                        in group
                        for key
                        in item.lineage_keys
                        if (
                            normalized
                            :=
                            self._normalize_key(
                                key
                            )
                        )
                    }
                )
            )

            # Select details deterministically only for
            # diagnostics. They do not affect scoring.
            canonical = min(
                group,
                key=self._stable_observation_key,
            )

            result.append(
                EvidenceSourceIndependenceObservation(
                    evidence_id=(
                        evidence_id
                    ),
                    source_id=next(
                        iter(
                            source_ids
                        )
                    ),
                    source_type=(
                        source_type
                    ),
                    origin_key=(
                        origin_key
                    ),
                    lineage_keys=(
                        lineage
                    ),
                    content_fingerprint=(
                        fingerprint
                    ),
                    details=dict(
                        canonical.details
                    ),
                )
            )

        return (
            result,
            duplicate_count,
        )

    # ==========================================================
    # Constructors
    # ==========================================================

    @staticmethod
    def _pair(
        *,
        first: EvidenceSourceIndependenceObservation,
        second: EvidenceSourceIndependenceObservation,
        relation: EvidenceSourceRelation,
        score: float | None,
        reason_code: str,
        reason: str,
        shared_lineage_keys: tuple[
            str,
            ...,
        ] = (),
        details: dict[
            str,
            Any,
        ] | None = None,
    ) -> EvidenceSourceIndependencePair:

        return (
            EvidenceSourceIndependencePair(
                first_evidence_id=(
                    first.evidence_id
                ),
                second_evidence_id=(
                    second.evidence_id
                ),
                first_source_id=(
                    first.source_id
                ),
                second_source_id=(
                    second.source_id
                ),
                relation=relation,
                score=score,
                reason_code=reason_code,
                reason=reason,
                shared_lineage_keys=(
                    shared_lineage_keys
                ),
                details=dict(
                    details
                    or {}
                ),
            )
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _ordered_pair(
        first: EvidenceSourceIndependenceObservation,
        second: EvidenceSourceIndependenceObservation,
    ) -> tuple[
        EvidenceSourceIndependenceObservation,
        EvidenceSourceIndependenceObservation,
    ]:

        if (
            str(
                first.evidence_id
            )
            <=
            str(
                second.evidence_id
            )
        ):

            return (
                first,
                second,
            )

        return (
            second,
            first,
        )

    @staticmethod
    def _merge_optional_value(
        values: list[
            str | None
        ],
        *,
        field_name: str,
        normalizer=None,
    ) -> str | None:

        if normalizer is None:

            normalizer = (
                EvidenceSourceIndependenceService
                ._normalize_key
            )

        normalized_values = {
            normalized
            for value
            in values
            if (
                normalized
                :=
                normalizer(
                    value
                )
            )
        }

        if not normalized_values:

            return None

        if (
            len(
                normalized_values
            )
            >
            1
        ):

            raise ValueError(
                f"Conflicting {field_name} values "
                "for the same Evidence object."
            )

        return next(
            iter(
                normalized_values
            )
        )

    @staticmethod
    def _normalize_key(
        value: Any,
    ) -> str:

        if value is None:

            return ""

        return str(
            value
        ).strip()

    @staticmethod
    def _normalize_fingerprint(
        value: Any,
    ) -> str:

        if value is None:

            return ""

        return str(
            value
        ).strip().lower()

    @staticmethod
    def _stable_observation_key(
        observation: (
            EvidenceSourceIndependenceObservation
        ),
    ) -> tuple[
        str,
        str,
        str,
        str,
        str,
    ]:

        return (
            str(
                observation.source_id
            ),
            str(
                observation.source_type
                or ""
            ),
            str(
                observation.origin_key
                or ""
            ),
            str(
                observation.content_fingerprint
                or ""
            ),
            json.dumps(
                observation.details,
                sort_keys=True,
                default=str,
                separators=(
                    ",",
                    ":",
                ),
            ),
        )

    @staticmethod
    def _reason_count(
        pairs: list[
            EvidenceSourceIndependencePair
        ],
        reason_code: str,
    ) -> int:

        return sum(
            1
            for pair
            in pairs
            if (
                pair.reason_code
                ==
                reason_code
            )
        )

    @staticmethod
    def _clamp(
        value: float,
    ) -> float:

        return min(
            1.0,
            max(
                0.0,
                float(
                    value
                ),
            ),
        )
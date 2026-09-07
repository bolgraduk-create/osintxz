"""
Exact identifier signals.

Builds deterministic entity-resolution signals
from strong canonical identifiers and metadata IDs.

Responsibilities:

- compare strong canonical entity identifiers
- compare platform-specific metadata identifiers
- detect exact support signals
- detect exact identifier contradictions
- preserve explainability details
- produce EntityResolutionSignal objects

Does NOT:

- calculate fuzzy name similarity
- calculate final identity score
- calculate final confidence
- decide MATCH / REVIEW / NO_MATCH
- merge entities
- access the database
"""

from __future__ import annotations

import json

from dataclasses import (
    dataclass,
    field,
)

from typing import Any

from app.entity_resolution.contracts import (
    EntityResolutionReason,
    EntityResolutionSignal,
    EntityResolutionSignalDirection,
    EntityResolutionSignalType,
)

from app.entity_resolution.normalizer import (
    EntityNormalizer,
)

from app.models.entity import (
    Entity,
    EntityType,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    slots=True,
)
class ExactIdentifierSignalConfig:
    """
    Weights for strong exact identifiers.

    Weights are intentionally separate from signal score.

    signal.score:
        strength of the observed exact fact.

    signal.weight:
        importance of that fact for later
        identity scoring.
    """

    entity_type_weights: dict[
        EntityType,
        float,
    ] = field(
        default_factory=lambda: {
            EntityType.EMAIL: 1.00,
            EntityType.PHONE: 1.00,
            EntityType.BANK_CARD: 1.00,
            EntityType.USERNAME: 0.80,
            EntityType.DOMAIN: 0.75,
        }
    )

    metadata_identifier_weights: dict[
        str,
        float,
    ] = field(
        default_factory=lambda: {
            "telegram_id": 1.00,
            "discord_id": 1.00,
            "vk_id": 1.00,
            "instagram_id": 1.00,
            "facebook_id": 1.00,
            "github_id": 1.00,
            "google_id": 1.00,
        }
    )

    scoped_metadata_weights: dict[
        str,
        float,
    ] = field(
        default_factory=lambda: {
            "user_id": 0.95,
            "account_id": 0.95,
            "profile_id": 0.95,
        }
    )

    source_scope_keys: tuple[
        str,
        ...,
    ] = (
        "source",
        "platform",
        "provider",
        "service",
        "network",
    )

    def __post_init__(
        self,
    ) -> None:

        for (
            entity_type,
            weight,
        ) in self.entity_type_weights.items():

            self.entity_type_weights[
                entity_type
            ] = self._validate_weight(
                weight,
                name=(
                    "entity_type_weights"
                    f"[{entity_type.value}]"
                ),
            )

        for (
            key,
            weight,
        ) in (
            self.metadata_identifier_weights
            .items()
        ):

            self.metadata_identifier_weights[
                key
            ] = self._validate_weight(
                weight,
                name=(
                    "metadata_identifier_weights"
                    f"[{key}]"
                ),
            )

        for (
            key,
            weight,
        ) in (
            self.scoped_metadata_weights
            .items()
        ):

            self.scoped_metadata_weights[
                key
            ] = self._validate_weight(
                weight,
                name=(
                    "scoped_metadata_weights"
                    f"[{key}]"
                ),
            )

    @staticmethod
    def _validate_weight(
        value: float,
        *,
        name: str,
    ) -> float:

        normalized = float(
            value
        )

        if normalized < 0.0:

            raise ValueError(
                f"{name} cannot be negative."
            )

        return normalized


# ==========================================================
# Signal builder
# ==========================================================


class ExactIdentifierSignalBuilder:
    """
    Build strong exact-match and exact-conflict signals.

    Important:

    This class generates evidence for later scoring.

    It does NOT decide whether two entities are
    ultimately the same identity.
    """

    def __init__(
        self,
        normalizer: EntityNormalizer | None = None,
        config: ExactIdentifierSignalConfig | None = None,
    ) -> None:

        self.normalizer = (
            normalizer
            or EntityNormalizer()
        )

        self.config = (
            config
            or ExactIdentifierSignalConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def build(
        self,
        first: Entity,
        second: Entity,
    ) -> list[
        EntityResolutionSignal
    ]:
        """
        Build all applicable exact identifier signals.

        Result ordering is deterministic.
        """

        signals: list[
            EntityResolutionSignal
        ] = []

        first_type = (
            self._resolve_entity_type(
                getattr(
                    first,
                    "entity_type",
                    None,
                )
            )
        )

        second_type = (
            self._resolve_entity_type(
                getattr(
                    second,
                    "entity_type",
                    None,
                )
            )
        )

        # ======================================================
        # Canonical entity-value signal
        # ======================================================

        if (
            first_type is not None
            and first_type == second_type
        ):

            value_signal = (
                self._build_entity_value_signal(
                    entity_type=first_type,
                    first=first,
                    second=second,
                )
            )

            if value_signal is not None:

                signals.append(
                    value_signal
                )

        # ======================================================
        # Metadata signals
        # ======================================================

        first_metadata = self._parse_metadata(
            getattr(
                first,
                "metadata_json",
                None,
            )
        )

        second_metadata = self._parse_metadata(
            getattr(
                second,
                "metadata_json",
                None,
            )
        )

        signals.extend(
            self._build_explicit_metadata_signals(
                first_metadata=first_metadata,
                second_metadata=second_metadata,
            )
        )

        signals.extend(
            self._build_scoped_metadata_signals(
                first_metadata=first_metadata,
                second_metadata=second_metadata,
            )
        )

        # ======================================================
        # Deterministic output
        # ======================================================

        signals.sort(
            key=lambda signal: (
                signal.name,
                signal.direction.value,
                signal.signal_type.value,
            )
        )

        return signals

    def build_reasons(
        self,
        signals: list[
            EntityResolutionSignal
        ],
    ) -> list[
        EntityResolutionReason
    ]:
        """
        Convert generated signals into UI/report-ready
        explainability reasons.
        """

        reasons: list[
            EntityResolutionReason
        ] = []

        for signal in signals:

            if not signal.reason:

                continue

            reasons.append(
                EntityResolutionReason(
                    code=signal.name,
                    message=signal.reason,
                    direction=signal.direction,
                    signal_name=signal.name,
                    score=signal.score,
                    details=dict(
                        signal.details
                    ),
                )
            )

        return reasons

    # ==========================================================
    # Canonical entity identifiers
    # ==========================================================

    def _build_entity_value_signal(
        self,
        *,
        entity_type: EntityType,
        first: Entity,
        second: Entity,
    ) -> (
        EntityResolutionSignal
        | None
    ):
        """
        Compare strong atomic entity types.

        PERSON / ORGANIZATION / LOCATION etc. are
        intentionally excluded here.
        """

        weight = (
            self.config
            .entity_type_weights
            .get(
                entity_type
            )
        )

        if weight is None:

            return None

        first_value = self._canonical_entity_value(
            first,
            entity_type,
        )

        second_value = self._canonical_entity_value(
            second,
            entity_type,
        )

        if (
            not first_value
            or not second_value
        ):

            return None

        if first_value == second_value:

            return EntityResolutionSignal(
                name=(
                    f"{entity_type.value}"
                    "_exact"
                ),
                signal_type=(
                    EntityResolutionSignalType
                    .EXACT_IDENTIFIER
                ),
                direction=(
                    EntityResolutionSignalDirection
                    .SUPPORT
                ),
                score=1.0,
                weight=weight,
                reason=(
                    "Canonical "
                    f"{entity_type.value} "
                    "identifiers are identical."
                ),
                details={
                    "entity_type": (
                        entity_type.value
                    ),
                    "first": first_value,
                    "second": second_value,
                },
            )

        return EntityResolutionSignal(
            name=(
                f"{entity_type.value}"
                "_conflict"
            ),
            signal_type=(
                EntityResolutionSignalType
                .CONTRADICTION
            ),
            direction=(
                EntityResolutionSignalDirection
                .CONTRADICT
            ),
            score=1.0,
            weight=weight,
            reason=(
                "Canonical "
                f"{entity_type.value} "
                "identifiers are different."
            ),
            details={
                "entity_type": (
                    entity_type.value
                ),
                "first": first_value,
                "second": second_value,
            },
        )

    def _canonical_entity_value(
        self,
        entity: Entity,
        entity_type: EntityType,
    ) -> str:

        normalized_value = getattr(
            entity,
            "normalized_value",
            None,
        )

        raw_value = getattr(
            entity,
            "value",
            "",
        )

        source_value = (
            normalized_value
            if normalized_value
            not in (
                None,
                "",
            )
            else raw_value
        )

        return self.normalizer.normalize(
            entity_type,
            source_value,
        )

    # ==========================================================
    # Explicit platform metadata identifiers
    # ==========================================================

    def _build_explicit_metadata_signals(
        self,
        *,
        first_metadata: dict[str, Any],
        second_metadata: dict[str, Any],
    ) -> list[
        EntityResolutionSignal
    ]:

        signals: list[
            EntityResolutionSignal
        ] = []

        for key in sorted(
            self.config
            .metadata_identifier_weights
        ):

            weight = (
                self.config
                .metadata_identifier_weights[
                    key
                ]
            )

            first_value = (
                self._normalize_metadata_identifier(
                    first_metadata.get(
                        key
                    )
                )
            )

            second_value = (
                self._normalize_metadata_identifier(
                    second_metadata.get(
                        key
                    )
                )
            )

            # Both values are required.
            # One missing value is absence of evidence,
            # not a contradiction.
            if (
                not first_value
                or not second_value
            ):

                continue

            if first_value == second_value:

                signals.append(
                    EntityResolutionSignal(
                        name=(
                            f"metadata_{key}"
                            "_exact"
                        ),
                        signal_type=(
                            EntityResolutionSignalType
                            .METADATA_IDENTIFIER
                        ),
                        direction=(
                            EntityResolutionSignalDirection
                            .SUPPORT
                        ),
                        score=1.0,
                        weight=weight,
                        reason=(
                            f"Both entities have the "
                            f"same {key}."
                        ),
                        details={
                            "metadata_key": key,
                            "first": first_value,
                            "second": second_value,
                        },
                    )
                )

            else:

                signals.append(
                    EntityResolutionSignal(
                        name=(
                            f"metadata_{key}"
                            "_conflict"
                        ),
                        signal_type=(
                            EntityResolutionSignalType
                            .CONTRADICTION
                        ),
                        direction=(
                            EntityResolutionSignalDirection
                            .CONTRADICT
                        ),
                        score=1.0,
                        weight=weight,
                        reason=(
                            f"The entities have "
                            f"different {key} values."
                        ),
                        details={
                            "metadata_key": key,
                            "first": first_value,
                            "second": second_value,
                        },
                    )
                )

        return signals

    # ==========================================================
    # Source-scoped generic metadata identifiers
    # ==========================================================

    def _build_scoped_metadata_signals(
        self,
        *,
        first_metadata: dict[str, Any],
        second_metadata: dict[str, Any],
    ) -> list[
        EntityResolutionSignal
    ]:

        first_scope = (
            self._metadata_source_scope(
                first_metadata
            )
        )

        second_scope = (
            self._metadata_source_scope(
                second_metadata
            )
        )

        # Generic IDs are only comparable inside
        # the same explicit source/platform namespace.
        if (
            not first_scope
            or not second_scope
            or first_scope != second_scope
        ):

            return []

        signals: list[
            EntityResolutionSignal
        ] = []

        for key in sorted(
            self.config
            .scoped_metadata_weights
        ):

            weight = (
                self.config
                .scoped_metadata_weights[
                    key
                ]
            )

            first_value = (
                self._normalize_metadata_identifier(
                    first_metadata.get(
                        key
                    )
                )
            )

            second_value = (
                self._normalize_metadata_identifier(
                    second_metadata.get(
                        key
                    )
                )
            )

            if (
                not first_value
                or not second_value
            ):

                continue

            details = {
                "metadata_key": key,
                "source_scope": (
                    first_scope
                ),
                "first": first_value,
                "second": second_value,
            }

            if first_value == second_value:

                signals.append(
                    EntityResolutionSignal(
                        name=(
                            "metadata_scoped_"
                            f"{key}_exact"
                        ),
                        signal_type=(
                            EntityResolutionSignalType
                            .METADATA_IDENTIFIER
                        ),
                        direction=(
                            EntityResolutionSignalDirection
                            .SUPPORT
                        ),
                        score=1.0,
                        weight=weight,
                        reason=(
                            f"Both entities have the "
                            f"same {key} within "
                            f"{first_scope}."
                        ),
                        details=details,
                    )
                )

            else:

                signals.append(
                    EntityResolutionSignal(
                        name=(
                            "metadata_scoped_"
                            f"{key}_conflict"
                        ),
                        signal_type=(
                            EntityResolutionSignalType
                            .CONTRADICTION
                        ),
                        direction=(
                            EntityResolutionSignalDirection
                            .CONTRADICT
                        ),
                        score=1.0,
                        weight=weight,
                        reason=(
                            f"The entities have different "
                            f"{key} values within "
                            f"{first_scope}."
                        ),
                        details=details,
                    )
                )

        return signals

    # ==========================================================
    # Metadata helpers
    # ==========================================================

    def _metadata_source_scope(
        self,
        metadata: dict[str, Any],
    ) -> str:

        for key in (
            self.config
            .source_scope_keys
        ):

            value = (
                self._normalize_metadata_identifier(
                    metadata.get(
                        key
                    )
                )
            )

            if value:

                return value

        return ""

    @staticmethod
    def _normalize_metadata_identifier(
        value: Any,
    ) -> str:

        if value is None:

            return ""

        return str(
            value
        ).strip().casefold()

    @staticmethod
    def _parse_metadata(
        metadata_json: Any,
    ) -> dict[str, Any]:

        if isinstance(
            metadata_json,
            dict,
        ):

            return metadata_json

        if metadata_json is None:

            return {}

        text = str(
            metadata_json
        ).strip()

        if not text:

            return {}

        try:

            parsed = json.loads(
                text
            )

        except (
            TypeError,
            ValueError,
        ):

            return {}

        if not isinstance(
            parsed,
            dict,
        ):

            return {}

        return parsed

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _resolve_entity_type(
        value: Any,
    ) -> EntityType | None:

        if isinstance(
            value,
            EntityType,
        ):

            return value

        if value is None:

            return None

        try:

            return EntityType(
                str(
                    value
                )
                .strip()
                .lower()
            )

        except (
            TypeError,
            ValueError,
        ):

            return None
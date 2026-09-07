"""
Entity resolution candidate generation.

Builds a reduced set of entity pairs that are
worth passing to the identity scoring pipeline.

Responsibilities:

- isolate candidates by investigation case
- build deterministic blocking keys
- use canonical entity values
- use strong metadata identifiers
- generate conservative name blocks
- avoid full O(n^2) pair comparison
- preserve reasons why a pair became a candidate

Does NOT:

- calculate identity similarity
- calculate confidence
- decide MATCH / REVIEW / NO_MATCH
- merge entities
- modify database objects
"""

from __future__ import annotations

import json

from collections import defaultdict

from dataclasses import (
    dataclass,
    field,
)

from typing import Iterable

from uuid import UUID

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
    frozen=True,
)
class EntityCandidateGeneratorConfig:
    """
    Candidate generation configuration.

    max_neighbors_per_block limits pair explosion
    for very common blocking keys.

    Example:

        PERSON = "John Smith"

    may occur hundreds of times. Candidate generation
    must remain bounded rather than falling back to
    unrestricted O(n^2) comparison.
    """

    max_neighbors_per_block: int = 30

    max_candidates_per_entity: int = 100

    minimum_name_token_length: int = 2

    name_prefix_length: int = 4

    require_same_entity_type: bool = True

    def __post_init__(
        self,
    ) -> None:

        if (
            self.max_neighbors_per_block
            <= 0
        ):

            raise ValueError(
                "max_neighbors_per_block "
                "must be positive."
            )

        if (
            self.max_candidates_per_entity
            <= 0
        ):

            raise ValueError(
                "max_candidates_per_entity "
                "must be positive."
            )

        if (
            self.minimum_name_token_length
            <= 0
        ):

            raise ValueError(
                "minimum_name_token_length "
                "must be positive."
            )

        if (
            self.name_prefix_length
            <= 0
        ):

            raise ValueError(
                "name_prefix_length "
                "must be positive."
            )


# ==========================================================
# Candidate contract
# ==========================================================


@dataclass(
    slots=True,
)
class EntityResolutionCandidate:
    """
    One entity pair selected for deeper resolution.

    reasons:
        Human-readable machine codes describing why
        the pair entered the candidate set.

    blocking_keys:
        Deterministic blocks that connected the pair.

    Candidate presence does NOT mean the entities match.
    """

    first_entity: Entity

    second_entity: Entity

    reasons: list[str] = field(
        default_factory=list
    )

    blocking_keys: list[str] = field(
        default_factory=list
    )

    @property
    def first_entity_id(
        self,
    ) -> UUID:

        return self.first_entity.id

    @property
    def second_entity_id(
        self,
    ) -> UUID:

        return self.second_entity.id

    @property
    def case_id(
        self,
    ) -> UUID:

        return self.first_entity.case_id

    @property
    def entity_type(
        self,
    ) -> EntityType:

        return self.first_entity.entity_type

    @property
    def identity_key(
        self,
    ) -> tuple[str, str]:
        """
        Stable unordered pair identity.
        """

        first_id = str(
            self.first_entity_id
        )

        second_id = str(
            self.second_entity_id
        )

        if first_id <= second_id:

            return (
                first_id,
                second_id,
            )

        return (
            second_id,
            first_id,
        )

    def add_reason(
        self,
        reason: str,
    ) -> None:

        normalized = str(
            reason
            or ""
        ).strip()

        if (
            normalized
            and normalized
            not in self.reasons
        ):

            self.reasons.append(
                normalized
            )

    def add_blocking_key(
        self,
        blocking_key: str,
    ) -> None:

        normalized = str(
            blocking_key
            or ""
        ).strip()

        if (
            normalized
            and normalized
            not in self.blocking_keys
        ):

            self.blocking_keys.append(
                normalized
            )


# ==========================================================
# Internal block
# ==========================================================


@dataclass(
    slots=True,
    frozen=True,
)
class _EntityCandidateBlock:
    """
    Internal deterministic blocking record.
    """

    key: str

    reason: str


# ==========================================================
# Generator
# ==========================================================


class EntityCandidateGenerator:
    """
    Generate conservative entity-resolution candidates.

    Processing:

        entities
          ↓
        canonical values
          ↓
        blocking indexes
          ↓
        bounded candidate pairs
          ↓
        deduplicated candidates
    """

    _NAME_LIKE_TYPES = {
        EntityType.PERSON,
        EntityType.ORGANIZATION,
    }

    _STRONG_METADATA_KEYS = {
        "telegram_id": "telegram",
        "discord_id": "discord",
        "vk_id": "vk",
        "instagram_id": "instagram",
        "facebook_id": "facebook",
        "github_id": "github",
        "google_id": "google",
    }

    _SCOPED_METADATA_KEYS = {
        "user_id",
        "account_id",
        "profile_id",
    }

    _SOURCE_SCOPE_KEYS = (
        "source",
        "platform",
        "provider",
        "service",
        "network",
    )

    def __init__(
        self,
        normalizer: EntityNormalizer | None = None,
        config: EntityCandidateGeneratorConfig | None = None,
    ) -> None:

        self.normalizer = (
            normalizer
            or EntityNormalizer()
        )

        self.config = (
            config
            or EntityCandidateGeneratorConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def generate(
        self,
        entities: Iterable[Entity],
    ) -> list[
        EntityResolutionCandidate
    ]:
        """
        Generate candidate entity pairs.

        Input order does not control pair identity.
        Output is deterministic by entity UUID pair.
        """

        prepared = (
            self._prepare_entities(
                entities
            )
        )

        if len(prepared) < 2:

            return []

        block_index: dict[
            tuple[str, str],
            list[Entity],
        ] = defaultdict(
            list
        )

        block_reasons: dict[
            tuple[str, str],
            str,
        ] = {}

        # ======================================================
        # Build block index
        # ======================================================

        for entity in prepared:

            for block in self._build_blocks(
                entity
            ):

                scoped_key = (
                    str(entity.case_id),
                    block.key,
                )

                block_index[
                    scoped_key
                ].append(
                    entity
                )

                block_reasons[
                    scoped_key
                ] = block.reason

        # ======================================================
        # Build bounded pairs
        # ======================================================

        candidates: dict[
            tuple[str, str],
            EntityResolutionCandidate,
        ] = {}

        per_entity_counts: dict[
            UUID,
            int,
        ] = defaultdict(
            int
        )

        for scoped_key in sorted(
            block_index,
            key=lambda item: (
                item[0],
                item[1],
            ),
        ):

            members = (
                self._unique_sorted_entities(
                    block_index[
                        scoped_key
                    ]
                )
            )

            if len(members) < 2:

                continue

            block_key = scoped_key[1]

            reason = block_reasons[
                scoped_key
            ]

            self._add_block_pairs(
                members=members,
                block_key=block_key,
                reason=reason,
                candidates=candidates,
                per_entity_counts=(
                    per_entity_counts
                ),
            )

        result = list(
            candidates.values()
        )

        result.sort(
            key=lambda candidate: (
                candidate.identity_key[
                    0
                ],
                candidate.identity_key[
                    1
                ],
            )
        )

        return result

    # ==========================================================
    # Entity preparation
    # ==========================================================

    def _prepare_entities(
        self,
        entities: Iterable[Entity],
    ) -> list[Entity]:
        """
        Remove unusable and deleted objects
        without mutating input entities.
        """

        unique: dict[
            UUID,
            Entity,
        ] = {}

        for entity in entities:

            if entity is None:

                continue

            entity_id = getattr(
                entity,
                "id",
                None,
            )

            case_id = getattr(
                entity,
                "case_id",
                None,
            )

            entity_type = getattr(
                entity,
                "entity_type",
                None,
            )

            if (
                entity_id is None
                or case_id is None
                or entity_type is None
            ):

                continue

            deleted_at = getattr(
                entity,
                "deleted_at",
                None,
            )

            if deleted_at is not None:

                continue

            unique[
                entity_id
            ] = entity

        return sorted(
            unique.values(),
            key=lambda entity: (
                str(
                    entity.case_id
                ),
                str(
                    entity.entity_type
                ),
                str(
                    entity.id
                ),
            ),
        )

    # ==========================================================
    # Blocking
    # ==========================================================

    def _build_blocks(
        self,
        entity: Entity,
    ) -> list[
        _EntityCandidateBlock
    ]:
        """
        Build all safe blocking keys for one entity.
        """

        blocks: list[
            _EntityCandidateBlock
        ] = []

        entity_type = (
            self._resolve_entity_type(
                entity.entity_type
            )
        )

        if entity_type is None:

            return blocks

        canonical = (
            self._canonical_value(
                entity
            )
        )

        # ======================================================
        # Exact canonical block
        # ======================================================

        if canonical:

            blocks.append(
                _EntityCandidateBlock(
                    key=(
                        "canonical:"
                        f"{entity_type.value}:"
                        f"{canonical}"
                    ),
                    reason=(
                        "exact_canonical_value"
                    ),
                )
            )

        # ======================================================
        # Metadata identifiers
        # ======================================================

        metadata = (
            self._parse_metadata(
                getattr(
                    entity,
                    "metadata_json",
                    None,
                )
            )
        )

        blocks.extend(
            self._build_metadata_blocks(
                entity_type=entity_type,
                metadata=metadata,
            )
        )

        # ======================================================
        # Name-like blocking
        # ======================================================

        if (
            entity_type
            in self._NAME_LIKE_TYPES
            and canonical
        ):

            blocks.extend(
                self._build_name_blocks(
                    entity_type=entity_type,
                    canonical=canonical,
                )
            )

        return self._deduplicate_blocks(
            blocks
        )

    def _build_name_blocks(
        self,
        *,
        entity_type: EntityType,
        canonical: str,
    ) -> list[
        _EntityCandidateBlock
    ]:
        """
        Build conservative name candidate blocks.

        These blocks only generate candidates.

        They do NOT imply identity equality.
        """

        tokens = [
            token
            for token
            in canonical.split()
            if (
                len(token)
                >=
                self.config
                .minimum_name_token_length
            )
        ]

        if not tokens:

            return []

        blocks: list[
            _EntityCandidateBlock
        ] = []

        type_value = (
            entity_type.value
        )

        # ======================================================
        # Sorted token signature
        #
        # "John Smith"
        # "Smith John"
        #
        # become candidates, but are NOT automatically matched.
        # ======================================================

        if len(tokens) >= 2:

            token_signature = "|".join(
                sorted(
                    tokens
                )
            )

            blocks.append(
                _EntityCandidateBlock(
                    key=(
                        "name_tokens:"
                        f"{type_value}:"
                        f"{token_signature}"
                    ),
                    reason=(
                        "name_token_signature"
                    ),
                )
            )

        # ======================================================
        # Initial signature
        #
        # Alexander Petrov -> ap
        # Aleksandr Petrov -> ap
        #
        # Weak candidate block only.
        # ======================================================

        if len(tokens) >= 2:

            initials = "".join(
                token[0]
                for token
                in tokens
                if token
            )

            if len(initials) >= 2:

                blocks.append(
                    _EntityCandidateBlock(
                        key=(
                            "name_initials:"
                            f"{type_value}:"
                            f"{len(tokens)}:"
                            f"{initials}"
                        ),
                        reason=(
                            "name_initial_signature"
                        ),
                    )
                )

        # ======================================================
        # Prefix blocks
        #
        # Use first and last meaningful tokens.
        # This allows fuzzy spellings to enter the scorer
        # without comparing every PERSON to every PERSON.
        # ======================================================

        selected_tokens = {
            tokens[0],
            tokens[-1],
        }

        for token in sorted(
            selected_tokens
        ):

            prefix_length = min(
                len(token),
                self.config
                .name_prefix_length,
            )

            if (
                prefix_length
                <
                self.config
                .minimum_name_token_length
            ):

                continue

            prefix = token[
                :prefix_length
            ]

            blocks.append(
                _EntityCandidateBlock(
                    key=(
                        "name_prefix:"
                        f"{type_value}:"
                        f"{len(tokens)}:"
                        f"{prefix}"
                    ),
                    reason=(
                        "name_token_prefix"
                    ),
                )
            )

        return blocks

    # ==========================================================
    # Metadata blocking
    # ==========================================================

    def _build_metadata_blocks(
        self,
        *,
        entity_type: EntityType,
        metadata: dict,
    ) -> list[
        _EntityCandidateBlock
    ]:

        if not metadata:

            return []

        blocks: list[
            _EntityCandidateBlock
        ] = []

        # ======================================================
        # Explicit platform identifiers
        # ======================================================

        for (
            metadata_key,
            platform,
        ) in self._STRONG_METADATA_KEYS.items():

            raw_value = metadata.get(
                metadata_key
            )

            value = (
                self._normalize_metadata_identifier(
                    raw_value
                )
            )

            if not value:

                continue

            blocks.append(
                _EntityCandidateBlock(
                    key=(
                        "metadata_id:"
                        f"{entity_type.value}:"
                        f"{platform}:"
                        f"{metadata_key}:"
                        f"{value}"
                    ),
                    reason=(
                        f"metadata_{metadata_key}"
                    ),
                )
            )

        # ======================================================
        # Generic IDs require source scope
        #
        # user_id=123 on Telegram must not collide with
        # user_id=123 on another unrelated platform.
        # ======================================================

        source_scope = (
            self._metadata_source_scope(
                metadata
            )
        )

        if source_scope:

            for metadata_key in (
                self._SCOPED_METADATA_KEYS
            ):

                raw_value = metadata.get(
                    metadata_key
                )

                value = (
                    self._normalize_metadata_identifier(
                        raw_value
                    )
                )

                if not value:

                    continue

                blocks.append(
                    _EntityCandidateBlock(
                        key=(
                            "metadata_scoped_id:"
                            f"{entity_type.value}:"
                            f"{source_scope}:"
                            f"{metadata_key}:"
                            f"{value}"
                        ),
                        reason=(
                            "metadata_scoped_"
                            f"{metadata_key}"
                        ),
                    )
                )

        return blocks

    # ==========================================================
    # Pair generation
    # ==========================================================

    def _add_block_pairs(
        self,
        *,
        members: list[Entity],
        block_key: str,
        reason: str,
        candidates: dict[
            tuple[str, str],
            EntityResolutionCandidate,
        ],
        per_entity_counts: dict[
            UUID,
            int,
        ],
    ) -> None:
        """
        Generate bounded neighbor pairs inside one block.

        Pair generation is intentionally capped so a
        huge common-name block cannot explode to O(n^2).
        """

        member_count = len(
            members
        )

        neighbor_limit = min(
            self.config
            .max_neighbors_per_block,
            member_count - 1,
        )

        for index, first in enumerate(
            members
        ):

            if (
                per_entity_counts[
                    first.id
                ]
                >=
                self.config
                .max_candidates_per_entity
            ):

                continue

            last_index = min(
                member_count,
                index
                +
                1
                +
                neighbor_limit,
            )

            for second in members[
                index + 1:
                last_index
            ]:

                if (
                    self.config
                    .require_same_entity_type
                    and (
                        first.entity_type
                        !=
                        second.entity_type
                    )
                ):

                    continue

                if (
                    first.case_id
                    !=
                    second.case_id
                ):

                    continue

                if (
                    per_entity_counts[
                        first.id
                    ]
                    >=
                    self.config
                    .max_candidates_per_entity
                ):

                    break

                if (
                    per_entity_counts[
                        second.id
                    ]
                    >=
                    self.config
                    .max_candidates_per_entity
                ):

                    continue

                pair_key = (
                    self._pair_key(
                        first,
                        second,
                    )
                )

                existing = candidates.get(
                    pair_key
                )

                if existing is not None:

                    existing.add_reason(
                        reason
                    )

                    existing.add_blocking_key(
                        block_key
                    )

                    continue

                candidate = (
                    EntityResolutionCandidate(
                        first_entity=first,
                        second_entity=second,
                        reasons=[
                            reason
                        ],
                        blocking_keys=[
                            block_key
                        ],
                    )
                )

                candidates[
                    pair_key
                ] = candidate

                per_entity_counts[
                    first.id
                ] += 1

                per_entity_counts[
                    second.id
                ] += 1

    # ==========================================================
    # Canonical values
    # ==========================================================

    def _canonical_value(
        self,
        entity: Entity,
    ) -> str:

        entity_type = (
            self._resolve_entity_type(
                entity.entity_type
            )
        )

        if entity_type is None:

            return ""

        supplied_normalized = getattr(
            entity,
            "normalized_value",
            None,
        )

        source_value = (
            supplied_normalized
            if supplied_normalized
            not in (
                None,
                "",
            )
            else getattr(
                entity,
                "value",
                "",
            )
        )

        return self.normalizer.normalize(
            entity_type,
            source_value,
        )

    # ==========================================================
    # Metadata
    # ==========================================================

    @staticmethod
    def _parse_metadata(
        metadata_json,
    ) -> dict:

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

            result = json.loads(
                text
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):

            return {}

        if not isinstance(
            result,
            dict,
        ):

            return {}

        return result

    def _metadata_source_scope(
        self,
        metadata: dict,
    ) -> str:

        for key in (
            self._SOURCE_SCOPE_KEYS
        ):

            value = metadata.get(
                key
            )

            normalized = (
                self._normalize_metadata_identifier(
                    value
                )
            )

            if normalized:

                return normalized

        return ""

    @staticmethod
    def _normalize_metadata_identifier(
        value,
    ) -> str:

        if value is None:

            return ""

        return str(
            value
        ).strip().casefold()

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _pair_key(
        first: Entity,
        second: Entity,
    ) -> tuple[str, str]:

        first_id = str(
            first.id
        )

        second_id = str(
            second.id
        )

        if first_id <= second_id:

            return (
                first_id,
                second_id,
            )

        return (
            second_id,
            first_id,
        )

    @staticmethod
    def _unique_sorted_entities(
        entities: list[Entity],
    ) -> list[Entity]:

        unique = {
            entity.id: entity
            for entity
            in entities
        }

        return sorted(
            unique.values(),
            key=lambda entity: str(
                entity.id
            ),
        )

    @staticmethod
    def _deduplicate_blocks(
        blocks: list[
            _EntityCandidateBlock
        ],
    ) -> list[
        _EntityCandidateBlock
    ]:

        unique: dict[
            tuple[str, str],
            _EntityCandidateBlock,
        ] = {}

        for block in blocks:

            key = (
                block.key,
                block.reason,
            )

            unique[
                key
            ] = block

        return sorted(
            unique.values(),
            key=lambda block: (
                block.key,
                block.reason,
            ),
        )

    @staticmethod
    def _resolve_entity_type(
        value,
    ) -> EntityType | None:

        if isinstance(
            value,
            EntityType,
        ):

            return value

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
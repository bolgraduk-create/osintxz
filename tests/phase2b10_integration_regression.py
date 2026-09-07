from uuid import uuid4

from sqlalchemy.orm import Session

from app.entity_resolution.candidate_generator import (
    EntityResolutionCandidate,
)

from app.entity_resolution.contracts import (
    EntityResolutionDecision,
    EntityResolutionSignalDirection,
    EntityResolutionSignalType,
)

from app.entity_resolution.evidence_bridge import (
    EvidenceIdentityBridgeObservation,
)

from app.evidence.entity_evidence_scoring import (
    EntityEvidenceAssociationResult,
)

from app.models.entity import (
    Entity,
    EntityType,
)

from app.services.entity_resolution_pipeline import (
    EntityResolutionPipeline,
)


CASE_ID = uuid4()

session = Session()

pipeline = EntityResolutionPipeline(
    session
)


def person(
    value: str,
) -> Entity:

    return Entity(
        id=uuid4(),
        case_id=CASE_ID,
        entity_type=EntityType.PERSON,
        value=value,
        normalized_value=(
            value.casefold()
        ),
        confidence=1.0,
        metadata_json=None,
    )


def association(
    *,
    entity: Entity,
    evidence_id,
    association_score: float,
    confidence: float,
    contradiction_score: float = 0.0,
) -> EntityEvidenceAssociationResult:

    return (
        EntityEvidenceAssociationResult(
            case_id=CASE_ID,
            entity_id=entity.id,
            evidence_id=evidence_id,
            association_score=(
                association_score
            ),
            confidence=confidence,
            support_score=(
                association_score
            ),
            contradiction_score=(
                contradiction_score
            ),
            conflict_score=min(
                association_score,
                contradiction_score,
            ),
            assessment_strength=max(
                association_score,
                contradiction_score,
            ),
            signal_count_factor=0.5,
            hard_conflict=False,
        )
    )


def support_observation(
    first: Entity,
    second: Entity,
    *,
    evidence_id=None,
) -> EvidenceIdentityBridgeObservation:

    evidence_id = (
        evidence_id
        or uuid4()
    )

    return (
        EvidenceIdentityBridgeObservation(
            proposition_key=(
                "entity_identity:"
                f"{first.id}:"
                f"{second.id}"
            ),
            first_association=(
                association(
                    entity=first,
                    evidence_id=evidence_id,
                    association_score=1.0,
                    confidence=1.0,
                )
            ),
            second_association=(
                association(
                    entity=second,
                    evidence_id=evidence_id,
                    association_score=1.0,
                    confidence=1.0,
                )
            ),
            direction=(
                EntityResolutionSignalDirection
                .SUPPORT
            ),
            identity_relevance=1.0,
            reason=(
                "Explicit identity-bearing Evidence "
                "supports this entity pair."
            ),
        )
    )


def contradiction_observation(
    first: Entity,
    second: Entity,
    *,
    evidence_id=None,
) -> EvidenceIdentityBridgeObservation:

    evidence_id = (
        evidence_id
        or uuid4()
    )

    return (
        EvidenceIdentityBridgeObservation(
            proposition_key=(
                "entity_identity:"
                f"{first.id}:"
                f"{second.id}"
            ),
            first_association=(
                association(
                    entity=first,
                    evidence_id=evidence_id,
                    association_score=1.0,
                    confidence=1.0,
                )
            ),
            second_association=(
                association(
                    entity=second,
                    evidence_id=evidence_id,
                    association_score=0.0,
                    confidence=1.0,
                    contradiction_score=1.0,
                )
            ),
            direction=(
                EntityResolutionSignalDirection
                .CONTRADICT
            ),
            identity_relevance=1.0,
            reason=(
                "Explicit Evidence associates with "
                "the first Entity and contradicts "
                "the second."
            ),
        )
    )


print()
print("=" * 100)
print(
    "PHASE 2B.10 ENTITY RESOLUTION "
    "EVIDENCE INTEGRATION"
)
print("=" * 100)


# ==========================================================
# 1. Baseline remains unchanged
#
# Exact PERSON name alone is intentionally REVIEW
# in the modern resolution policy.
# ==========================================================

first = person(
    "John Smith"
)

second = person(
    "John Smith"
)


baseline = (
    pipeline.process_pair(
        first,
        second,
    )
)


baseline_explicit_none = (
    pipeline.process_pair(
        first,
        second,
        evidence_observations=None,
    )
)


print()
print(
    "BASELINE:"
)

print(
    "decision:",
    baseline.decision.value,
)

print(
    "identity:",
    baseline.identity_score,
)

print(
    "confidence:",
    baseline.confidence,
)


assert (
    baseline
    ==
    baseline_explicit_none
)

assert (
    "evidence_bridge"
    not in
    baseline.metadata
)

assert (
    baseline.decision
    ==
    EntityResolutionDecision.REVIEW
)


# ==========================================================
# 2. Explicit Evidence enters SAME resolution engine
#
# Exact PERSON name + strong explicit Evidence:
#
# old name support + Evidence support
# can cross normal multi-signal MATCH policy.
# ==========================================================

evidence_support = (
    support_observation(
        first,
        second,
    )
)


with_evidence = (
    pipeline.process_pair(
        first,
        second,
        evidence_observations=[
            evidence_support
        ],
    )
)


print()
print(
    "WITH EVIDENCE:"
)

print(
    "decision:",
    with_evidence.decision.value,
)

print(
    "identity:",
    with_evidence.identity_score,
)

print(
    "confidence:",
    with_evidence.confidence,
)


assert (
    with_evidence.identity_score
    >
    baseline.identity_score
)

assert (
    with_evidence.support_score
    >
    baseline.support_score
)

assert any(
    signal.signal_type
    ==
    EntityResolutionSignalType.EVIDENCE
    for signal
    in with_evidence.signals
)

assert (
    "evidence_bridge"
    in
    with_evidence.metadata
)

assert (
    with_evidence.metadata[
        "evidence_bridge"
    ][
        "signal_count"
    ]
    ==
    1
)

assert (
    with_evidence.decision
    ==
    EntityResolutionDecision.MATCH
)


# ==========================================================
# 3. Evidence-only MATCH protection
# ==========================================================

different_a = person(
    "Alice Example"
)

different_b = person(
    "Zed Unknown"
)


evidence_only_support = (
    support_observation(
        different_a,
        different_b,
    )
)


evidence_only_result = (
    pipeline.process_pair(
        different_a,
        different_b,
        evidence_observations=[
            evidence_only_support
        ],
    )
)


print()
print(
    "EVIDENCE-ONLY SUPPORT:"
)

print(
    "decision:",
    evidence_only_result
    .decision.value,
)

print(
    "identity:",
    evidence_only_result
    .identity_score,
)


assert (
    evidence_only_result.decision
    !=
    EntityResolutionDecision.MATCH
)


# ==========================================================
# 4. Evidence-only NO_MATCH protection
# ==========================================================

evidence_only_conflict = (
    contradiction_observation(
        different_a,
        different_b,
    )
)


conflict_only_result = (
    pipeline.process_pair(
        different_a,
        different_b,
        evidence_observations=[
            evidence_only_conflict
        ],
    )
)


print()
print(
    "EVIDENCE-ONLY CONTRADICTION:"
)

print(
    "decision:",
    conflict_only_result
    .decision.value,
)

print(
    "contradiction:",
    conflict_only_result
    .contradiction_score,
)


assert any(
    signal.signal_type
    ==
    EntityResolutionSignalType.EVIDENCE
    and
    signal.direction
    ==
    EntityResolutionSignalDirection
    .CONTRADICT
    for signal
    in conflict_only_result.signals
)

assert (
    conflict_only_result.decision
    !=
    EntityResolutionDecision.NO_MATCH
)


# ==========================================================
# 5. Pair-binding safety
# ==========================================================

third = person(
    "John Smith"
)


wrong_pair_observation = (
    support_observation(
        first,
        third,
    )
)


try:

    pipeline.process_pair(
        first,
        second,
        evidence_observations=[
            wrong_pair_observation
        ],
    )

except ValueError:

    pass

else:

    raise AssertionError(
        "Evidence observation for a different "
        "entity pair was accepted."
    )


# ==========================================================
# 6. Case-binding safety
# ==========================================================

other_case_entity = Entity(
    id=uuid4(),
    case_id=uuid4(),
    entity_type=EntityType.PERSON,
    value="John Smith",
    normalized_value="john smith",
    confidence=1.0,
    metadata_json=None,
)


cross_case_association = (
    EntityEvidenceAssociationResult(
        case_id=(
            other_case_entity.case_id
        ),
        entity_id=(
            other_case_entity.id
        ),
        evidence_id=uuid4(),
        association_score=1.0,
        confidence=1.0,
        support_score=1.0,
        contradiction_score=0.0,
        conflict_score=0.0,
        assessment_strength=1.0,
        signal_count_factor=0.5,
        hard_conflict=False,
    )
)


# Observation construction itself must reject mixed cases.
try:

    EvidenceIdentityBridgeObservation(
        proposition_key="cross-case",
        first_association=(
            association(
                entity=first,
                evidence_id=(
                    cross_case_association
                    .evidence_id
                ),
                association_score=1.0,
                confidence=1.0,
            )
        ),
        second_association=(
            cross_case_association
        ),
        direction=(
            EntityResolutionSignalDirection
            .SUPPORT
        ),
    )

except ValueError:

    pass

else:

    raise AssertionError(
        "Cross-case Evidence bridge "
        "observation was accepted."
    )


# ==========================================================
# 7. Batch mapping
# ==========================================================

candidate = (
    EntityResolutionCandidate(
        first_entity=first,
        second_entity=second,
        reasons=[
            "regression",
        ],
        blocking_keys=[
            "regression:person",
        ],
    )
)


pair_key = tuple(
    sorted(
        (
            str(
                first.id
            ),
            str(
                second.id
            ),
        )
    )
)


batch = (
    pipeline.process_candidates(
        [
            candidate
        ],
        evidence_observations_by_pair={
            pair_key: [
                evidence_support
            ]
        },
    )
)


assert (
    batch.processed_count
    ==
    1
)

assert (
    batch.results[
        0
    ].decision
    ==
    EntityResolutionDecision.MATCH
)

assert (
    "evidence_bridge"
    in
    batch.results[
        0
    ].metadata
)


print(
    "BATCH EVIDENCE MAPPING: OK"
)


# ==========================================================
# 8. Reversed mapping key is normalized
# ==========================================================

reversed_batch = (
    pipeline.process_candidates(
        [
            candidate
        ],
        evidence_observations_by_pair={
            (
                pair_key[
                    1
                ],
                pair_key[
                    0
                ],
            ): [
                evidence_support
            ]
        },
    )
)


assert (
    reversed_batch
    ==
    batch
)


# ==========================================================
# 9. Unknown batch-pair safety
# ==========================================================

unknown_pair = (
    str(
        uuid4()
    ),
    str(
        uuid4()
    ),
)


try:

    pipeline.process_candidates(
        [
            candidate
        ],
        evidence_observations_by_pair={
            unknown_pair: [
                evidence_support
            ]
        },
    )

except ValueError:

    pass

else:

    raise AssertionError(
        "Evidence mapping for an unknown "
        "candidate pair was silently ignored."
    )


# ==========================================================
# 10. are_same_entity uses Evidence only explicitly
# ==========================================================

assert (
    pipeline.are_same_entity(
        first,
        second,
    )
    is False
)

assert (
    pipeline.are_same_entity(
        first,
        second,
        evidence_observations=[
            evidence_support
        ],
    )
    is True
)


# ==========================================================
# 11. Resolution remains non-destructive
# ==========================================================

assert (
    len(
        session.new
    )
    ==
    0
)

assert (
    len(
        session.deleted
    )
    ==
    0
)

assert (
    len(
        session.dirty
    )
    ==
    0
)


# ==========================================================
# 12. No automatic merge concept added
# ==========================================================

assert not hasattr(
    with_evidence,
    "merge"
)

assert not hasattr(
    with_evidence,
    "merged"
)


# ==========================================================
# 13. Determinism
# ==========================================================

first_run = (
    pipeline.process_pair(
        first,
        second,
        evidence_observations=[
            evidence_support
        ],
    )
)

second_run = (
    pipeline.process_pair(
        first,
        second,
        evidence_observations=[
            evidence_support
        ],
    )
)


assert (
    first_run
    ==
    second_run
)


print()
print("=" * 100)
print(
    "BACKWARD COMPATIBILITY: OK"
)
print(
    "EVIDENCE SIGNAL INJECTION: OK"
)
print(
    "EXISTING RESOLUTION MATH REUSED: OK"
)
print(
    "EVIDENCE SUPPORT INTEGRATION: OK"
)
print(
    "EVIDENCE CONTRADICTION INTEGRATION: OK"
)
print(
    "EVIDENCE-ONLY MATCH PROTECTION: OK"
)
print(
    "EVIDENCE-ONLY NO-MATCH PROTECTION: OK"
)
print(
    "PAIR-BINDING SAFETY: OK"
)
print(
    "CROSS-CASE SAFETY: OK"
)
print(
    "BATCH EVIDENCE MAPPING: OK"
)
print(
    "REVERSED PAIR NORMALIZATION: OK"
)
print(
    "UNKNOWN BATCH-PAIR SAFETY: OK"
)
print(
    "EXPLAINABILITY METADATA: OK"
)
print(
    "MATCH / MERGE SEPARATION: OK"
)
print(
    "DETERMINISM: OK"
)
print(
    "DATABASE WRITES: 0"
)
print("=" * 100)

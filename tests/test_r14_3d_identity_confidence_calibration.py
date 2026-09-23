from __future__ import annotations

from pathlib import Path

from app.application.identity_confidence_calibration import (
    IdentityConfidenceCalibrationService,
)
from app.application.identity_relationship_corroboration import (
    RelationshipCorroborationResult,
)
from app.application.identity_resolution import (
    IdentityResolution,
)


def _relationship_result(
    *,
    support: float,
) -> RelationshipCorroborationResult:
    base = 0.50
    effective = base + (1.0 - base) * support
    return RelationshipCorroborationResult(
        base_confidence=base,
        effective_confidence=effective,
        support=support,
        boost=effective - base,
        signals=(),
        suppressed_circular=0,
    )


def test_supported_identity_and_social_support_raise_machine_confidence():
    service = IdentityConfidenceCalibrationService()

    identity = IdentityResolution(
        status="supported",
        score=55.0,
        matched=(
            "Full name matches",
            "Email matches",
        ),
        matched_categories=(
            "name",
            "email",
        ),
        pivot_allowed=True,
    )

    result = service.calibrate(
        base_confidence=0.50,
        identity_resolution=identity,
        relationship_result=_relationship_result(
            support=0.20
        ),
    )

    assert result.calibrated_confidence > 0.50
    assert result.identity_support > 0.0
    assert result.relationship_support == 0.20
    assert result.combined_support > 0.20
    assert result.hard_conflict is False
    assert result.pivot_allowed is True


def test_name_only_insufficient_identity_does_not_raise_confidence_by_itself():
    service = IdentityConfidenceCalibrationService()

    identity = IdentityResolution(
        status="insufficient",
        score=22.0,
        matched=(
            "Full name matches",
        ),
        matched_categories=(
            "name",
        ),
        pivot_allowed=False,
    )

    result = service.calibrate(
        base_confidence=0.67,
        identity_resolution=identity,
    )

    assert result.identity_support == 0.0
    assert result.calibrated_confidence == 0.67
    assert result.pivot_allowed is False


def test_hard_identity_conflict_caps_confidence_even_with_strong_social_support():
    service = IdentityConfidenceCalibrationService()

    identity = IdentityResolution(
        status="conflicting",
        score=20.0,
        matched=(
            "Full name matches",
        ),
        conflicts=(
            "Birth date conflicts",
        ),
        matched_categories=(
            "name",
        ),
        conflict_categories=(
            "birth_date",
        ),
        pivot_allowed=False,
    )

    result = service.calibrate(
        base_confidence=0.90,
        identity_resolution=identity,
        relationship_result=_relationship_result(
            support=0.45
        ),
    )

    assert result.hard_conflict is True
    assert result.calibrated_confidence <= 0.25
    assert result.pivot_allowed is False
    assert "Birth date conflicts" in result.negative_signals


def test_soft_conflict_penalizes_but_does_not_become_hard_conflict():
    service = IdentityConfidenceCalibrationService()

    identity = IdentityResolution(
        status="supported",
        score=60.0,
        matched=(
            "Email matches",
            "Organization matches",
        ),
        conflicts=(
            "Username conflicts",
        ),
        matched_categories=(
            "email",
            "organization",
        ),
        conflict_categories=(
            "username",
        ),
        pivot_allowed=False,
    )

    with_conflict = service.calibrate(
        base_confidence=0.60,
        identity_resolution=identity,
    )

    clean_identity = IdentityResolution(
        status="supported",
        score=60.0,
        matched=identity.matched,
        matched_categories=identity.matched_categories,
        pivot_allowed=True,
    )

    clean = service.calibrate(
        base_confidence=0.60,
        identity_resolution=clean_identity,
    )

    assert with_conflict.hard_conflict is False
    assert with_conflict.conflict_penalty > 0.0
    assert (
        with_conflict.calibrated_confidence
        < clean.calibrated_confidence
    )
    assert with_conflict.pivot_allowed is False


def test_analyst_confirmed_does_not_rewrite_machine_confidence_to_one():
    service = IdentityConfidenceCalibrationService()

    unreviewed = service.calibrate(
        base_confidence=0.71,
        analyst_decision="unreviewed",
    )
    confirmed = service.calibrate(
        base_confidence=0.71,
        analyst_decision="confirmed",
    )

    assert unreviewed.calibrated_confidence == 0.71
    assert confirmed.calibrated_confidence == 0.71
    assert confirmed.analyst_authoritative is True
    assert confirmed.analyst_decision == "confirmed"
    assert confirmed.calibrated_confidence != 1.0


def test_analyst_rejected_does_not_destroy_machine_observation():
    service = IdentityConfidenceCalibrationService()

    result = service.calibrate(
        base_confidence=0.83,
        analyst_decision="rejected",
    )

    assert result.calibrated_confidence == 0.83
    assert result.analyst_authoritative is True
    assert result.analyst_decision == "rejected"
    assert result.review_required is False


def test_relationship_support_is_bounded():
    service = IdentityConfidenceCalibrationService()

    result = service.calibrate(
        base_confidence=0.40,
        relationship_result=_relationship_result(
            support=0.90
        ),
    )

    assert result.relationship_support == 0.45
    assert result.calibrated_confidence < 0.70


def test_person_card_exposes_calibrated_machine_confidence():
    bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")
    qml = Path(
        "app/interface/desktop/qml/pages/Person.qml"
    ).read_text(encoding="utf-8")

    for token in (
        "IdentityConfidenceCalibrationService",
        "_identity_resolution_from_metadata",
        '"calibratedConfidence"',
        '"calibrationIdentitySupport"',
        '"calibrationRelationshipSupport"',
        '"calibrationConflictPenalty"',
        '"calibrationHardConflict"',
        '"calibrationReviewRequired"',
        '"calibrationPivotAllowed"',
        '"calibrationPositiveSignals"',
        '"calibrationNegativeSignals"',
    ):
        assert token in bridge

    for token in (
        "calibrationIdentitySupport",
        "calibrationRelationshipSupport",
        "calibrationConflictPenalty",
        "calibrationHardConflict",
        "calibrationLabel",
        "calibrationSummary",
        "effectiveConfidence",
        "baseConfidence",
    ):
        assert token in qml


def test_persisted_identity_pivot_false_string_does_not_become_true():
    bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")

    assert '"true",' in bridge
    assert '"yes",' in bridge
    assert '"on",' in bridge
    assert "pivot_raw" in bridge
    assert "bool(\n                pivot_raw\n            )" not in bridge

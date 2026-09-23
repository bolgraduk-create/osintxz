from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.application.person_identity_review_service import (
    PersonIdentityReviewService,
)


def _review_evidence(
    *,
    candidate_id,
    decision,
    previous,
    note,
    machine_confidence,
    created_at,
):
    return SimpleNamespace(
        id=uuid4(),
        source_id=uuid4(),
        created_at=created_at,
        metadata_json=json.dumps(
            {
                "workflow": "person_identity_review",
                "decision": decision,
                "previous_decision": previous,
                "candidate_entity_id": str(candidate_id),
                "analyst_note": note,
                "machine_confidence": machine_confidence,
                "identity_verified": decision == "confirmed",
            }
        ),
    )


def test_decision_history_is_newest_first_and_preserves_notes():
    candidate_id = uuid4()
    now = datetime.now(UTC)

    rows = [
        _review_evidence(
            candidate_id=candidate_id,
            decision="review",
            previous="unreviewed",
            note="Need a second signal.",
            machine_confidence=0.51,
            created_at=now,
        ),
        _review_evidence(
            candidate_id=candidate_id,
            decision="confirmed",
            previous="review",
            note="Known associate and matching travel event.",
            machine_confidence=0.78,
            created_at=now + timedelta(seconds=1),
        ),
    ]

    history = (
        PersonIdentityReviewService
        .decision_history_from_evidence(
            rows,
            candidate_id=candidate_id,
        )
    )

    assert [item["decision"] for item in history] == [
        "confirmed",
        "review",
    ]
    assert history[0]["previousDecision"] == "review"
    assert history[0]["note"] == (
        "Known associate and matching travel event."
    )
    assert history[0]["machineConfidence"] == 0.78
    assert history[1]["previousDecision"] == "unreviewed"


def test_decision_history_ignores_other_candidates_and_other_workflows():
    wanted = uuid4()
    other = uuid4()
    now = datetime.now(UTC)

    unrelated = _review_evidence(
        candidate_id=other,
        decision="rejected",
        previous="unreviewed",
        note="Other account.",
        machine_confidence=0.2,
        created_at=now,
    )
    wrong_workflow = _review_evidence(
        candidate_id=wanted,
        decision="review",
        previous="unreviewed",
        note="Wrong workflow row.",
        machine_confidence=0.5,
        created_at=now,
    )
    wrong_workflow.metadata_json = json.dumps(
        {
            "workflow": "person_profile_selection",
            "candidate_entity_id": str(wanted),
            "decision": "review",
        }
    )

    history = (
        PersonIdentityReviewService
        .decision_history_from_evidence(
            [unrelated, wrong_workflow],
            candidate_id=wanted,
        )
    )

    assert history == []


def test_person_card_has_review_filters_note_and_history_workflow():
    qml = Path(
        "app/interface/desktop/qml/pages/Person.qml"
    ).read_text(encoding="utf-8")
    bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")

    for token in (
        'property string candidateReviewFilter: "all"',
        'placeholderText: "Decision note (optional):',
        '"All statuses"',
        '"Unreviewed"',
        '"Needs review"',
        '"Confirmed"',
        '"Rejected"',
        'text: "History"',
        "desktopBridge.identityReviewHistory",
        "identityHistoryDialog",
        "previousDecision",
        "machineConfidence",
    ):
        assert token in qml

    for token in (
        "def identityReviewHistory(",
        ".decision_history(",
        "reviewable_profile_types",
        "excluded_profile_ids.update(",
    ):
        assert token in bridge


def test_identity_decision_note_is_sent_to_backend():
    qml = Path(
        "app/interface/desktop/qml/pages/Person.qml"
    ).read_text(encoding="utf-8")

    assert "String(candidateDecisionNote.text || "")" in qml


def test_person_avatar_size_regression_is_restored():
    qml = Path(
        "app/interface/desktop/qml/pages/Person.qml"
    ).read_text(encoding="utf-8")

    marker = 'fallbackSource: "../../assets/icons/users_purple.svg"'
    index = qml.index(marker)
    avatar_block = qml[max(0, index - 240): index + 120]

    assert "width: 72" in avatar_block
    assert "height: 72" in avatar_block

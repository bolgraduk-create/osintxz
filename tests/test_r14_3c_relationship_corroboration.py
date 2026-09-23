from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.application.identity_relationship_corroboration import (
    IdentityRelationshipCorroborationService,
)
from app.models.entity import EntityType
from app.models.relationship import RelationshipType


class FakeRelationshipService:
    def __init__(self, relationships):
        self.relationships = list(relationships)

    def get_case_relationships(self, _case_id):
        return list(self.relationships)


class FakeEntityService:
    def __init__(self, entities):
        self.entities = {
            entity.id: entity
            for entity in entities
        }

    def get_entity(self, entity_id):
        return self.entities.get(entity_id)


def _entity(*, case_id, entity_type, value, confidence=1.0, metadata=None):
    return SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=entity_type,
        value=value,
        confidence=confidence,
        metadata_json=json.dumps(metadata or {}),
    )


def _relationship(
    *,
    case_id,
    source,
    target,
    relationship_type=RelationshipType.KNOWS,
    confidence=1.0,
    evidence_id=None,
):
    metadata = {}
    if evidence_id is not None:
        metadata["evidence_id"] = str(evidence_id)

    return SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        source_entity_id=source.id,
        target_entity_id=target.id,
        relationship_type=relationship_type,
        confidence=confidence,
        metadata_json=json.dumps(metadata),
    )


def _service(relationships, entities):
    return IdentityRelationshipCorroborationService(
        relationship_service=FakeRelationshipService(
            relationships
        ),
        entity_service=FakeEntityService(
            entities
        ),
    )


def test_independent_shared_associate_increases_effective_confidence():
    case_id = uuid4()
    person = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person A",
    )
    candidate = _entity(
        case_id=case_id,
        entity_type=EntityType.ACCOUNT,
        value="@candidate",
        confidence=0.50,
    )
    associate = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person B",
    )

    relationships = [
        _relationship(
            case_id=case_id,
            source=person,
            target=associate,
            confidence=0.95,
            evidence_id=uuid4(),
        ),
        _relationship(
            case_id=case_id,
            source=candidate,
            target=associate,
            relationship_type=RelationshipType.MESSAGED,
            confidence=0.90,
            evidence_id=uuid4(),
        ),
    ]

    result = _service(
        relationships,
        [person, candidate, associate],
    ).assess(
        person=person,
        candidate=candidate,
        relationships=relationships,
    )

    assert result.base_confidence == 0.50
    assert result.effective_confidence > 0.50
    assert result.boost > 0.0
    assert result.support > 0.0
    assert len(result.signals) == 1
    assert result.signals[0].associate_label == "Person B"
    assert result.signals[0].independent_lineage is True


def test_same_provenance_is_suppressed_as_circular_support():
    case_id = uuid4()
    shared_evidence = uuid4()

    person = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person A",
    )
    candidate = _entity(
        case_id=case_id,
        entity_type=EntityType.ACCOUNT,
        value="@candidate",
        confidence=0.60,
    )
    associate = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person B",
    )

    relationships = [
        _relationship(
            case_id=case_id,
            source=person,
            target=associate,
            confidence=0.9,
            evidence_id=shared_evidence,
        ),
        _relationship(
            case_id=case_id,
            source=candidate,
            target=associate,
            confidence=0.9,
            evidence_id=shared_evidence,
        ),
    ]

    result = _service(
        relationships,
        [person, candidate, associate],
    ).assess(
        person=person,
        candidate=candidate,
        relationships=relationships,
    )

    assert result.effective_confidence == 0.60
    assert result.boost == 0.0
    assert result.signals == ()
    assert result.suppressed_circular == 1


def test_incomplete_lineage_is_downweighted_not_treated_as_full_support():
    case_id = uuid4()
    person = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person A",
    )
    candidate = _entity(
        case_id=case_id,
        entity_type=EntityType.ACCOUNT,
        value="@candidate",
        confidence=0.40,
    )
    associate = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person B",
    )

    incomplete = [
        _relationship(
            case_id=case_id,
            source=person,
            target=associate,
            confidence=1.0,
        ),
        _relationship(
            case_id=case_id,
            source=candidate,
            target=associate,
            confidence=1.0,
        ),
    ]
    complete = [
        _relationship(
            case_id=case_id,
            source=person,
            target=associate,
            confidence=1.0,
            evidence_id=uuid4(),
        ),
        _relationship(
            case_id=case_id,
            source=candidate,
            target=associate,
            confidence=1.0,
            evidence_id=uuid4(),
        ),
    ]

    service = _service(
        complete,
        [person, candidate, associate],
    )

    incomplete_result = service.assess(
        person=person,
        candidate=candidate,
        relationships=incomplete,
    )
    complete_result = service.assess(
        person=person,
        candidate=candidate,
        relationships=complete,
    )

    assert incomplete_result.boost > 0.0
    assert complete_result.boost > incomplete_result.boost
    assert incomplete_result.signals[0].independent_lineage is False


def test_candidate_metadata_mention_of_known_associate_can_corroborate():
    case_id = uuid4()
    known_evidence = uuid4()
    candidate_evidence = uuid4()

    person = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person A",
    )
    associate = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person B",
    )
    candidate = _entity(
        case_id=case_id,
        entity_type=EntityType.ACCOUNT,
        value="@candidate",
        confidence=0.55,
        metadata={
            "mentioned_entity_ids": [
                str(associate.id)
            ],
            "evidence_id": str(candidate_evidence),
        },
    )

    relationships = [
        _relationship(
            case_id=case_id,
            source=person,
            target=associate,
            confidence=0.9,
            evidence_id=known_evidence,
        )
    ]

    result = _service(
        relationships,
        [person, candidate, associate],
    ).assess(
        person=person,
        candidate=candidate,
        relationships=relationships,
    )

    assert result.effective_confidence > 0.55
    assert len(result.signals) == 1
    assert (
        result.signals[0].candidate_relationship_type
        == "metadata_mention"
    )


def test_different_social_neighborhood_does_not_raise_confidence():
    case_id = uuid4()
    person = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person A",
    )
    candidate = _entity(
        case_id=case_id,
        entity_type=EntityType.ACCOUNT,
        value="@candidate",
        confidence=0.62,
    )
    associate_b = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person B",
    )
    associate_c = _entity(
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Person C",
    )

    relationships = [
        _relationship(
            case_id=case_id,
            source=person,
            target=associate_b,
            evidence_id=uuid4(),
        ),
        _relationship(
            case_id=case_id,
            source=candidate,
            target=associate_c,
            evidence_id=uuid4(),
        ),
    ]

    result = _service(
        relationships,
        [person, candidate, associate_b, associate_c],
    ).assess(
        person=person,
        candidate=candidate,
        relationships=relationships,
    )

    assert result.effective_confidence == 0.62
    assert result.boost == 0.0
    assert result.signals == ()


def test_person_card_exposes_relationship_corroboration_separately_from_base_confidence():
    bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")
    qml = Path(
        "app/interface/desktop/qml/pages/Person.qml"
    ).read_text(encoding="utf-8")

    for token in (
        "IdentityRelationshipCorroborationService",
        '"baseConfidence"',
        '"effectiveConfidence"',
        '"relationshipBoost"',
        '"relationshipSignals"',
        '"relationshipSuppressedCircular"',
    ):
        assert token in bridge

    for token in (
        "baseConfidence",
        "effectiveConfidence",
        "relationshipBoost",
        "relationshipSummary",
        '" · social +"',
        '" → "',
    ):
        assert token in qml

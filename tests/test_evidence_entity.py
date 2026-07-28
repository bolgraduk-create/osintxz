"""
Tests for EvidenceEntity model.
"""


from app.models.evidence_entity import (
    EvidenceEntity,
)



def test_table_name():

    assert (
        EvidenceEntity.__tablename__
        ==
        "evidence_entities"
    )



def test_columns():

    columns = (
        EvidenceEntity.__table__.columns.keys()
    )


    assert (
        "evidence_id"
        in
        columns
    )


    assert (
        "entity_id"
        in
        columns
    )
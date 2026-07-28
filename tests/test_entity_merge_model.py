"""
Tests for EntityMerge model.
"""

from app.models.entity_merge import (
    EntityMerge,
)



def test_table_name():

    assert (
        EntityMerge.__tablename__
        ==
        "entity_merges"
    )



def test_columns():

    columns = (
        EntityMerge.__table__.columns.keys()
    )


    assert (
        "source_entity_id"
        in
        columns
    )


    assert (
        "target_entity_id"
        in
        columns
    )
"""
Tests for EntityComparator.
"""


from app.entity_resolution.comparator import (
    EntityComparator,
)

from app.models.entity import (
    EntityType,
)



def test_email_compare():

    comparator = EntityComparator()


    assert comparator.compare(
        EntityType.EMAIL,
        "John@Mail.com",
        "john@mail.com",
    )



def test_username_compare():

    comparator = EntityComparator()


    assert comparator.compare(
        EntityType.USERNAME,
        "John",
        "john",
    )



def test_unknown_type():

    comparator = EntityComparator()


    assert not comparator.compare(
        EntityType.PERSON,
        "John",
        "John",
    )
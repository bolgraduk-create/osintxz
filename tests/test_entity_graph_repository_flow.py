"""
Entity graph repository flow tests.
"""

from unittest.mock import MagicMock

from uuid import uuid4


from app.repositories.entity_graph_repository import (
    EntityGraphRepository,
)





class FakeEntity:

    def __init__(
        self,
        entity_id,
        value,
        entity_type,
    ):
        self.id = entity_id
        self.value = value
        self.entity_type = entity_type



class FakeRelationship:

    def __init__(
        self,
        source,
        target,
    ):
        self.source_entity_id = source
        self.target_entity_id = target
        self.relationship_type = MagicMock(
            value="knows"
        )
        self.confidence = 1.0



class FakeResult:

    def __init__(
        self,
        items,
    ):
        self.items = items


    def scalars(self):

        return self


    def all(self):

        return self.items



def test_build_case_graph():

    session = MagicMock()


    entity_a = FakeEntity(
        uuid4(),
        "John",
        MagicMock(
            value="person"
        ),
    )


    entity_b = FakeEntity(
        uuid4(),
        "Anna",
        MagicMock(
            value="person"
        ),
    )


    relationship = FakeRelationship(
        entity_a.id,
        entity_b.id,
    )


    session.execute.side_effect = [
        FakeResult(
            [
                entity_a,
                entity_b,
            ]
        ),
        FakeResult(
            [
                relationship,
            ]
        ),
    ]


    repository = EntityGraphRepository(
        session
    )


    graph = repository.build_case_graph(
        uuid4()
    )


    assert len(
        graph.nodes
    ) == 2


    assert len(
        graph.edges
    ) == 1


    assert (
        entity_b.id
        in graph.get_neighbors(
            entity_a.id
        )
    )
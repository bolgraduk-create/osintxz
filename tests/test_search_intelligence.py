"""
Search intelligence tests.
"""

from dataclasses import dataclass
from uuid import uuid4

from app.services.full_text_search import (
    FullTextSearchService,
)

from app.services.semantic_search_service import (
    SemanticSearchService,
)

from app.models.search_index import (
    SearchObjectType,
)



@dataclass
class FakeSearchIndex:
    """
    Fake object for search tests.
    """

    id: object

    case_id: object

    object_type: SearchObjectType

    object_id: object

    title: str

    content: str



def create_index(
    title: str,
    content: str,
):

    return FakeSearchIndex(
        id=uuid4(),

        case_id=uuid4(),

        object_type=SearchObjectType.NOTE,

        object_id=uuid4(),

        title=title,

        content=content,
    )



def test_full_text_search():

    service = FullTextSearchService()


    item = create_index(
        "Telegram message",
        "John contacted Peter",
    )


    assert service.match(
        item,
        "john",
    )


    assert service.match(
        item,
        "TELEGRAM",
    )



def test_full_text_ranking():

    service = FullTextSearchService()


    first = create_index(
        "Important case",
        "normal text",
    )


    second = create_index(
        "other",
        "Important information",
    )


    result = service.rank(
        [
            first,
            second,
        ],
        "important",
    )


    assert result[0] == first



def test_cosine_similarity():

    service = SemanticSearchService()


    value = service.cosine_similarity(
        [1, 0],
        [1, 0],
    )


    assert value == 1.0
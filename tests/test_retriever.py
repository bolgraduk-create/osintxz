"""
Tests for Retriever.

Checks:

- keyword retrieval
- multi-word queries
- punctuation handling
- empty results
- metadata
"""


from app.ai.rag.knowledge_store import (
    KnowledgeStore,
)

from app.ai.rag.retriever import (
    Retriever,
)



def create_retriever():

    store = KnowledgeStore()


    store.add(
        key="entity_1",
        content=(
            "John is connected "
            "with Organization X"
        ),
        metadata={
            "type": "entity",
        },
    )


    store.add(
        key="entity_2",
        content=(
            "Alice works with "
            "Company Y"
        ),
        metadata={
            "type": "person",
        },
    )


    return Retriever(
        store
    )



def test_retrieve_single_keyword():

    retriever = create_retriever()


    results = retriever.retrieve(
        "John"
    )


    assert len(results) == 1


    assert (
        results[0]["metadata"]["type"]
        ==
        "entity"
    )



def test_retrieve_multiple_keywords():

    retriever = create_retriever()


    results = retriever.retrieve(
        "John connected"
    )


    assert len(results) == 1


    assert (
        "Organization X"
        in
        results[0]["content"]
    )



def test_retrieve_with_punctuation():

    retriever = create_retriever()


    results = retriever.retrieve(
        "John?"
    )


    assert len(results) == 1



def test_retrieve_no_results():

    retriever = create_retriever()


    results = retriever.retrieve(
        "Unknown person"
    )


    assert results == []



def test_retriever_metadata():

    retriever = create_retriever()


    metadata = retriever.metadata()


    assert (
        metadata["type"]
        ==
        "keyword_retriever"
    )


    assert (
        metadata["version"]
        ==
        "1.1"
    )
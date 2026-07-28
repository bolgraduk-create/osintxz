"""
Integration tests for AI Layer.

Checks complete flow:

AIAnalyzer
    ↓
RAGEngine
    ↓
Retriever
    ↓
KnowledgeStore
    ↓
AI Provider
"""


from app.ai.analysis.ai_analyzer import (
    AIAnalyzer,
)

from app.ai.base_ai import (
    BaseAI,
)

from app.ai.rag.rag_engine import (
    RAGEngine,
)


class MockAI(BaseAI):
    """
    Fake AI model for integration testing.
    """


    def __init__(self):
        super().__init__(
            model_name="integration-test-model"
        )


    def generate(
        self,
        prompt: str,
        **kwargs,
    ):
        return {
            "answer": "integration success",
            "prompt": prompt,
        }



def test_full_ai_pipeline():

    # ----------------------------
    # Create AI layer
    # ----------------------------

    ai = MockAI()


    rag_engine = RAGEngine(
        ai
    )


    analyzer = AIAnalyzer(
        rag_engine
    )


    # ----------------------------
    # Add knowledge
    # ----------------------------

    rag_engine.add_knowledge(
        key="entity_1",
        content=(
            "John is connected "
            "with Organization X"
        ),
        metadata={
            "type": "entity"
        },
    )

    print(
        "STORE:",
        rag_engine.knowledge_store.search(
            "John"
        )
    )

    print(
        "RETRIEVER:",
        rag_engine.retriever.retrieve(
            "John connected"
        )
    )

    # ----------------------------
    # Execute analysis
    # ----------------------------

    result = analyzer.ask(
        "John connected"
    )


    # ----------------------------
    # Validate
    # ----------------------------

    assert (
        result["response"]["answer"]
        ==
        "integration success"
    )


    assert len(
        result["context"]
    ) == 1


    assert (
        "John"
        in
        result["context"][0]["content"]
    )



def test_ai_metadata():

    ai = MockAI()


    rag_engine = RAGEngine(
        ai
    )


    analyzer = AIAnalyzer(
        rag_engine
    )


    metadata = analyzer.metadata()


    assert (
        metadata["type"]
        ==
        "ai_analyzer"
    )
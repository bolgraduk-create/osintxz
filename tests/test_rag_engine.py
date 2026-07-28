from app.ai.rag.rag_engine import RAGEngine
from app.ai.base_ai import BaseAI


class MockAI(BaseAI):

    def __init__(self):
        super().__init__(
            model_name="test-model"
        )


    def generate(
        self,
        prompt: str,
        **kwargs
    ):
        return "AI RESPONSE"



def test_rag_engine():

    ai = MockAI()

    engine = RAGEngine(
        ai
    )


    engine.add_knowledge(
        "test",
        "John works with Organization X"
    )


    result = engine.query(
        "John"
    )


    assert result["response"] == "AI RESPONSE"


    assert len(
        result["context"]
    ) == 1
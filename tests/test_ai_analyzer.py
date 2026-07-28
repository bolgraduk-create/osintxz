"""
Tests for AIAnalyzer.
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
    Mock AI provider for testing.
    """


    def __init__(self):
        super().__init__(
            model_name="test-model"
        )


    def generate(
        self,
        prompt: str,
        **kwargs,
    ):
        return "TEST AI RESPONSE"



def test_ai_analyzer():

    ai = MockAI()


    rag_engine = RAGEngine(
        ai
    )


    analyzer = AIAnalyzer(
        rag_engine
    )


    result = analyzer.analyze(
        {
            "type": "test",
            "content": "Investigation data",
        }
    )


    assert result["response"] == (
        "TEST AI RESPONSE"
    )


def test_ai_analyzer_case():

    ai = MockAI()


    rag_engine = RAGEngine(
        ai
    )


    analyzer = AIAnalyzer(
        rag_engine
    )


    result = analyzer.analyze_case(
        {
            "id": 1,
            "name": "Test Case",
        }
    )


    assert result["response"] == (
        "TEST AI RESPONSE"
    )


def test_ai_analyzer_question():

    ai = MockAI()


    rag_engine = RAGEngine(
        ai
    )


    analyzer = AIAnalyzer(
        rag_engine
    )


    result = analyzer.ask(
        "Who is connected with entity X?"
    )


    assert result["response"] == (
        "TEST AI RESPONSE"
    )
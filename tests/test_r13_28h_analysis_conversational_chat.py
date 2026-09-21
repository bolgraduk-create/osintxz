from __future__ import annotations

from pathlib import Path

from app.application.analysis_chat_service import AnalysisChatService


def test_chat_prompt_preserves_multi_turn_context_and_case_boundaries():
    prompt = AnalysisChatService._prompt(
        message="And what does that mean for the timeline?",
        history=[
            {"role": "user", "text": "What happened first?"},
            {"role": "assistant", "text": "Event A appears before Event B [R1]."},
        ],
        case_context="[R1] Timeline source text",
        has_case_context=True,
        analysis_context={
            "summary": "Earlier structured summary [R1].",
            "conclusions": [],
            "runConfig": {"provider": "openai", "model": "gpt-5.6", "mode": "standard"},
        },
        scope_type="case",
        focus_entity_label="",
    )

    assert "RECENT CONVERSATION" in prompt
    assert "USER: What happened first?" in prompt
    assert "ASSISTANT: Event A appears before Event B [previous-turn source]." in prompt
    assert "CURRENT USER MESSAGE" in prompt
    assert "And what does that mean for the timeline?" in prompt
    assert "[R1] Timeline source text" in prompt
    assert "CURRENT STRUCTURED ANALYSIS" in prompt
    assert "Earlier structured summary [structured-analysis source]." in prompt
    assert "Never invent case-specific facts" in prompt
    assert "AI output is analysis and assistance, not Evidence." in prompt
    assert "R# references are turn-local." in prompt


def test_chat_retrieval_query_uses_recent_user_context_for_followups():
    query = AnalysisChatService._retrieval_question(
        message="Where did he go next?",
        history=[
            {"role": "user", "text": "Tell me about Example Person."},
            {"role": "assistant", "text": "The case contains several records."},
            {"role": "user", "text": "What happened on Monday?"},
        ],
        scope_type="person",
        focus_entity_label="Example Person",
    )

    assert "Focus person: Example Person" in query
    assert "Tell me about Example Person." in query
    assert "What happened on Monday?" in query
    assert "Where did he go next?" in query


def test_chat_history_is_bounded_and_keeps_roles():
    rows = [
        {"role": "user", "text": f"question {index}"}
        if index % 2 == 0
        else {"role": "assistant", "text": f"answer {index}"}
        for index in range(40)
    ]

    history = AnalysisChatService._history(rows)

    assert len(history) <= 16
    assert history[-1]["role"] == "assistant"
    assert "answer 39" in history[-1]["text"]


def test_service_container_wires_real_chat_service_to_existing_rag_and_ai():
    source = Path("app/core/service_container.py").read_text(encoding="utf-8")

    assert "AnalysisChatService" in source
    assert "self.analysis_chat_service" in source
    assert "self.investigation_rag_retrieval_service" in source
    assert "self.investigation_rag_context_builder" in source
    assert "self.ai_execution_service" in source
    assert "self.investigation_rag_grounded_citation_service" in source
    assert "prompt_manager=(" in source
    assert "self.prompt_manager" in source


def test_chat_worker_uses_selected_real_provider_model_and_persists_turn():
    source = Path(
        "app/interface/desktop/workers/analysis_chat_worker.py"
    ).read_text(encoding="utf-8")

    assert "ServiceContainer(" in source
    assert "ai_provider_name=self.provider_name or None" in source
    assert "ai_model_name=self.model or None" in source
    assert "ai_reasoning_effort=self.reasoning_effort or None" in source
    assert "analysis_context=self.analysis_context" in source
    assert "container.analysis_chat_service.reply(" in source
    assert "AnalysisChatHistoryService" in source
    assert "history.save_turn(" in source
    assert "history_session.commit()" in source
    assert "estimate_openai_cost(usage)" in source


def test_analysis_bridge_exposes_real_multi_turn_chat_contract():
    source = Path(
        "app/interface/desktop/bridges/analysis_bridge.py"
    ).read_text(encoding="utf-8")

    for expected in (
        "def chatMessages(",
        "def chatBusy(",
        "def sendMessage(",
        "def newChat(",
        "def openChatSource(",
        "AnalysisChatWorker(",
        "AnalysisChatHistoryService",
        "def _load_chat_history(",
        "previous_conversation",
    ):
        assert expected in source


def test_analysis_qml_renders_conversation_and_sends_followup_messages():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    for expected in (
        '{key:"assistant", label:"Assistant"',
        'property string activeView: "assistant"',
        'id: chatFlick',
        'text: "Investigation Assistant"',
        'text: "Ask anything about this investigation"',
        "root.chatMessages",
        "Text.MarkdownText",
        "analysisBridge.sendMessage(",
        "analysisBridge.openChatSource(",
        "analysisBridge.newChat()",
        "root.sendChatNow()",
        'id: sendButton',
        '"Send"',
        "Qt.ShiftModifier",
    ):
        assert expected in qml


def test_structured_analysis_remains_separate_from_chat():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    assert 'id: runButton' in qml
    assert '"Run Analysis"' in qml
    assert "root.runAnalysisNow()" in qml
    assert 'objectName: "analysisModeRow"' in qml
    assert '"Quick"' not in qml or "root.modes()" in qml
    assert 'title: "AI Summary"' in qml
    assert 'title: "Analysis Pipeline"' in qml


def test_chat_history_uses_existing_ai_analysis_table_without_new_schema():
    source = Path(
        "app/application/analysis_chat_history_service.py"
    ).read_text(encoding="utf-8")

    assert 'CHAT_MARKER = "analysis_workspace_chat_turn"' in source
    assert "AIAnalysisRepository" in source
    assert "AnalysisType.OTHER" in source
    assert "sessionId" in source
    assert "sanitize_sensitive_value" in source


def test_chat_prompt_uses_central_prompt_manager_contract():
    source = Path(
        "app/application/analysis_chat_service.py"
    ).read_text(encoding="utf-8")

    assert "PromptManager" in source
    assert 'ANALYSIS_CHAT_PROMPT_NAME = "analysis_conversational_chat"' in source
    assert "self.prompt_manager.register_prompt(" in source
    assert "prompt_manager.render_prompt(" in source

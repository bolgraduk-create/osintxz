from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai.providers.openai_provider import OpenAIProvider
from app.application.analysis_run_profile import (
    analysis_workspace_catalog,
    estimate_openai_cost,
    generation_kwargs_for_profile,
    normalize_analysis_mode,
)
from app.interface.desktop.workers.investigation_analysis_worker import (
    InvestigationAnalysisWorker,
)
from app.security.sensitive_content import (
    REDACTED,
    sanitize_sensitive_text,
    sanitize_sensitive_value,
)


def test_analysis_modes_have_real_ai_workflow_counts():
    quick = normalize_analysis_mode("quick")
    standard = normalize_analysis_mode("standard")
    deep = normalize_analysis_mode("deep")

    assert quick.ai_request_count == 1
    assert quick.conclusion_kinds == ()

    assert standard.ai_request_count == 3
    assert [item.value for item in standard.conclusion_kinds] == [
        "hypotheses",
        "contradictions",
    ]

    assert deep.ai_request_count == 4
    assert [item.value for item in deep.conclusion_kinds] == [
        "hypotheses",
        "contradictions",
        "next_steps",
    ]


def test_openai_generation_profile_uses_selected_model_reasoning_and_budget():
    kwargs = generation_kwargs_for_profile(
        provider="openai",
        mode="deep",
        model="gpt-5.6-terra",
        reasoning_effort="xhigh",
    )

    assert kwargs["model"] == "gpt-5.6-terra"
    assert kwargs["reasoning"] == {"effort": "xhigh"}
    assert kwargs["max_output_tokens"] == 4200


def test_non_openai_profile_does_not_inject_openai_kwargs():
    assert generation_kwargs_for_profile(
        provider="ollama",
        mode="deep",
        model="gpt-5.6",
        reasoning_effort="high",
    ) == {}


def test_workspace_catalog_exposes_three_gpt_56_tiers():
    catalog = analysis_workspace_catalog()

    assert [item["key"] for item in catalog["modes"]] == [
        "quick",
        "standard",
        "deep",
    ]
    assert [item["id"] for item in catalog["models"]] == [
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "gpt-5.6",
    ]
    assert "max" in catalog["reasoningEfforts"]


def test_cost_estimator_uses_actual_reported_usage():
    usage = {
        "events": [
            {
                "model": "gpt-5.6-terra",
                "inputTokens": 1000,
                "cachedInputTokens": 200,
                "outputTokens": 500,
                "reasoningTokens": 100,
                "totalTokens": 1500,
            }
        ]
    }

    cost = estimate_openai_cost(usage)

    # 800 uncached * $2/M + 200 cached * $0.20/M + 500 * $12/M.
    assert cost["estimatedUsd"] == pytest.approx(0.00764)
    assert cost["pricedRequests"] == 1
    assert cost["unpricedRequests"] == 0
    assert cost["approximate"] is True


def test_cost_estimator_accepts_snapshot_model_ids():
    usage = {
        "events": [
            {
                "model": "gpt-5.6-luna-2026-09-01",
                "inputTokens": 1000,
                "cachedInputTokens": 0,
                "outputTokens": 1000,
            }
        ]
    }

    cost = estimate_openai_cost(usage)
    assert cost["pricedRequests"] == 1
    assert cost["estimatedUsd"] == pytest.approx(0.0014)


class _Usage:
    input_tokens = 120
    output_tokens = 40
    total_tokens = 160
    input_tokens_details = SimpleNamespace(cached_tokens=20)
    output_tokens_details = SimpleNamespace(reasoning_tokens=12)


class _FakeResponses:
    def create(self, **kwargs):
        return SimpleNamespace(
            output_text="analysis",
            model="gpt-5.6-terra",
            usage=_Usage(),
        )


class _FakeClient:
    responses = _FakeResponses()


def test_openai_provider_accumulates_responses_usage_without_changing_text_contract():
    provider = OpenAIProvider(
        model_name="gpt-5.6",
        api_key="sk-test",
        store_responses=False,
    )
    provider.client = _FakeClient()
    provider.connected = True

    assert provider.generate(
        "test",
        model="gpt-5.6-terra",
        reasoning={"effort": "medium"},
    ) == "analysis"

    usage = provider.usage_snapshot()
    assert usage["requests"] == 1
    assert usage["inputTokens"] == 120
    assert usage["cachedInputTokens"] == 20
    assert usage["outputTokens"] == 40
    assert usage["reasoningTokens"] == 12
    assert usage["events"][0]["model"] == "gpt-5.6-terra"


def _analysis_result_with_source_text():
    source = SimpleNamespace(
        reference_id="R1",
        title="Observed source",
        object_type="evidence",
        object_id="11111111-1111-1111-1111-111111111111",
        final_score=0.9,
        status="full",
        matched_methods=("lexical",),
        text="Direct source material from the investigation.",
    )
    rag_context = SimpleNamespace(
        included_sources=(source,),
    )
    rag_summary = SimpleNamespace(
        summary="Summary [R1]",
        source_references=("R1",),
        model_info={"model": "gpt-5.6"},
    )
    rag = SimpleNamespace(
        summary=rag_summary,
        conclusions=None,
        context=rag_context,
        summary_citations=SimpleNamespace(
            valid_count=1,
            invalid_citations=(),
            unresolved_citations=(),
        ),
    )
    unified = SimpleNamespace(
        available_sections=("rag",),
        generated_at=SimpleNamespace(
            isoformat=lambda: "2026-09-21T18:00:00+00:00"
        ),
        rag=rag,
    )

    return SimpleNamespace(
        case_id="00000000-0000-0000-0000-000000000001",
        status=SimpleNamespace(value="success"),
        duration_seconds=1.0,
        warnings=(),
        stage_results=(),
        unified_context=unified,
        successful_stage_count=lambda: 0,
        failed_stage_count=lambda: 0,
        skipped_stage_count=lambda: 0,
        cancelled_stage_count=lambda: 0,
    )


def test_worker_separates_source_backed_facts_from_ai_conclusions():
    manager = SimpleNamespace(
        metadata=lambda: {"type": "openai"},
        info=lambda: {"model": "gpt-5.6"},
    )
    snapshot = InvestigationAnalysisWorker._snapshot_result(
        result=_analysis_result_with_source_text(),
        container=SimpleNamespace(ai_manager=manager),
        question="question",
        run_config={
            "mode": "quick",
            "modeLabel": "Quick",
            "model": "gpt-5.6-luna",
            "reasoningEffort": "low",
        },
        scope={
            "type": "person",
            "entityId": "person-id",
            "label": "Example Person",
        },
    )

    assert snapshot["facts"][0]["reference"] == "R1"
    assert snapshot["facts"][0]["verifiedFact"] is False
    assert "Direct source material" in snapshot["facts"][0]["text"]
    assert snapshot["conclusions"] == []
    assert snapshot["scope"]["type"] == "person"
    assert snapshot["modelInfo"]["model"] == "gpt-5.6-luna"


def test_orchestrator_uses_mode_specific_conclusions_and_person_focus():
    source = Path(
        "app/application/investigation_analysis_orchestrator.py"
    ).read_text(encoding="utf-8")

    assert "normalize_analysis_mode(" in source
    assert "generation_kwargs_for_profile(" in source
    assert "if profile.conclusion_kinds:" in source
    assert "kinds=profile.conclusion_kinds" in source
    assert "ANALYSIS FOCUS: Person" in source
    assert '"focus_entity_id"' in source


def test_history_uses_ai_analysis_and_not_evidence():
    source = Path(
        "app/application/analysis_history_service.py"
    ).read_text(encoding="utf-8")

    assert "AIAnalysisRepository" in source
    assert "AnalysisType.OTHER" in source
    assert "metadata_json=" in source
    assert "Evidence" in source
    assert "EvidenceService" not in source
    assert "evidence_service" not in source


def test_worker_persists_history_in_separate_transaction_after_read_only_analysis():
    source = Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")

    assert "container.rollback()" in source
    assert "container.commit()" not in source
    assert "AnalysisHistoryService(history_session)" in source
    assert "history_session.commit()" in source
    assert "usage_snapshot()" in source
    assert "estimate_openai_cost(usage)" in source


def test_analysis_bridge_exposes_scope_history_and_source_navigation():
    source = Path(
        "app/interface/desktop/bridges/analysis_bridge.py"
    ).read_text(encoding="utf-8")

    assert "def prepareCase(" in source
    assert "EntityType.PERSON" in source
    assert "def openHistory(" in source
    assert "def openSource(" in source
    assert "AnalysisHistoryService" in source
    assert "desktop_bridge" in source


def test_analysis_qml_is_an_analytical_console_not_a_single_text_page():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    for expected in (
        'text: "ANALYSIS LAB"',
        'text: "AI Analysis"',
        'title: "Analysis Focus"',
        'title: "AI Summary"',
        'title: "Hypotheses"',
        'title: "Contradictions"',
        'title: "Next Investigation Steps"',
        'title: "RAG Sources"',
        'title: "Analysis Pipeline"',
        'title: "Analysis History"',
        '"Facts"',
        '"Hypotheses"',
        '"Contradictions"',
        '"Next Steps"',
        '"Sources"',
        '"Pipeline"',
        '"History"',
        "analysisBridge.runAnalysis(",
        "analysisBridge.openSource(",
        "analysisBridge.openHistory(",
        "API storage off",
        "OPENAI_API_KEY",
        "AI output is analysis, not Evidence.",
    ):
        assert expected in qml


def test_desktop_bootstrap_gives_analysis_bridge_source_navigation_access():
    source = Path(
        "app/interface/desktop/desktop_app.py"
    ).read_text(encoding="utf-8")

    assert "desktop_bridge=self.bridge" in source


def test_legacy_orchestrator_callers_default_to_deep_profile():
    source = Path(
        "app/application/investigation_analysis_orchestrator.py"
    ).read_text(encoding="utf-8")

    assert 'else "deep"' in source
    assert "Preserve the pre-R13.28c canonical behavior" in source


def test_rag_source_navigation_can_focus_exact_evidence_and_timeline_rows():
    analysis_bridge = Path(
        "app/interface/desktop/bridges/analysis_bridge.py"
    ).read_text(encoding="utf-8")
    desktop_bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")
    workspace_qml = Path(
        "app/interface/desktop/qml/pages/DataWorkspace.qml"
    ).read_text(encoding="utf-8")

    assert 'bridge.focusWorkspaceRecord(' in analysis_bridge
    assert '"timeline"' in analysis_bridge
    assert '"evidence"' in analysis_bridge
    assert "def focusWorkspaceRecord(" in desktop_bridge
    assert "def workspaceFocus(" in desktop_bridge
    assert "positionViewAtIndex(i, ListView.Center)" in workspace_qml
    assert "externallyFocused" in workspace_qml
    assert "Theme.accentSoft" in workspace_qml


def test_conclusion_workflows_receive_the_same_analyst_question():
    source = Path(
        "app/services/investigation_rag_conclusions_service.py"
    ).read_text(encoding="utf-8")

    assert "question=normalized_question" in source
    assert '"ANALYST QUESTION / FOCUS:\\n"' in source
    assert "question: str = \"\"" in source



def test_sensitive_analysis_sanitizer_preserves_osint_identifiers_but_redacts_secrets():
    ordinary = (
        "email=user@example.com domain=example.com "
        "sha256=0123456789abcdef0123456789abcdef"
    )
    ordinary_result = sanitize_sensitive_text(ordinary)
    assert ordinary_result.text == ordinary
    assert ordinary_result.redacted is False

    sensitive = (
        "password=SuperSecret123 "
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz "
        "user@example.com:LeakPassword42 "
        "example.com:alice:StealerSecret99 "
        "sk-abcdefghijklmnopqrstuvwx"
    )
    result = sanitize_sensitive_text(sensitive)

    assert result.redacted is True
    assert result.redaction_count >= 5
    assert "SuperSecret123" not in result.text
    assert "abcdefghijklmnopqrstuvwxyz" not in result.text
    assert "LeakPassword42" not in result.text
    assert "StealerSecret99" not in result.text
    assert "sk-abcdefghijklmnopqrstuvwx" not in result.text
    assert REDACTED in result.text
    assert "user@example.com" in result.text
    assert "example.com:alice:" in result.text


def test_sensitive_analysis_sanitizer_redacts_private_keys_and_sensitive_mapping_keys():
    private_key = (
        "-----BEGIN PRIVATE KEY-----\n"
        "VERYSECRETKEYMATERIAL\n"
        "-----END PRIVATE KEY-----"
    )
    result = sanitize_sensitive_text(private_key)
    assert "VERYSECRETKEYMATERIAL" not in result.text
    assert "PRIVATE KEY REDACTED" in result.text

    mapping = sanitize_sensitive_value(
        {
            "api_key": "plain-value-that-has-no-prefix",
            "nested": {
                "access_token": "another-plain-value",
                "email": "user@example.com",
            },
            "inputTokens": 123,
        }
    )
    assert mapping["api_key"] == REDACTED
    assert mapping["nested"]["access_token"] == REDACTED
    assert mapping["nested"]["email"] == "user@example.com"
    assert mapping["inputTokens"] == 123


def test_worker_redacts_sensitive_material_before_facts_sources_and_history_snapshot():
    result = _analysis_result_with_source_text()
    result.unified_context.rag.summary.summary = (
        "Observed password=ModelEchoSecret [R1]"
    )
    source = result.unified_context.rag.context.included_sources[0]
    source.title = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz"
    source.text = (
        "user@example.com:LeakPassword42 "
        "example.com:alice:StealerSecret99"
    )

    manager = SimpleNamespace(
        metadata=lambda: {"type": "openai"},
        info=lambda: {"model": "gpt-5.6"},
    )
    snapshot = InvestigationAnalysisWorker._snapshot_result(
        result=result,
        container=SimpleNamespace(ai_manager=manager),
        question="password=QuestionSecret",
    )

    serialized = repr(snapshot)
    for secret in (
        "ModelEchoSecret",
        "abcdefghijklmnopqrstuvwxyz",
        "LeakPassword42",
        "StealerSecret99",
        "QuestionSecret",
    ):
        assert secret not in serialized

    assert snapshot["redactions"]["active"] is True
    assert snapshot["redactions"]["count"] >= 5
    assert REDACTED in snapshot["summary"]
    assert REDACTED in snapshot["facts"][0]["text"]
    assert REDACTED in snapshot["sources"][0]["title"]


def test_ai_prompt_layers_sanitize_context_before_remote_generation():
    summary_service = Path(
        "app/services/investigation_rag_prompt_service.py"
    ).read_text(encoding="utf-8")
    conclusions_service = Path(
        "app/services/investigation_rag_conclusions_service.py"
    ).read_text(encoding="utf-8")
    history_service = Path(
        "app/application/analysis_history_service.py"
    ).read_text(encoding="utf-8")

    assert "sanitize_sensitive_text(" in summary_service
    assert '"question": safe_question.text' in summary_service
    assert "safe_context.text" in summary_service

    assert "sanitized_text(" in conclusions_service
    assert 'f"{safe_context}"' in conclusions_service

    assert "sanitize_sensitive_value(" in history_service
    assert "safe_sanitized_snapshot" not in history_service


def test_analysis_ui_surfaces_when_secret_material_was_redacted():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    assert "root.run.redactions" in qml
    assert "credential/secret fragment(s) were redacted" in qml

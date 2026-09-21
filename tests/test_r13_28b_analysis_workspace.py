from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.interface.desktop.workers.investigation_analysis_worker import (
    InvestigationAnalysisWorker,
)


class _Value:
    def __init__(self, value: str):
        self.value = value


class _AnalysisResult:
    def __init__(self):
        self.case_id = "00000000-0000-0000-0000-000000000001"
        self.status = _Value("success")
        self.duration_seconds = 4.2
        self.warnings = ()
        self.stage_results = (
            SimpleNamespace(
                stage=_Value("rag"),
                status=_Value("success"),
                duration_seconds=1.2,
                warnings=(),
                error=None,
            ),
        )

        context_source = SimpleNamespace(
            reference_id="R1",
            title="Evidence one",
            object_type="evidence",
            object_id="11111111-1111-1111-1111-111111111111",
            final_score=0.93,
            status="full",
            matched_methods=("lexical", "semantic"),
        )
        rag_context = SimpleNamespace(
            included_sources=(context_source,),
        )
        rag_summary = SimpleNamespace(
            summary="Summary [R1]",
            source_references=("R1",),
            model_info={"model": "gpt-5.6"},
        )
        conclusion = SimpleNamespace(
            kind=_Value("hypotheses"),
            text="Hypothesis [R1]",
            source_references=("R1",),
            workflow_name="hypothesis_generation",
        )
        rag_conclusions = SimpleNamespace(
            conclusions=(conclusion,),
            model_info={"model": "gpt-5.6"},
        )
        citation_validation = SimpleNamespace(
            valid_count=1,
            invalid_citations=(),
            unresolved_citations=(),
        )
        rag = SimpleNamespace(
            summary=rag_summary,
            conclusions=rag_conclusions,
            context=rag_context,
            summary_citations=citation_validation,
        )
        self.unified_context = SimpleNamespace(
            available_sections=("graph", "temporal", "rag"),
            generated_at=SimpleNamespace(
                isoformat=lambda: "2026-09-21T12:00:00+00:00"
            ),
            rag=rag,
        )

    def successful_stage_count(self):
        return 1

    def failed_stage_count(self):
        return 0

    def skipped_stage_count(self):
        return 0

    def cancelled_stage_count(self):
        return 0


class _Manager:
    def metadata(self):
        return {
            "type": "openai",
            "model": "gpt-5.6",
            "configured": True,
            "api": "responses",
        }

    def info(self):
        return {
            "provider": "openai",
            "model": "gpt-5.6",
        }


def test_worker_serializes_structured_ai_analysis_workspace_payload():
    snapshot = InvestigationAnalysisWorker._snapshot_result(
        result=_AnalysisResult(),
        container=SimpleNamespace(ai_manager=_Manager()),
        question="What matters?",
    )

    assert snapshot["status"] == "success"
    assert snapshot["summary"] == "Summary [R1]"
    assert snapshot["summarySourceReferences"] == ["R1"]
    assert snapshot["conclusions"][0]["kind"] == "hypotheses"
    assert snapshot["conclusions"][0]["text"] == "Hypothesis [R1]"
    assert snapshot["sources"][0]["reference"] == "R1"
    assert snapshot["sources"][0]["title"] == "Evidence one"
    assert snapshot["citationSummary"]["valid"] == 1
    assert snapshot["modelInfo"]["model"] == "gpt-5.6"
    assert snapshot["provider"]["type"] == "openai"
    assert "not Evidence" in snapshot["notice"]


def test_analysis_worker_uses_canonical_runner_and_read_only_transaction():
    source = Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")

    assert "container.investigation_analysis_runner.run(" in source
    assert "progress_callback=self._on_progress" in source
    assert "container.rollback()" in source
    assert "container.commit()" not in source
    assert "ServiceContainer(session)" in source


def test_analysis_bridge_never_exposes_openai_api_key_field():
    source = Path(
        "app/interface/desktop/bridges/analysis_bridge.py"
    ).read_text(encoding="utf-8")

    assert "openai_api_key" in source
    assert "get_secret_value()" in source
    assert '"configured": configured' in source

    # Secret may only be inspected to produce the configured boolean.
    assert '"apiKey"' not in source
    assert '"api_key"' not in source
    assert '"key":' not in source


def test_analysis_bridge_runs_worker_in_qthread():
    source = Path(
        "app/interface/desktop/bridges/analysis_bridge.py"
    ).read_text(encoding="utf-8")

    assert "QThread(self)" in source
    assert "InvestigationAnalysisWorker(" in source
    assert "worker.moveToThread(thread)" in source
    assert "worker.progress.connect(self._on_progress)" in source
    assert "worker.succeeded.connect(self._on_succeeded)" in source
    assert "worker.failed.connect(self._on_failed)" in source


def test_analysis_page_has_structured_pipeline_sections():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    for expected in (
        'text: "AI Analysis"',
        'title: "Analysis Focus"',
        'title: "AI Summary"',
        'title: "RAG Sources"',
        'title: "Analysis Pipeline"',
        "root.conclusions",
        "root.sources",
        "root.stages",
        "analysisBridge.runAnalysis",
        "OPENAI_API_KEY",
        "API storage off",
    ):
        assert expected in qml


def test_analysis_workspace_is_registered_in_shell():
    main = Path(
        "app/interface/desktop/qml/Main.qml"
    ).read_text(encoding="utf-8")
    sidebar = Path(
        "app/interface/desktop/qml/components/Sidebar.qml"
    ).read_text(encoding="utf-8")
    desktop_app = Path(
        "app/interface/desktop/desktop_app.py"
    ).read_text(encoding="utf-8")
    desktop_bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")

    assert 'case "analysis": return "pages/Analysis.qml"' in main
    assert '{key:"analysis", label:"Analysis", icon:"chart.svg"}' in sidebar
    assert '"analysisBridge"' in desktop_app
    assert "AnalysisBridge" in desktop_app
    assert '"analysis"' in desktop_bridge


def test_analysis_page_does_not_claim_ai_output_is_verified_evidence():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")
    worker = Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")

    assert "AI output is analysis, not Evidence." in qml
    assert "not Evidence" in worker
    assert "independently verified fact" in worker


def test_openai_foundation_is_present_under_analysis_workspace_branch():
    provider = Path(
        "app/ai/providers/openai_provider.py"
    ).read_text(encoding="utf-8")
    config = Path(
        "app/core/config.py"
    ).read_text(encoding="utf-8")

    assert "self.client.responses.create" in provider
    assert '"store": self.store_responses' in provider
    assert 'openai_model: str = "gpt-5.6"' in config
    assert "openai_api_key: SecretStr | None = None" in config

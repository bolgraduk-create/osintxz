"""Block 10.9 Investigation Engine contract audit.

Read-only development gate. It verifies the active Investigation Engine
contracts and reports known architectural gaps without mutating application
state or the database.
"""
from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.application.investigation_analysis_contracts import (
    CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER,
    INVESTIGATION_ANALYSIS_STAGE_DEPENDENCIES,
    InvestigationAnalysisStage,
)
from app.investigation.search_query import InvestigationSearchQuery, SearchMethod
from app.investigation.search_result import (
    InvestigationSearchHit,
    InvestigationSearchResponse,
    SearchMatchReason,
    SearchScores,
)
from app.models.search_index import SearchObjectType
from app.services.investigation_rag_retrieval_service import InvestigationRAGRetrievalService


@dataclass(frozen=True, slots=True)
class AuditFinding:
    level: str
    code: str
    message: str


class _FakeUnifiedSearchService:
    def __init__(self, response: InvestigationSearchResponse) -> None:
        self.response = response
        self.last_query: InvestigationSearchQuery | None = None

    def search(self, query: InvestigationSearchQuery) -> InvestigationSearchResponse:
        self.last_query = query
        return self.response


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _check_stage_contract(findings: list[AuditFinding]) -> None:
    order = CANONICAL_INVESTIGATION_ANALYSIS_STAGE_ORDER
    if len(order) != len(set(order)):
        findings.append(AuditFinding("FAIL", "ANALYSIS_STAGE_DUPLICATE", "Canonical analysis stage order contains duplicates."))
        return

    positions = {stage: index for index, stage in enumerate(order)}
    for stage, dependencies in INVESTIGATION_ANALYSIS_STAGE_DEPENDENCIES.items():
        if stage not in positions:
            findings.append(AuditFinding("FAIL", "ANALYSIS_DEPENDENCY_UNKNOWN_STAGE", f"Dependency map references non-canonical stage {stage!r}."))
            continue
        for dependency in dependencies:
            if dependency not in positions:
                findings.append(AuditFinding("FAIL", "ANALYSIS_DEPENDENCY_UNKNOWN", f"{stage.value} depends on unknown stage {dependency!r}."))
            elif positions[dependency] >= positions[stage]:
                findings.append(AuditFinding("FAIL", "ANALYSIS_DEPENDENCY_ORDER", f"{stage.value} depends on {dependency.value}, but dependency does not precede it."))

    findings.append(AuditFinding("PASS", "ANALYSIS_STAGE_CONTRACT", f"Canonical analysis stage order is valid ({len(order)} stages)."))


def _check_search_contract(findings: list[AuditFinding]) -> None:
    expected_methods = {"auto", "structured", "lexical", "fuzzy", "semantic", "image"}
    actual_methods = {item.value for item in SearchMethod}
    if actual_methods != expected_methods:
        findings.append(AuditFinding("FAIL", "SEARCH_METHOD_VOCABULARY", f"SearchMethod vocabulary differs: {sorted(actual_methods)}"))
    else:
        findings.append(AuditFinding("PASS", "SEARCH_METHOD_VOCABULARY", "Unified Search method vocabulary is stable."))

    expected_object_types = {"message", "document", "evidence", "entity", "artifact", "report", "note"}
    actual_object_types = {item.value for item in SearchObjectType}
    if actual_object_types != expected_object_types:
        findings.append(AuditFinding("FAIL", "SEARCH_OBJECT_TYPE_VOCABULARY", f"SearchObjectType vocabulary differs: {sorted(actual_object_types)}"))
    else:
        findings.append(AuditFinding("PASS", "SEARCH_OBJECT_TYPE_VOCABULARY", "Search object-type vocabulary is canonical and lowercase."))

    case_id = uuid4()
    object_id = uuid4()
    hit = InvestigationSearchHit(
        object_id=object_id,
        object_type="ENTITY",
        case_id=case_id,
        scores=SearchScores(structured=1.0, final=0.9),
        matched_methods=[SearchMethod.STRUCTURED],
    )
    if hit.identity_key != (case_id, "entity", object_id):
        findings.append(AuditFinding("FAIL", "SEARCH_HIT_IDENTITY", "InvestigationSearchHit identity normalization is inconsistent."))
    else:
        findings.append(AuditFinding("PASS", "SEARCH_HIT_IDENTITY", "Search hit identity is case + object_type + object_id."))


def _check_rag_bridge(findings: list[AuditFinding]) -> None:
    case_id = uuid4()
    object_id = uuid4()
    source_object = object()
    query = InvestigationSearchQuery(query="phone", case_id=case_id, limit=5, candidate_limit=10)
    hit = InvestigationSearchHit(
        object_id=object_id,
        object_type="entity",
        case_id=case_id,
        title="PHONE",
        snippet="+380671234567",
        scores=SearchScores(lexical=0.8, final=0.9),
        matched_methods=[SearchMethod.LEXICAL],
        reasons=[SearchMatchReason(reason="exact value", method=SearchMethod.LEXICAL, score=0.8)],
        source=source_object,
        metadata={"entity_type": "phone"},
    )
    response = InvestigationSearchResponse(
        query=query,
        hits=[hit],
        candidate_count=1,
        total_matches=1,
    )
    fake = _FakeUnifiedSearchService(response)
    service = InvestigationRAGRetrievalService(unified_search_service=fake)  # type: ignore[arg-type]
    result = service.retrieve_query(query)
    source = result.sources[0]

    preserved = (
        source.object_id == object_id
        and source.object_type == "entity"
        and source.case_id == case_id
        and source.source is source_object
        and source.metadata.get("entity_type") == "phone"
        and source.matched_methods == ("lexical",)
    )
    if not preserved:
        findings.append(AuditFinding("FAIL", "RAG_IDENTITY_PROVENANCE", "RAG retrieval loses SearchHit identity/provenance."))
    else:
        findings.append(AuditFinding("PASS", "RAG_IDENTITY_PROVENANCE", "RAG retrieval preserves SearchHit identity, source and provenance."))


def _check_composition_gaps(findings: list[AuditFinding]) -> None:
    root = _project_root()
    container_path = root / "app" / "core" / "service_container.py"
    text = container_path.read_text(encoding="utf-8")

    registration_anchor = "self.unified_search_service ="
    start = text.find(registration_anchor)
    window = text[start:start + 2500] if start >= 0 else ""
    has_structured = "structured" in window.casefold() and "retriever" in window.casefold()
    if not has_structured:
        findings.append(AuditFinding(
            "WARN",
            "STRUCTURED_RETRIEVER_MISSING",
            "SearchMethod.STRUCTURED exists, but the active ServiceContainer does not register a structured retriever. Direct typed Entity/Evidence queries therefore have no dedicated retrieval path yet.",
        ))
    else:
        findings.append(AuditFinding("PASS", "STRUCTURED_RETRIEVER_REGISTERED", "Active ServiceContainer registers structured retrieval."))

    legacy_paths = [
        root / "app" / "investigation" / "context.py",
        root / "app" / "investigation" / "state.py",
        root / "app" / "investigation" / "stages.py",
        root / "app" / "investigation" / "result.py",
        root / "app" / "pipelines" / "investigation_pipeline.py",
        root / "app" / "services" / "investigation_pipeline.py",
        root / "app" / "services" / "investigation_runner.py",
        root / "app" / "services" / "investigation_application_service.py",
    ]
    present = [str(path.relative_to(root)) for path in legacy_paths if path.exists()]
    if present:
        findings.append(AuditFinding(
            "WARN",
            "LEGACY_INVESTIGATION_STACK_PRESENT",
            "Legacy/parallel Investigation scaffolding remains present and must not become a dependency of new Engine work: " + ", ".join(present),
        ))

    old_runner = root / "app" / "services" / "investigation_runner.py"
    old_pipeline = root / "app" / "pipelines" / "investigation_pipeline.py"
    if old_runner.exists() and old_pipeline.exists():
        runner_text = old_runner.read_text(encoding="utf-8")
        pipeline_text = old_pipeline.read_text(encoding="utf-8")
        if "self.pipeline.run(" in runner_text and "def run(" not in pipeline_text:
            findings.append(AuditFinding(
                "WARN",
                "LEGACY_RUNNER_API_MISMATCH",
                "Legacy InvestigationRunner calls pipeline.run(), while its imported legacy pipeline exposes process_existing_case()/process_collected_items(). This path is not the canonical desktop analysis path.",
            ))


def run_audit() -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    _check_stage_contract(findings)
    _check_search_contract(findings)
    _check_rag_bridge(findings)
    _check_composition_gaps(findings)
    return findings


def main() -> int:
    print("======================================")
    print("OSINTXZ INVESTIGATION CONTRACT AUDIT")
    print("======================================")
    findings = run_audit()
    for item in findings:
        print(f"[{item.level}] {item.code}: {item.message}")

    failures = [item for item in findings if item.level == "FAIL"]
    warnings = [item for item in findings if item.level == "WARN"]
    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} hard contract violation(s), {len(warnings)} warning(s))")
        return 1
    print(f"RESULT: PASS ({len(warnings)} known architectural warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

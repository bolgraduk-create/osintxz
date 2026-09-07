"""M028 golden investigation fixture and Stage 23 integration contract."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.investigation.search_query import (
    InvestigationSearchQuery,
    SearchMethod,
    StructuredSearchFilters,
)
from app.investigation.search_result import (
    InvestigationSearchHit,
    SearchMatchReason,
    SearchScores,
)
from app.models.entity import EntityType
from app.services.search_retriever import SearchRetriever, SearchRetrieverInfo
from app.services.structured_search_retriever import StructuredSearchRetriever
from app.services.unified_search_service import UnifiedSearchService
import importlib.util

_RUNTIME_PATH = Path(__file__).parent / "golden_investigation_runtime.py"
_RUNTIME_SPEC = importlib.util.spec_from_file_location("osintxz_golden_runtime", _RUNTIME_PATH)
assert _RUNTIME_SPEC is not None and _RUNTIME_SPEC.loader is not None
_RUNTIME_MODULE = importlib.util.module_from_spec(_RUNTIME_SPEC)
_RUNTIME_SPEC.loader.exec_module(_RUNTIME_MODULE)
build_golden_runtime = _RUNTIME_MODULE.build_golden_runtime


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "golden_investigation"


class DeterministicEntitySignalRetriever(SearchRetriever):
    """Offline deterministic signal used only by the golden integration fixture."""

    def __init__(self, *, method: SearchMethod, entities, source, score: float, priority: int):
        self._method = method
        self.entities = list(entities)
        self.source_record = source
        self.score = score
        self._info = SearchRetrieverInfo(
            name=f"golden-{method.value}",
            method=method,
            description=f"Deterministic {method.value} signal for M028 golden fixture.",
            priority=priority,
        )

    @property
    def method(self) -> SearchMethod:
        return self._method

    @property
    def info(self):
        return self._info

    def can_handle(self, query):
        return query.case_id is not None and query.has_text_query

    def retrieve(self, query):
        query_digits = "".join(ch for ch in query.query if ch.isdigit())
        hits = []
        for entity in self.entities:
            normalized = entity.normalized_value or ""
            value = entity.value or ""
            is_target = query_digits and query_digits == "".join(ch for ch in normalized if ch.isdigit())
            text_match = query.query.casefold() in value.casefold() or query.query.casefold() in normalized.casefold()
            if not (is_target or text_match):
                continue

            scores = SearchScores(final=self.score)
            setattr(scores, self.method.value, self.score)
            hits.append(
                InvestigationSearchHit(
                    object_id=entity.id,
                    object_type="entity",
                    case_id=entity.case_id,
                    title=f"{entity.entity_type.value}: {entity.value}",
                    snippet=entity.value,
                    scores=scores,
                    matched_methods=[self.method],
                    reasons=[
                        SearchMatchReason(
                            reason=f"Golden {self.method.value} signal matched canonical entity value.",
                            method=self.method,
                            score=self.score,
                            details={"normalized_value": entity.normalized_value},
                        )
                    ],
                    source=entity,
                    metadata={
                        "entity_type": entity.entity_type.value,
                        "normalized_value": entity.normalized_value,
                        "confidence": entity.confidence,
                        "source_id": str(self.source_record.id),
                        "checksum": self.source_record.checksum,
                    },
                )
            )
        return hits


def _load_expected():
    return json.loads((FIXTURE_ROOT / "expected.json").read_text(encoding="utf-8"))


def _import_fixture():
    runtime = build_golden_runtime()
    result = runtime.importer.import_export(runtime.case_id, FIXTURE_ROOT)
    return runtime, result


def test_golden_fixture_import_extraction_resolution_and_provenance_contract():
    expected = _load_expected()
    runtime, result = _import_fixture()

    assert result["items_imported"] == expected["items_imported"]
    assert result["identifiers_found"] == expected["identifiers_found"]
    assert result["identifiers_created"] == expected["identifiers_created"]
    assert result["identifiers_existing"] == expected["identifiers_existing"]
    assert result["identifier_provenance_evidence_created"] == expected["provenance_evidence_created"]
    assert result["identifier_evidence_links_created"] == expected["evidence_links_created"]

    actual = {}
    for entity in runtime.entities.entities.values():
        actual.setdefault(entity.entity_type.value, []).append(entity.normalized_value)
    for values in actual.values():
        values.sort()

    assert actual == expected["entities"]
    assert len(runtime.messages.messages) == expected["items_imported"]
    assert len(runtime.evidences.evidences) == expected["provenance_evidence_created"]
    assert len(runtime.links.links) == expected["evidence_links_created"]

    phone = next(
        entity for entity in runtime.entities.entities.values()
        if entity.entity_type == EntityType.PHONE
    )
    phone_support = sum(1 for (_, entity_id) in runtime.links.links if entity_id == phone.id)
    assert phone_support == 2


def test_golden_fixture_retrieve_fuse_rank_confidence_explain_unified_result():
    expected = _load_expected()
    runtime, _ = _import_fixture()
    entities = list(runtime.entities.entities.values())
    source = runtime.sources.sources[0]

    structured = StructuredSearchRetriever(
        entity_repository=runtime.entities,
        evidence_repository=runtime.evidence_repository,
    )
    retrievers = [
        structured,
        DeterministicEntitySignalRetriever(
            method=SearchMethod.LEXICAL,
            entities=entities,
            source=source,
            score=0.94,
            priority=60,
        ),
        DeterministicEntitySignalRetriever(
            method=SearchMethod.FUZZY,
            entities=entities,
            source=source,
            score=0.91,
            priority=70,
        ),
        DeterministicEntitySignalRetriever(
            method=SearchMethod.SEMANTIC,
            entities=entities,
            source=source,
            score=0.88,
            priority=80,
        ),
    ]

    query = InvestigationSearchQuery(
        query="1234 5678 9012 3452",
        case_id=runtime.case_id,
        object_types=("entity",),
        structured_filters=StructuredSearchFilters(entity_types=("bank_card",)),
        enable_query_expansion=False,
        enable_neural_reranking=False,
        limit=10,
    )

    response = UnifiedSearchService(retrievers=retrievers).search(query)

    assert response.returned_count == 1
    hit = response.hits[0]
    golden_search = expected["golden_search"]

    assert hit.case_id == runtime.case_id
    assert hit.object_type == "entity"
    assert hit.metadata["entity_type"] == golden_search["entity_type"]
    assert hit.metadata["normalized_value"] == golden_search["normalized_value"]
    assert {method.value for method in hit.matched_methods} == set(golden_search["required_methods"])

    assert hit.scores.structured == pytest.approx(1.0)
    assert hit.scores.lexical == pytest.approx(0.94)
    assert hit.scores.fuzzy == pytest.approx(0.91)
    assert hit.scores.semantic == pytest.approx(0.88)
    assert hit.scores.fusion is not None
    assert hit.scores.final > 0.0

    assert hit.scores.confidence is not None
    assert "evidence_confidence" in hit.metadata
    assert "search_explanation" in hit.metadata
    explanation = hit.metadata["search_explanation"]
    assert set(explanation["matched_methods"]) == set(golden_search["required_methods"])
    assert explanation["identity"]["object_id"] == str(hit.object_id)
    assert response.metadata["confidence_scoring"]["applied"] is True
    assert response.metadata["explainability"]["applied"] is True

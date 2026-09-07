# Block 10.9 — Investigation Engine Contract Audit

## Purpose

Freeze the active Investigation Engine boundaries before wiring the next
Retrieve → Fuse → Rank → Resolve block.

## Canonical active contracts

- Analysis request/result/stage contracts:
  `app/application/investigation_analysis_contracts.py`
- Analysis orchestration:
  `app/application/investigation_analysis_orchestrator.py`
- Search request:
  `app/investigation/search_query.py`
- Search hit/response:
  `app/investigation/search_result.py`
- Search orchestration:
  `app/services/unified_search_service.py`
- RAG retrieval bridge:
  `app/services/investigation_rag_retrieval_service.py`
- Unified analytical aggregation:
  `app/services/investigation_unified_analytical_context_service.py`

## Confirmed invariants

1. Search object identity is `(case_id, object_type, object_id)`.
2. Search object types use one lowercase vocabulary matching `SearchObjectType`.
3. Scores crossing Unified Search use the normalized 0.0–1.0 contract.
4. RAG retrieval does not rerank or reinterpret SearchHit identity/provenance.
5. Analysis stage dependencies must refer to canonical stages and precede their consumers.
6. New Investigation Engine work must use the active Application/Unified Search contracts, not legacy scaffolding.

## Known gaps intentionally not fixed in 10.9

### Structured retrieval is declared but not wired

`SearchMethod.STRUCTURED` exists, but the active `ServiceContainer` currently
registers lexical, fuzzy and composite-semantic retrievers only. Therefore a
query such as “return BANK_CARD entities” has no dedicated typed/structured
retrieval path. This is a target for the following integration block.

### Legacy/parallel Investigation scaffolding remains

Old context/state/stages/result and duplicate pipeline/application-service files
remain in the repository. They are not the canonical desktop analysis path.
One legacy runner also calls `pipeline.run()` although its imported legacy
pipeline does not expose that method. These files are retained for now to avoid
mixing cleanup/removal with the current integration work.

## Gate

Run:

```powershell
.\.venv\Scripts\python.exe .\tools\check_investigation_contracts.py
.\.venv\Scripts\python.exe -m pytest tests\test_investigation_engine_contract_audit.py -q -vv
```

Hard contract violations fail the gate. Known architectural debt is reported as
WARN so it can be handled in the planned integration/cleanup blocks.

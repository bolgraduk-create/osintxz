# Investigation Analysis — Definition of Done

Status: formal integration DoD
Roadmap block: 9.2
Prerequisite: Blocks 8.1–8.13 completed

## Mandatory criteria

| Criterion | Evidence / verification | Status |
|---|---|---|
| Mathematical core has no separate user window | Block 7 existing-UX integration test | PASS |
| Existing `Analyze` is the single user entry point | Block 7 routing test; legacy workspace/workflow calls = 0 | PASS |
| Unified Analytical Context aggregates only | Object-reuse / unified-context tests | PASS |
| Orchestrator owns order, dependencies, progress and failure isolation | Blocks 4, 6 and 8 functional tests | PASS |
| Ordinary Analyze performs no automatic Entity merge | DB/write safety regression | PASS |
| Analytical signals are not automatically persisted as facts | Transaction/write audit + service boundaries | PASS |
| RAG runs over Unified Search and retrieval occurs once | Block 5 call-count tests | PASS |
| Summary/conclusions use bounded context and provenance | Blocks 5.3–5.8 and 6.6 | PASS |
| Valid citation only proves source-reference resolution | Citation validation tests 5.5–5.7 | PASS |
| Non-fatal stage failure preserves other results | 4.10, 6.7, 8.10 | PASS |
| Ollama outage preserves mathematical results | 5.9 and 8.8 | PASS |
| Heavy layers run at most once per Analyze | 4.x, 5.x, 8.2 call-count tests | PASS |
| Full Analyze runs outside the UI thread | 6.1 and subsequent UI worker regressions | PASS |
| Multimodal executes conditionally for applicable evidence | 8.9 | PASS |
| Lean audit → code → functional → integration process followed | Development/test history | PASS |
| Closed mathematical blocks are not needlessly recomputed/retested | Reuse-focused integration approach | PASS |

## Critical Definition-of-Done criteria

### 1. Existing Analyze starts the orchestrator exactly once

Verified in Block 7 and Block 8 UI/controller integration.

Result: **PASS**

### 2. Graph, Temporal, Anomaly, Clustering and RAG all participate in one production run

Verified on a real PostgreSQL case. Clean production diagnostic returned success for:

- Case Validation;
- Entity Resolution;
- Evidence;
- Graph;
- Temporal;
- Anomaly;
- Clustering;
- Multimodal;
- RAG;
- Unified Context.

Result: **PASS**

### 3. Results reach the existing UI

Summary, hypotheses, contradictions, next steps, source references, citation status, warnings and partial-stage information were rendered in the existing AI Assistant / Case Workspace UI.

No separate mathematical-core window was created.

Result: **PASS**

### 4. No unexpected DB writes or duplicate AI/search execution

Verified runtime observations included:

```text
commit_calls: 0
write_flushes: 0
write_sql_count: 0
pending_new: 0
pending_dirty: 0
pending_deleted: 0
changed_table_count: 0
```

Legacy main Analyze AI/workflow calls were also verified at zero.

Result: **PASS**

### 5. Stable failure and concurrency behavior

Verified:

- partial result after forced stage failure;
- AI outage fallback;
- cooperative cancellation;
- duplicate-run protection;
- worker/thread cleanup;
- restart after cleanup;
- timeout guard for heavy stages;
- responsive UI event loop.

Result: **PASS**

### 6. Existing Case Workspace functionality survives integration

Regression checks confirmed the continued presence/routing of:

- workspace loading;
- refresh;
- Telegram import;
- file import;
- create Evidence;
- create Entity;
- add TimelineEvent;
- general investigation action dispatcher.

Result: **PASS**

## Open blockers

No integration blocker is currently identified by Blocks 8.1–8.13.

## Remaining Block 9 work

The integration itself satisfies the formal DoD. The remaining administrative/finalization work is:

1. safely organize `.bak` files after successful E2E;
2. record the roadmap integration state as COMPLETE;
3. formally open the boundary for Block 10.

## Final DoD decision

**PASS — the existing Analyze pipeline satisfies the mandatory integration Definition of Done.**

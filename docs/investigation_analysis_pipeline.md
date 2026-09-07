# Investigation Analysis — Production Pipeline

Status: integration-complete candidate
Scope: existing Case Workspace `Analyze` action
Project root: `C:\osintxz`

## Purpose

The mathematical and analytical core is an internal engine of the existing investigation workflow. It does not expose a separate user-facing window. The existing Case Workspace `Analyze` action remains the single user entry point.

## Production flow

```text
User
  ↓
Case Workspace — Analyze
  ↓
CaseWorkspacePage
  ↓
InvestigationAnalysisRequest
  ↓
background QThread / worker
  ↓
InvestigationAnalysisOrchestrator
  ↓
CASE_VALIDATION
  ↓
ENTITY_RESOLUTION
  ↓
EVIDENCE
  ↓
GRAPH
  ↓
TEMPORAL
  ↓
ANOMALY
  ↓
CLUSTERING
  ↓
MULTIMODAL          [conditional on applicable evidence]
  ↓
RAG
  ├─ Unified Search
  ├─ RAG Retrieval
  ├─ bounded context
  ├─ investigation summary
  ├─ hypotheses
  ├─ contradictions
  ├─ next investigation steps
  └─ citation validation / R1, R2, ...
  ↓
UNIFIED_CONTEXT
  ↓
InvestigationAnalysisResult
  ↓
existing AI Assistant / Case Workspace UI
```

## Architectural ownership

### CaseWorkspacePage

Owns the desktop execution lifecycle:

- converts the existing UI action into `InvestigationAnalysisRequest`;
- starts the analysis outside the UI thread;
- forwards progress events to the existing workspace status UI;
- prevents duplicate full-analysis runs;
- owns cooperative cancellation;
- owns the soft heavy-stage watchdog;
- renders final, partial, citation, warning, and normalized error output.

It does not implement Graph, Temporal, anomaly, clustering, RAG, or multimodal algorithms.

### InvestigationAnalysisOrchestrator

Owns orchestration only:

- case validation;
- canonical stage ordering;
- stage dependencies;
- stage progress;
- timing;
- cancellation boundaries;
- failure isolation;
- partial-result construction;
- reuse of precomputed Graph / Temporal / RAG objects;
- assembly of one final `InvestigationAnalysisResult`.

It does not persist analytical results and does not silently convert analytical signals into facts.

### Mathematical / analytical services

Existing services continue to own their algorithms:

- Entity Resolution;
- Evidence analysis;
- Graph analysis;
- Temporal analysis;
- Anomaly analysis;
- Entity clustering;
- Multimodal analysis.

Heavy upstream results are reused by downstream stages. Graph and Temporal are not recomputed by Anomaly or Clustering during one orchestrated Analyze run.

### RAG / AI layer

The AI layer is grounded in the existing Unified Search system:

```text
Unified Search
  ↓
one RAG retrieval
  ↓
bounded RAG context
  ↓
summary + conclusions
  ↓
citation validation
```

Default RAG guards currently verified by functional tests:

- result limit: 20;
- candidate limit: 100;
- total context budget: 12,000 characters;
- per-source context budget: 3,000 characters.

Citation validity means that a reference resolves to a source made available to the model. It does not mean that the generated statement itself has been independently proven true.

### Unified Analytical Context

`InvestigationUnifiedAnalyticalContext` is an aggregation boundary.

It receives already calculated typed results and packages them into one context. It must not trigger Graph, Temporal, Anomaly, Clustering, RAG, or other heavy calculations again.

## Runtime guarantees

The integration has regression coverage for the following runtime guarantees:

- one active full Analyze run per Case Workspace page;
- background execution outside the UI thread;
- progress delivery back to the UI;
- cooperative cancellation;
- heavy-stage timeout guard;
- safe cleanup and subsequent restart;
- bounded RAG memory/context use;
- transaction/read-only safety for analytical execution;
- partial results when a non-fatal stage fails;
- mathematical results survive Ollama outage;
- no duplicate legacy AI/workflow route for the main Analyze action;
- conditional multimodal execution;
- existing non-Analyze Case Workspace actions remain available.

## Data-safety boundary

Ordinary investigation Analyze is read-only with respect to analytical execution.

Verified safeguards include:

- no automatic Entity merge;
- no automatic creation/update of Evidence, Relationships, TimelineEvents, or analytical persistence from the read-only pipeline;
- no unexpected `commit`;
- no unexpected ORM write flush;
- no unexpected INSERT / UPDATE / DELETE;
- no hidden second search/AI path.

Any explicit user action that intentionally creates or edits investigation data remains outside this read-only Analyze boundary and continues to use the existing transactional Case Workspace action flow.

## Failure model

A failure in an optional/non-fatal stage does not invalidate already computed successful stages.

Example:

```text
Graph          SUCCESS
Temporal       SUCCESS
Anomaly        SUCCESS
Clustering     FAILED
UnifiedContext SUCCESS
Overall        PARTIAL
```

AI provider failure follows the same rule: core mathematical results remain available while the RAG stage reports failure and the overall result becomes partial.

## Performance baseline

The real-case E2E run on 2026-08-25 showed that most mathematical stages complete quickly relative to RAG. One recorded run included approximately:

- Graph: 0.02 s
- Temporal: 0.77 s
- Anomaly: 1.41 s
- Clustering: 0.007 s
- Multimodal: 0.007 s
- RAG: 144.15 s

This is a baseline, not a performance guarantee. RAG is currently the dominant latency source and is the main future optimization target.

## Integration boundary

Once Block 9 is closed, further changes to this pipeline are new development tasks. They should not be treated as unfinished work from the mathematical-core integration unless they fix a regression against the documented contracts above.

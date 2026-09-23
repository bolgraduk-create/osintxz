# OSINTXZ — Fixed Roadmap to v1.0

Status baseline: M025 unified explainability / WHY UI.
Baseline commit: 4f51c61e8b764a74de984713f8220de67577e155.
This document is the fixed implementation order for the production-readiness phase.
Architecture is not to be changed outside the current stage unless explicitly approved.

## R14.1 — Baseline & CI Quality Gate

Goal: make the current working system reproducible and regression-resistant.

Deliverables:
- one integration branch based on the latest accepted M025 state;
- GitHub Actions quality gate;
- deterministic architecture-contract test suite;
- search-quality benchmark gate;
- M024 confidence and M025 explainability regression suite;
- Alembic heads validation and clean-database upgrade test;
- Python compile/import smoke checks.

Exit criteria:
- CI can execute without API keys or live OSINT services;
- search-quality benchmark passes its fixture thresholds;
- M024/M025 contracts pass;
- an empty PostgreSQL/pgvector database upgrades to Alembic head;
- no production feature work starts while the gate is red.

## R14.2 — Security & Runtime Hardening

Goal: safely process untrusted files, remote data and external-tool output.

Deliverables:
- threat model for desktop/local mode;
- safe secret storage boundary;
- executable allowlist and normalized command construction;
- subprocess output/resource limits;
- archive path-traversal and archive-bomb protection;
- file-type/size/decompression limits;
- outbound network policy for sensitive workflows;
- security regression fixtures;
- sensitive-data display/storage policy enforcement.

Exit criteria:
- hostile archive/path fixtures cannot escape managed storage;
- external tools cannot execute outside the approved runtime policy;
- credentials never enter Evidence, Analysis history or ordinary UI payloads;
- security tests run in CI.

## R14.3 — Entity Review & Identity Resolution Control

Goal: make identity decisions reviewable instead of silently automatic.

Deliverables:
- Possible Match review queue;
- confirm/reject/defer decisions;
- conflict visualization;
- merge provenance and audit trail;
- reversible merge or safe merge-history reconstruction;
- benchmark identities covering common names, aliases and conflicting identifiers.

Exit criteria:
- name-only candidates are never silently merged;
- every confirmed merge has supporting signals and provenance;
- analyst decisions are persisted and explainable.

## R14.4 — Registry Legal Semantics

Goal: prevent legal/court records from being presented with misleading meaning.

Deliverables:
- normalized legal outcome/state model;
- distinction between mention, party, defendant/accused, conviction, acquittal and unknown states where source semantics support it;
- source-specific mapping with provenance;
- uncertainty and unsupported-state handling;
- legal-result UI badges and WHY explanations;
- registry semantic regression fixtures.

Exit criteria:
- the application never infers a conviction from a generic court mention;
- normalized legal states preserve source evidence and uncertainty.

## R14.5 — Background Job Layer

Goal: move long-running OSINT, Registry, AI, OCR and media work into recoverable jobs.

Deliverables:
- persisted job model;
- queued/running/completed/failed/cancelled states;
- progress events;
- cancellation;
- bounded retries/backoff;
- Redis/Celery integration or an equivalent approved implementation behind the existing application boundary;
- restart/recovery semantics;
- desktop job center.

Exit criteria:
- long-running work does not block the desktop UI;
- interrupted jobs have deterministic recovery behavior;
- cancellation and failure are visible and auditable.

## R14.6 — Backup, Restore & Case Portability

Goal: make investigations recoverable and transferable.

Deliverables:
- database backup/restore procedure;
- Case export package with manifest and checksums;
- Case import/restore;
- evidence-file integrity verification;
- versioned package format;
- restore tests from clean state.

Exit criteria:
- a representative investigation can be exported, deleted from a clean test environment and restored with equivalent core records and evidence checksums.

## R14.7 — Import, Media & Geospatial Expansion

Goal: complete high-value ingestion and multimodal workflows.

Deliverables:
- EML/MBOX semantic import;
- CSV/XLSX mapping import;
- WhatsApp/Discord export import where format support is deterministic;
- bulk directory/archive ingestion;
- transcript entity extraction and search indexing;
- speaker diarization;
- scene/keyframe detection;
- reverse geocoding;
- map/timeline synchronization;
- location confidence and provenance.

Exit criteria:
- imported communication/media artifacts enter the same Source/Evidence/Entity/Timeline model;
- derived media/geospatial claims remain traceable to source evidence.

## R14.8 — Release Engineering & v1 Acceptance

Goal: produce a repeatable Windows desktop release.

Deliverables:
- clean-install workflow;
- Windows packaging/installer;
- first-run diagnostics;
- migration execution on upgrade;
- rollback/recovery documentation;
- release versioning and changelog;
- acceptance suite;
- performance/stability run on a representative investigation dataset.

Exit criteria:
- v1 installs on a clean supported Windows machine;
- application starts without a development environment;
- database migration and recovery paths are documented and tested;
- acceptance gate is green.

## Cross-stage rules

1. Preserve the existing Source -> Evidence -> Entity provenance model.
2. No automatic identity merge from a name-only match.
3. Sensitive credential/leak content is not exposed as ordinary user-visible content.
4. New external sources must declare access policy, configuration state and provenance.
5. Every new scoring or inference mechanism must expose a human-readable explanation.
6. Every stage adds regression tests before it is considered complete.
7. main is updated only from a green production-readiness baseline.

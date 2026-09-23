# R14.2 — Security & Runtime Hardening

R14.2 turns the current desktop OSINT runtime into a stricter execution
environment for untrusted files, remote data and third-party CLI tools.

## R14.2a — ToolRunner Guardrails

Implemented in this branch:

- one security policy boundary before subprocess execution;
- maximum process timeout;
- maximum stdin size;
- maximum command-argument count and argument size;
- working-directory validation;
- bounded per-process environment overrides;
- blocking of high-risk executable/library injection variables;
- explicit `blocked_by_policy` execution result;
- cross-platform regression tests that execute only the current Python runtime.

The runner continues to use `shell=False`. Existing normal connector commands
retain the same subprocess behavior after policy validation.

### Deliberately not included yet

R14.2a does not claim complete subprocess isolation. The following are separate
hardening steps because they require connector inventory and compatibility
testing:

- executable allowlisting;
- bounded stdout/stderr capture;
- process-tree termination;
- CPU/memory limits where supported;
- outbound network policy;
- sandboxing of selected third-party tools.

## R14.2b — Executable Inventory & Output Budgets

Planned next:

1. inventory every CLI executable and invocation path;
2. route managed binaries through the canonical tool runtime;
3. define the approved executable set;
4. cap captured stdout/stderr without losing partial-result semantics;
5. add process-tree termination tests.

## R14.2c — Untrusted File & Archive Boundaries

Planned after subprocess hardening:

- managed-storage path confinement;
- archive traversal prevention;
- decompressed-size/file-count/depth limits;
- archive-bomb regression fixtures;
- stricter file-size and file-type policies.

## R14.2d — Secrets & Network Boundaries

Planned final security slice:

- secret-storage boundary;
- outbound network policy for sensitive workflows;
- provider credential handling audit;
- evidence/history/UI leak regression tests;
- threat-model closure audit.

## Exit rule

R14.2 is complete only when all new security tests are included in the normal
quality gate and no existing search, registry, analysis or OSINT regression is
broken.

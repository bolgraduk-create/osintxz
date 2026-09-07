# M021.4 — Production Integration + ServiceContainer

## Goal

Provide one application-level entry point for policy-controlled OSINT
enrichment and wire it into the existing composition root.

## Production path

`Target/Entity`
`-> Pivot Policy`
`-> Capability Router`
`-> Enrichment Execution`
`-> existing OsintPipeline`
`-> Findings Persistence`
`-> Source / Evidence / Entity`

## Manual workspace compatibility

The existing `OsintWorkspaceService` is intentionally left unchanged.

It is the user-driven/manual OSINT workspace and may execute explicitly selected
connectors.

The new `OsintEnrichmentService` is the Investigation Engine path and always
uses M021 policy routing.

Both reuse the same:

- OsintManager
- ConnectorRegistry
- OsintPipeline

There is no second OSINT runtime.

## Transaction policy

`OsintEnrichmentService` does not call commit/rollback.

The caller/application transaction boundary remains responsible for committing
or rolling back persistence.

## Recursion

This block performs one target enrichment pass only.

It increments `PivotTraversalState.new_entities_count` when persistence creates
new entities, preparing the same state object for M021.5 controlled recursive
pivot expansion.

Automatic recursion is not enabled in M021.4.

## Applying ServiceContainer wiring

After extracting the patch into the project root:

`python tools/apply_m021_4_service_container_patch.py`

The patcher is strict, idempotent and creates:

`app/core/service_container.py.m021_4_backup`

before the first modification.

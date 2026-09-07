# M021.5 — Controlled Recursive Pivot Expansion

## Goal

Turn one-pass M021.4 enrichment into bounded recursive OSINT discovery.

## Traversal model

Breadth-first search:

`seed(depth=0)`
`-> enrich + persist`
`-> persisted Entity candidates(depth=1)`
`-> enrich + persist`
`-> ...`

## Candidate source

Recursive pivots are created only from persisted/normalized Entity objects.

Raw `OsintFinding.value`, connector metadata and arbitrary page text are not
recursed directly.

Supported automatic entity pivots:

- USERNAME
- EMAIL
- PHONE
- DOMAIN
- URL
- IP

Blocked by default:

- ACCOUNT
- PERSON
- ORGANIZATION
- LOCATION
- ADDRESS
- DOCUMENT
- OTHER

These blocked objects may later receive explicit evidence-aware conversion
policies, but M021.5 does not infer them.

## Guards

The same `PivotTraversalState` is reused through the complete traversal.

Existing M021.1 policy remains authoritative for:

- max_depth
- max_pivots_per_entity
- visited target/goal pivots
- max_new_entities

The recursive service also maintains a queue-level scheduled set so the same
entity/value is not enqueued repeatedly inside one traversal.

## Runtime policy

M021.5 does not alter connector eligibility. Every recursive target goes back
through:

`Pivot Policy -> Capability Router -> Execution Boundary`

Therefore active, credentialed, separate and unsupported connectors remain
excluded exactly as before.

## Transactions

No commit/rollback occurs inside this service.

## No migration

No database schema changes are introduced.

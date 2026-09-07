# M021.6 — Recursive OSINT Golden Fixture + Regression Gate

## Purpose

Freeze the M021.0.1-M021.5 recursive OSINT behavior before implementing the
Open-Web Discovery Layer.

## Golden scenario

`USERNAME golden_alice`
`-> Maigret-like deterministic account finding`
`-> ACCOUNT + URL persisted`
`-> ACCOUNT blocked from recursion`
`-> URL recursive pivot`
`-> Common-Crawl-like deterministic findings`
`-> DOMAIN + URL persisted`
`-> DOMAIN / URL depth=2 pivots`
`-> max_depth stops further expansion`

## What is real

The fixture uses the production M021 services:

- capability catalog
- pivot policy
- capability router
- enrichment execution boundary
- findings persistence
- application enrichment service
- recursive enrichment service

## What is fake

Only external side effects are replaced:

- connectors are deterministic test doubles
- repositories/domain storage are in-memory doubles

Therefore the fixture requires:

- no internet
- no API keys
- no external CLI
- no PostgreSQL
- no Redis
- no Ollama

## Regression guarantees

The tests guard:

- recursive BFS behavior
- connector policy
- active/credentialed connector exclusion
- persistence provenance
- ACCOUNT recursion block
- max depth
- full rerun persistence idempotency

## Gate

Run:

`.\.venv\Scripts\python.exe .\tools\run_m021_6_recursive_osint_gate.py`

The gate also reruns the focused regression tests from M021.0.1 through M021.5.

## Schema

No migration is required.

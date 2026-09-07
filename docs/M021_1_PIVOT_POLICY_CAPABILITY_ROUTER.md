# M021.1 — Pivot Policy + Capability Router

## Purpose

Turn the M021.0.1 capability catalog into a deterministic routing contract.

No connector is executed by this block.

## Flow

`Target -> default discovery goal -> pivot policy -> capability router -> allowed connector capabilities`

## Safety / stability guards

The automatic policy carries conservative traversal limits:

- max depth
- max pivots per entity
- max new entities per enrichment run
- normalized visited-pivot keys

This prevents recursive discovery from repeatedly expanding the same object.

## Important routing rules

- USERNAME / ACCOUNT_DISCOVERY -> Maigret + Sherlock by default.
- EMAIL / EMAIL_REGISTRATION -> keyless support tools only.
- PHONE -> PHONE_ENRICHMENT only. Account discovery is intentionally not
  invented until a real open-web phone discovery capability exists.
- DOMAIN -> domain discovery and historical-web routes.
- active assessment tools are excluded from all automatic routes.
- credentialed connectors are excluded from all automatic routes.
- HASH currently has no automatic route because its useful sources are
  optional/credentialed.

## What this block does NOT do

- no connector execution
- no HTTP/network requests
- no findings persistence
- no recursive entity creation
- no Investigation Engine orchestration

Those begin in later M021 blocks.


## Goal-specific disposition rule

`ACCOUNT_DISCOVERY` is stricter than other automatic goals:

- only `CORE` connectors are allowed automatically;
- `SUPPORT` connectors such as SocialScan do not widen the primary username
  account-discovery route;
- support signals may be used in later enrichment/validation stages.

Other safe automatic goals may use both `CORE` and `SUPPORT` connectors.

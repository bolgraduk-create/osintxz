# OSINTXZ R13.20 — Unified Investigation Search

R13.20 turns the existing **Search** page into the primary investigation workflow.
Instead of entering one target at a time, an analyst can enter every currently
known data point and let OSINTXZ build a bounded, policy-aware search plan over
the source layers already present in the application.

## What is added

- Structured **Known Data** form for identity, online identifiers, locations,
  organizations, registry identifiers, web/network indicators and specialist
  identifiers.
- One **Run All Sources** operation over:
  - Classic OSINT connectors;
  - Open-Web / archive providers;
  - R13 Federation adapters;
  - Registry Intelligence providers.
- Existing controlled recursive OSINT is reused rather than replaced.
- Federation and Registry records can produce a bounded second wave of **exact
  identifier pivots** (email, username, phone, domain, URL, IP, hash, CVE, LEI,
  etc.).
- Weak names/organizations remain review candidates and are **not** automatically
  treated as the same identity.
- Name-based court routing is opt-in with **Include sensitive legal name routes**.
- Contract, verified-scope, dark-web, secret-scanning, wanted/sanctions-style
  explicit sources are not silently executed by a generic search.
- The previous persisted-data search remains available under **Stored Intelligence**.
- Result Center tabs: Results / Providers / Pivots / Errors.

## Persistence rules

Classic OSINT and Open-Web continue using their existing Evidence/Entity
persistence path because that is what enables provenance-aware recursive pivots.
Federation and Registry results on this unified page remain review-first; they are
not silently persisted as verified identity facts.

No raw password, cookie, token, session value, private key or other active secret
is stored by this workflow.

## What is NOT changed

- No database migration.
- No new bulk datasets.
- No new external sources.
- Existing dedicated OSINT, Sources and Registry pages remain available.
- Existing connector policy and pivot budgets remain authoritative.
- R13.18 Source Center and R13.19 Registry Center are not replaced.

## Install

From `C:\osintxz` with the virtual environment active:

```powershell
python .\OSINTXZ_R13_20_UNIFIED_INVESTIGATION_SEARCH\install_r13_20_unified_investigation_search.py C:\osintxz --run-tests
```

The installer creates a backup below:

```text
C:\osintxz\storage\patch_backups\r13_20_<timestamp>
```

## Manual UI check

Run:

```powershell
python main.py
```

Open **Search**, select an investigation, enter one or more known values, leave
safe pivoting enabled and run **Run All Sources**. Inspect Providers and Pivots to
see which source layer handled each seed and which exact identifiers were queued
for the second wave.

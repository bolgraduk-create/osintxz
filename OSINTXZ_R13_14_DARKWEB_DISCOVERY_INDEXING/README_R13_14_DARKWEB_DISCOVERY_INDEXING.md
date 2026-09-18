# OSINTXZ — R13.14 Dark Web Discovery & Indexing

## What this pack adds

R13.14 turns the existing R13.7 single-page Tor reader into a bounded discovery workflow without changing the database schema.

- `DarkWebDiscoveryService`: breadth-first discovery from explicit public v3 `.onion` seeds.
- Ahmia clearnet metadata integration:
  - known non-banned onion directory can be imported as candidate URLs without fetching them;
  - published Ahmia blacklist hashlist is checked before Tor access and is fail-closed by default.
- Hard crawl budgets: max pages, max depth, per-host limit and per-page discovered-link limit.
- Only discovered `.onion` links are followed. Clearnet links remain indicators and are never crawled by this workflow.
- No login, authentication bypass, POST/forms, redirect following, binary/file downloads or direct-network fallback.
- No raw HTML/page body is persisted. Existing indicator extraction produces only bounded metadata.
- New `TorOnionDiscoveryAdapter` plugs discovery into the R13 Federation Core but has `automatic_enabled=False`, so generic federation cannot start Tor crawling accidentally.
- `ExposureFederationService.discover_onion()` gives an explicit application entry point.
- Dark-web discovery records can reuse the existing Exposure persistence layer.
- Exposure persistence now places only whitelisted non-secret indicators (email/domain/username/URLs/crypto addresses) in Evidence description so the existing text index can find them. Secret-like indicator kinds are excluded.

## Safety properties

The crawler operates only on public, unauthenticated v3 onion pages. Ahmia's safety blocklist is required by default. If that blocklist cannot be loaded, discovery stops before any Tor request. Existing R13.7 protections still reject clearnet targets, v2 onion addresses, credential-bearing URLs, sensitive query parameters, redirects, attachments and unsupported content types.

## Database

No migration and no new database tables.

## Expected regression gate

R13.13 baseline: 79 passing tests.
R13.14 adds 11 tests.
Expected combined gate on the tested baseline: **90 passed**.

## Install

From `C:\osintxz` with `.venv` active:

```powershell
python .\OSINTXZ_R13_14_DARKWEB_DISCOVERY_INDEXING\install_r13_14_darkweb_discovery_indexing.py C:\osintxz --run-tests
```

A backup is created under `storage/patch_backups/r13_14_<timestamp>` before files are changed.

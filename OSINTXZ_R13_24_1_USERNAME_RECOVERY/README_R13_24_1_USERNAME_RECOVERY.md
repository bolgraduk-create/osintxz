# OSINTXZ R13.24.1 — Username Recovery Hotfix

Purpose: restore useful username/account findings that disappeared after strict result hardening, while keeping historical URL noise suppressed.

## Changes

- Sherlock uses its bundled local site database, a larger bounded process budget, and recovers already printed claimed profile URLs when a timeout happens before CSV finalisation.
- User Scanner runs username checks in independent category passes (`social`, `dev`, `creator`, `community`, `gaming`, `donation`) so one slow category cannot discard the rest of the scan.
- Maigret fast-pass expands from 140 to 300 ranked sites and can recover safe owner-profile URLs from partial stdout.
- Unified Search preserves Classic OSINT finding metadata/confidence/reliability.
- An explicit `account`/`username` finding for exactly the searched handle receives a structured username identifier even when the provider does not return a canonical profile URL.
- Exact username/account findings are visible again; unrelated archive/GAU/Wayback URLs remain suppressed.
- Username-only Classic OSINT requests use a slightly larger per-connector timeout and the overall Classic budget is raised to 250 seconds.

## Not changed

- No database migrations.
- No new bulk downloads.
- No weakening of the pre-persistence Evidence gate.
- No fuzzy username ownership inference.
- No automatic pivot from medium-confidence/foreign-account URLs.

## Test gate

`tests/test_r13_24_1_username_recovery.py` plus prior R13.24 / R13.21.4 / QML regression tests when present.

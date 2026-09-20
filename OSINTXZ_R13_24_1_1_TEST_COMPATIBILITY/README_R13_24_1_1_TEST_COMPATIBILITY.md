# OSINTXZ R13.24.1.1 — Maigret Regression Compatibility Fix

This is a test-only compatibility hotfix for R13.24.1.

R13.24 originally fixed the Maigret fast-pass at 140 sites and its regression test asserted that literal value. R13.24.1 intentionally expanded the bounded fast-pass to 300 sites, but the older test was left unchanged.

This package updates only the regression contract:

- keeps the R13.24.1 Maigret limit at 300;
- still requires `--top-sites` to be explicitly bounded;
- accepts only a bounded value between 1 and 500;
- still requires `--no-recursion`, `--no-extracting`, and `--retries 0`;
- does not change connectors, Search UI, database, persistence, APIs, or source configuration.

A backup of the previous test file is created before replacement.

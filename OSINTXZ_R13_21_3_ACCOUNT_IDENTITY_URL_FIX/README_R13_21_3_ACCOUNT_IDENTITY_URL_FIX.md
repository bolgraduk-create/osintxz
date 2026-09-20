# OSINTXZ R13.21.3 — Account Identity Separation & URL Relevance Fix

This is a focused hotfix on top of R13.21.2.

## Added / changed

- Online accounts (`public_account`, `public_user`, `profile`, `account`, username-like records) are no longer treated as separate PERSON identity candidates.
- Added `Related Accounts` result contract and an `Accounts` tab in Investigation Search.
- Exact username searches now require evidence in the returned account identifier/value or in an account-owner URL path. The original seed echoed in UI metadata no longer makes an unrelated historical URL relevant.
- Random GAU/Wayback-style URLs returned from a username route stay available in Raw but are suppressed from Clean and cannot become pivots.
- Hardened the classic Common Crawl connector: malformed JSON and JSON strings/lists are skipped safely instead of causing `'str' object has no attribute 'get'`.
- Updated the R13.21.2 regression test to reflect the corrected person-vs-account domain model.

## Not changed

- No database migration.
- No source/API-key changes.
- No weakening of the R13.21.2 pre-persistence gate.
- No automatic identity assertion. A related account is a signal, not proof of account ownership by a person.
- Raw provider output remains available for analyst review.

## Verification

The installer runs `py_compile` and, with `--run-tests`, the new R13.21.3 tests plus available R13.20/R13.21, Common Crawl, persistence, recursion and QML bridge regressions.

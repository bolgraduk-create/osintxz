# OSINTXZ R13.23.1.1 — Person Card Compatibility Fix

Small compatibility hotfix for R13.23.1.

## Fix

R13.23.1 split the old `WEB & TECHNICAL` area into `WEB PROFILES / PAGES` and `TECHNICAL`. The old R13.23 regression suite still expects the safe empty-state text `No web / network identifiers`.

This hotfix keeps the new split UI and restores that compatibility text for the empty `TECHNICAL` group. It does not change search, persistence, database schema, sources, Mentions, provenance, or Person relationships.

## Install

```powershell
python .\OSINTXZ_R13_23_1_1_COMPATIBILITY_FIX\install_r13_23_1_1_compatibility_fix.py C:\osintxz --run-tests
```

The installer prefers `C:\osintxz\.venv\Scripts\python.exe` for pytest when available.

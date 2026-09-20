# OSINTXZ R13.24.2.1 — URL Scope Compatibility Fix

Small logic hotfix for R13.24.2 Balanced Relevance.

## Fix
- Same host alone no longer makes a suppressed URL visible as `Possible`.
- URL seeds use path scope:
  - `https://gitlab.com/torvalds` -> `https://gitlab.com/torvalds/linux` may be `Possible`.
  - `https://gitlab.com/torvalds` -> `https://gitlab.com/adamstoolkit` remains suppressed.
  - A host-root seed such as `https://example.com/` can still surface same-host pages.
- Persistence, Evidence, pivots, connectors, DB and migrations are unchanged.

This preserves the softer analyst-visible R13.24.2 behavior while keeping completely unrelated same-host URLs out of it.

## Regression contract update
The R13.24.2 test that previously treated any same-host URL as `Possible` is updated to the new rule: same host alone is not a relation; the path must remain inside the searched URL scope.

OSINT Intelligence Platform
OSINT Expansion 05R3 — Desktop Root Recursive Wiring

05R2 proved live production recursion:
- targets_processed: 7
- candidates_discovered: 19
- candidates_enqueued: 6
- max observed depth: 2
- live collection: PASS
- PostgreSQL persistence: PASS
- second-level recursion: PASS
- policy limits: PASS
- rollback: clean

05R1 also showed that the desktop checkbox did not start recursion from the
root OSINT seed. The UI first ran one-shot OSINT and only later bridged
Open-Web-persisted entities into recursion.

05R3 changes exactly two production UI files:

1. app/interface/desktop/workers/investigation_search_worker.py
2. app/interface/desktop/views/workspace/investigation_search_view.py

New checkbox behavior:

    target
      -> OsintRecursiveEnrichmentService.enrich(root seed)
      -> root OSINT result
      -> persisted Entities
      -> BFS pivots
      -> Open-Web seed search
      -> Open-Web persisted entities
      -> SAME PivotTraversalState
      -> additional bounded recursion

This means visited guards, max depth, per-entity pivot budgets and the global
new-entity budget are shared rather than reset between root OSINT and Open-Web.

When recursive is OFF, the old one-shot OsintEnrichmentService.enrich_target()
path remains unchanged.

EMAIL and USERNAME are no longer artificially excluded by the desktop worker.
The production PivotPolicy/CapabilityRouter remains authoritative for what they
are allowed to expand into.

The result view now displays:
- recursive targets processed
- recursive candidates discovered/enqueued
- max recursive depth
- stop reason
- extra Open-Web recursive candidates/targets
- entities and connector rows from recursive child runs

Added:
    tests/test_investigation_search_root_recursive_ui.py

INSTALL
-------
Extract this ZIP into:
    C:\osintxz
with replacement.

TARGETED TESTS
--------------
    cd C:\osintxz

    & .\.venv\Scripts\python.exe -m pytest `
        .\tests\test_investigation_search_root_recursive_ui.py `
        .\tests\test_osint_recursive_controlled_simulation.py `
        .\tests\test_osint_recursive_budget_wiring.py -q

FULL SUITE
----------
    & .\.venv\Scripts\python.exe -m pytest -q

APP CHECK
---------
After tests are green, launch the normal desktop application exactly as you
usually do.

Open a Case -> Investigation Search.

For the first controlled UI check:
    Target: example.com
    Enable:
        "Автоматически продолжать поиск по найденным сущностям"

Run search.

The Overview should now contain lines similar to:
    Recursive targets processed: <N>
    Recursive candidates: <N>; enqueued: <N>
    Recursive max depth: <N>; stop: <reason>
    Open-Web extra recursive candidates: <N>; targets: <N>

A value greater than 1 for "Recursive targets processed" proves the UI itself
has performed follow-up OSINT on a persisted entity.

IMPORTANT
---------
This patch does not change PivotPolicy limits and does not bypass persistence.
Raw findings still do not become pivots directly.

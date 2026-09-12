OSINT Intelligence Platform
OSINT Expansion 05R3b — Recursive Budget Fairness

Observed in the real desktop app:
    OSINT findings: 50
    New Entity: 50
    Recursive targets processed: 1
    Recursive candidates: 50; enqueued: 0
    stop: new_entity_budget_reached

Root cause:
The global max_new_entities=50 was correctly enforced, but execute_defaults()
gave the ROOT target the entire remaining budget. A high-volume first target
could therefore consume all 50 entities before the BFS had a chance to process
any discovered pivot.

05R3b DOES NOT raise the global limit.

It adds a target-local entity creation cap that sits below the existing global
budget:

    effective target budget =
        min(global remaining entities, per-target limit)

Desktop recursive mode uses:
    root recursive per-target new Entity limit: 5
    Open-Web recursive per-target new Entity limit: 5

Global policy remains:
    max_depth = 3
    max_pivots_per_entity = 8
    max_new_entities = 50

The physical persistence budget is still authoritative, so this is not merely
a UI/result truncation.

Expected behavior for example.com:
    root target creates <=5 new Entity
        -> candidates can be enqueued
        -> depth 1 targets execute
        -> later targets share the still-remaining global budget

Production files:
    app/osint/enrichment_execution.py
    app/application/osint_enrichment_service.py
    app/application/osint_recursive_enrichment_service.py
    app/application/open_web_recursive_pivot_service.py
    app/interface/desktop/workers/investigation_search_worker.py

Tests:
    tests/test_osint_recursive_budget_fairness.py
    tests/test_investigation_search_recursive_progress.py

INSTALL
-------
Close the running desktop application.

Extract into:
    C:\osintxz
with replacement.

TARGETED TESTS
--------------
    cd C:\osintxz

    & .\.venv\Scripts\python.exe -m pytest `
        .\tests\test_osint_recursive_budget_fairness.py `
        .\tests\test_investigation_search_recursive_progress.py `
        .\tests\test_osint_recursive_progress_runtime_budget.py `
        .\tests\test_investigation_search_root_recursive_ui.py `
        .\tests\test_osint_recursive_controlled_simulation.py `
        .\tests\test_osint_recursive_budget_wiring.py -q

FULL SUITE
----------
    & .\.venv\Scripts\python.exe -m pytest -q

APP TEST
--------
Restart the desktop app.

Case -> Investigation Search
Target:
    example.com

Enable:
    Автоматически продолжать поиск по найденным сущностям

The important change is that the Overview should NO LONGER show:
    New Entity: 50
    Recursive targets processed: 1
    enqueued: 0
    stop: new_entity_budget_reached

A healthy controlled run should instead have:
    New Entity on root: <= 5
    Recursive targets processed: > 1
    Recursive candidates enqueued: > 0
    Recursive max depth: >= 1

Exact counts vary with live sources.

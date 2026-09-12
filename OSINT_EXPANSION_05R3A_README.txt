OSINT Intelligence Platform
OSINT Expansion 05R3a — Recursive Progress + Interactive Runtime Budget

Problem observed in the desktop app:
- status stayed on the first recursive message for 5+ minutes;
- no visible progress was emitted while the BFS processed targets;
- UI passed timeout=120 to every connector execution inside recursion.

Root cause:
OsintRecursiveEnrichmentService was synchronous at target level and had no
progress callback. The worker therefore emitted one status before .enrich()
and stayed silent until the whole recursive traversal returned.

05R3a fixes this without changing global OSINT/PivotPolicy limits.

PRODUCTION CHANGES
------------------
1. app/application/osint_recursive_enrichment_service.py
   - optional target-level progress callback
   - queue/target start/target finish/completed/stopped events
   - optional max_targets safety bound
   - optional overall time_budget_seconds bound checked between targets
   - new stop reasons:
       max_targets_reached
       time_budget_reached
   - callback failures cannot break evidence collection

2. app/application/open_web_recursive_pivot_service.py
   - forwards progress callback and runtime bounds to the same recursive BFS

3. app/interface/desktop/workers/investigation_search_worker.py
   Interactive-only limits:
       connector timeout: 15 s
       root recursive max targets: 6
       root recursive time budget: 150 s
       Open-Web timeout: 20 s
       Open-Web recursive max targets: 4
       Open-Web recursive time budget: 90 s

   These DO NOT alter backend/free-maximum policy.
   They only bound one interactive desktop search.

The status now changes between targets, for example:
    Recursive OSINT: depth=0 · domain · example.com · ...
    Recursive OSINT: цель завершена · обработано=1 · findings=...
    Recursive OSINT: depth=1 · url · https://... · ...

IMPORTANT
---------
The time budget is checked between targets. A connector already running is
still governed by its connector timeout (15 seconds in desktop mode).

INSTALL
-------
Close the currently running desktop app/search first.

Extract this ZIP into:
    C:\osintxz
with replacement.

TARGETED TESTS
--------------
    cd C:\osintxz

    & .\.venv\Scripts\python.exe -m pytest `
        .\tests\test_osint_recursive_progress_runtime_budget.py `
        .\tests\test_investigation_search_recursive_progress.py `
        .\tests\test_investigation_search_root_recursive_ui.py `
        .\tests\test_osint_recursive_controlled_simulation.py `
        .\tests\test_osint_recursive_budget_wiring.py -q

FULL SUITE
----------
    & .\.venv\Scripts\python.exe -m pytest -q

APP TEST
--------
Restart the normal desktop app.

Case -> Investigation Search:
    example.com

Enable:
    Автоматически продолжать поиск по найденным сущностям

Now the status should update while recursion advances. It should not sit for
five minutes on the single initial message.

If a target is slow, the status will explicitly show the target/depth and:
    "Ожидание источников..."

After this is green we can add an explicit Cancel button as a separate UX
improvement if desired.

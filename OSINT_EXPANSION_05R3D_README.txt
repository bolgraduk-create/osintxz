OSINT Intelligence Platform
OSINT Expansion 05R3d — Certificate Finding -> Entity Mapping

PROVEN ROOT CAUSE
-----------------
The latest real desktop search produced five OSINT Evidence rows from crt.sh:

    certificate "*.example.com"
    certificate "example.com"
    certificate "www.example.com"
    certificate "user@example.com"
    certificate "AS207960 Test Intermediate - example.com"

Production _entity_candidates() returned ZERO candidates for all five because
category="certificate" had no identifier mapping.

05R3d fixes ONLY this proven mapping gap.

SAFE CERTIFICATE RULES
----------------------
A certificate finding becomes an Entity only if the entire value is a valid,
conservative identifier:

    *.example.com
        -> DOMAIN example.com

    example.com
        -> DOMAIN example.com

    www.example.com
        -> DOMAIN www.example.com

    user@example.com
        -> EMAIL user@example.com

Arbitrary certificate/common-name text:

    AS207960 Test Intermediate - example.com

remains Evidence only and never becomes an Entity/pivot.

Certificate Evidence is now typed as METADATA rather than OTHER.

No global recursion limits are raised.
No raw metadata text is searched recursively.
No certificate issuer/serial/common-name description is treated as an
identifier unless the whole finding value passes the strict syntax gate.

FILES
-----
Production:
    app/osint/finding_persistence.py

Tests:
    tests/test_osint_certificate_entity_mapping.py

INSTALL
-------
Close the desktop app.

Extract into:
    C:\osintxz
with replacement.

TARGETED TESTS
--------------
    cd C:\osintxz

    & .\.venv\Scripts\python.exe -m pytest `
        .\tests\test_osint_certificate_entity_mapping.py `
        .\tests\test_osint_persistence_entity_pivot_integration.py `
        .\tests\test_osint_recursive_budget_fairness.py `
        .\tests\test_osint_recursive_progress_runtime_budget.py `
        .\tests\test_investigation_search_recursive_progress.py `
        .\tests\test_investigation_search_root_recursive_ui.py -q

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

Now a normal successful crt.sh result should produce Entity candidates.

Expected qualitative result:
    New Entity: > 0
    Recursive candidates: > 0
    enqueued: > 0
    Recursive targets processed: > 1
    Recursive max depth: >= 1

Exact live counts can vary.

NOTE ABOUT EXISTING EVIDENCE
----------------------------
The five Evidence rows already stored by the previous run will not be
retroactively converted by this patch alone. Run the search again after
installing 05R3d so the fixed persistence path receives live findings.

OSINT Intelligence Platform
OSINT Expansion 04H — Controlled Recursive Integration Simulation

Purpose:
Prove the recursive safety limits under deterministic load without network or DB.

This block changes NO production files.

Tests:
1. Depth:
   recursion processes depths 0,1,2,3 and never depth 4.

2. Global entity budget:
   recursive expansion stops exactly at max_new_entities.

3. Per-entity pivot budget:
   actual OsintPivotPolicy allows 8 automatic pivots for one entity and blocks
   the 9th/10th with PIVOT_BUDGET_EXHAUSTED.

4. Combined branching pressure:
   a fan-out tree is allowed to expand, but it still cannot create entity #51
   and cannot process beyond max_depth.

Run:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe -m pytest `
        .\tests\test_osint_recursive_controlled_simulation.py -q

Expected:
    4 passed

Then run the recursive/budget regression group:

    & .\.venv\Scripts\python.exe -m pytest .\tests -q `
        -k "osint and (recursive or pivot or budget or enrichment or persistence)"

Finally:

    & .\.venv\Scripts\python.exe -m pytest -q

If the previous 04G2 full suite was 619 passed, this block should raise it to
approximately 623 passed.

OSINT Intelligence Platform
OSINT Expansion 04G2 — Recursive Budget Wiring

04G1 confirmed:
- PivotPolicyLimits defaults:
    max_depth = 3
    max_pivots_per_entity = 8
    max_new_entities = 50
- ConnectorRequest is created in app/osint/enrichment_execution.py
- ConnectorRequest.limit was not wired into recursive execution.
- persistence had no hard new-entity budget.

04G2 changes:
1. PivotTraversalState
   - remaining_new_entities(limits)
   - remaining_pivots(entity_identity, limits)

2. OsintEnrichmentExecutionService
   - derives the ConnectorRequest.limit from remaining max_new_entities
   - keeps one cumulative finding budget across connectors
   - execute_defaults shares the same budget across sibling goals
   - trims legacy/non-compliant connector results at the execution boundary

3. NewEntityBudget
   - one mutable in-memory token may be shared by sibling execution results
   - persistence consumes it only for a genuinely new Entity

4. OsintFindingPersistenceService
   - once NewEntityBudget is exhausted, it cannot create another Entity
   - Evidence can still link to an already-existing Entity
   - generic non-recursive persist_findings() remains backward-compatible/unlimited

Important:
max_pivots_per_entity is intentionally NOT converted into a finding count.
It remains a pivot-operation budget enforced by OsintPivotPolicy.

Changed:
- app/osint/pivot_policy.py
- app/osint/enrichment_execution.py
- app/osint/finding_persistence.py
- tests/test_osint_recursive_budget_wiring.py

Run targeted:
    cd C:\osintxz
    & .\.venv\Scripts\python.exe -m pytest `
        .\tests\test_osint_recursive_budget_wiring.py `
        .\tests\test_osint_discovery_result_budget.py `
        .\tests\test_osint_discovery_connector_reliability.py -q

Then relevant M021/OSINT tests:
    & .\.venv\Scripts\python.exe -m pytest .\tests -q -k "osint and (pivot or enrichment or persistence or recursive)"

Then full suite:
    & .\.venv\Scripts\python.exe -m pytest -q

OSINT Intelligence Platform
OSINT Expansion 04G1 — Recursive Budget Contract Probe

04F status:
- targeted: 15 passed
- live result-budget gate: no violations
- full suite: 613 passed

Goal:
Wire ConnectorRequest.limit into the existing recursive enrichment budgets:
- max_pivots_per_entity
- max_new_entities
- max_depth

Before modifying production code, 04G1 collects the exact current execution path
after Astra.

It makes:
    storage\cache\osint_expansion_04g1\recursive_budget_contract.json
    storage\cache\osint_expansion_04g1\osint_04g1_recursive_budget_bundle.zip

No network, DB writes, or production modifications.

Run:

    cd C:\osintxz
    & .\.venv\Scripts\python.exe .\tools\osint_recursive_budget_contract_probe_04g1.py

Upload BOTH generated files to ChatGPT.

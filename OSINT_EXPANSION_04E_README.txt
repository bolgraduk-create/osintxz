OSINT Intelligence Platform
OSINT Expansion 04E — Discovery Result Budget Gate

04D is green:
- 6 targeted tests passed
- full suite: 604 passed

04B exposed a budget contract bug:
ConnectorRequest.limit was 25, but GAU returned 1508 findings.

04E tests all six discovery wrappers with:
    ConnectorRequest.limit = 5

It reports:
- findings returned
- whether limit was honored
- status/error
- whether the connector source explicitly references request.limit

It also creates a diagnostic ZIP with the exact current six connector sources.

Run:
    cd C:\osintxz
    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"
    & .\.venv\Scripts\python.exe .\tools\osint_result_budget_gate_04e.py

Upload:
    storage\cache\osint_expansion_04e\budget_report.json
    storage\cache\osint_expansion_04e\osint_04e_budget_bundle.zip

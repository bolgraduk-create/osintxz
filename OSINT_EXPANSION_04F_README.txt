OSINT Intelligence Platform
OSINT Expansion 04F — Discovery Result Budget Contract

04E revealed that ConnectorRequest did not actually contain a result-limit
field. The diagnostic gate intended to pass limit=5, but the current request
model had no such field.

04F completes the contract safely:

1. ConnectorRequest gains:
       limit: int | None = None

   None preserves all existing behavior. Existing callers remain compatible.

2. All six discovery connectors honor an explicit limit:
   - subfinder
   - dnsx
   - gau
   - waybackurls
   - katana
   - assetfinder

3. Metadata now exposes:
   - result_limit
   - limit_reached

4. Waybackurls, Katana and Assetfinder also deduplicate results so duplicate
   rows do not waste a result budget.

5. DNSX, Waybackurls, Katana and Assetfinder now resolve the managed binaries
   through app.osint.tool_runtime, matching the Subfinder/GAU runtime model.
   The desktop application no longer has to rely only on shell PATH.

No persistence, evidence, entity-resolution, recursive-pivot or DB contracts
are changed in this block.

Install:
    extract this ZIP into C:\osintxz with file replacement.

Targeted tests:
    & .\.venv\Scripts\python.exe -m pytest `
        .\tests\test_osint_discovery_result_budget.py `
        .\tests\test_osint_discovery_connector_reliability.py -q

Then re-run the same 04E live budget gate:
    & .\.venv\Scripts\python.exe .\tools\osint_result_budget_gate_04e.py

Expected:
    gau          returned <= 5
    waybackurls  returned <= 5
    assetfinder  returned <= 5
    all completed wrappers: limit_honored=True

Then full suite:
    & .\.venv\Scripts\python.exe -m pytest -q

After 04F is green, the next block will wire ConnectorRequest.limit into the
recursive enrichment budget rather than relying on an unlimited default.

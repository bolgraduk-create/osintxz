OSINT Intelligence Platform
OSINT Expansion 04D — Discovery connector reliability fix

Files changed:
- app/osint/runner.py
- app/osint/tool_runtime.py
- app/osint/connectors/subfinder_connector.py
- app/osint/connectors/gau_connector.py
- tests/test_osint_discovery_connector_reliability.py

What changes:
1. ToolRunner preserves partial stdout/stderr when a CLI times out.
2. Subfinder:
   - resolves project-local binary through tool_runtime
   - disables update check during runs
   - bounds Subfinder's own passive-source timeout
   - deduplicates hosts
   - accepts only true subdomains of the requested domain
   - returns PARTIAL if useful findings were emitted before timeout
3. GAU:
   - resolves project-local binary through tool_runtime
   - normalizes URL targets to a hostname
   - adds bounded provider timeout / retries / threads
   - honors ConnectorRequest.include_related via --subs
   - filters unrelated/invalid URLs and removes duplicates
   - returns PARTIAL if useful URLs were emitted before timeout
4. tool_runtime knows the six tools installed in tools/osint/bin.

The patch does not change persistence, evidence, entity resolution or pivot
contracts.

Targeted test:
    & .\.venv\Scripts\python.exe -m pytest .\tests\test_osint_discovery_connector_reliability.py -q

Then re-run 04B:
    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"
    & .\.venv\Scripts\python.exe .\tools\osint_wrapper_execution_gate_04b.py

Then full suite:
    & .\.venv\Scripts\python.exe -m pytest -q

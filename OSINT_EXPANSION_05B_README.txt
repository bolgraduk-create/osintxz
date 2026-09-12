OSINT Intelligence Platform
OSINT Expansion 05B — HTTPX/GHunt Production Contract Probe

05A status:
- ProjectDiscovery httpx installed successfully
- identity=projectdiscovery_httpx
- subfinder/dnsx/gau/waybackurls/katana/assetfinder READY
- GHunt BROKEN due traceback/import failure

05B does not modify production code.

It:
1. Executes app.osint.connectors.httpx_connector against:
       https://example.com
   with:
       ConnectorRequest.limit = 5
       timeout = 20

2. Records the actual OsintResult / findings contract.

3. Inspects the current GHunt connector source without performing an
   account/user query.

4. Captures GHunt --help health.

5. Builds a ZIP containing the exact current production files needed for 05C.

Run:

    cd C:\osintxz

    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"

    & .\.venv\Scripts\python.exe .\tools\osint_httpx_ghunt_contract_probe_05b.py

Upload:
    storage\cache\osint_expansion_05b\httpx_ghunt_contract.json
    storage\cache\osint_expansion_05b\osint_05b_httpx_ghunt_bundle.zip

OSINT Intelligence Platform
OSINT Expansion 05A — ProjectDiscovery httpx + Runtime Identity Hardening

04H status:
- controlled recursive simulation: 4 passed
- recursive/pivot regression group: 85 passed
- full suite: 623 passed

This block changes no production Python files.

It:
1. Installs official ProjectDiscovery httpx into:
       tools\osint\bin\httpx.exe

2. Fingerprints the installed binary so the Python `httpx` CLI can no longer
   be mistaken for ProjectDiscovery httpx.

3. Runs runtime identity audit v3:
   - ProjectDiscovery httpx identity
   - GHunt traceback/import health
   - six discovery CLIs
   - API/config state as ABSENT / DECLARED_EMPTY / PRESENT_NONEMPTY
   - secret values are never shown

Run:

    cd C:\osintxz

    powershell -ExecutionPolicy Bypass -File .\tools\install_projectdiscovery_httpx_05a.ps1

Expected:
    HTTPX IDENTITY CHECK: PASS
    OSINT EXPANSION 05A HTTPX INSTALL: PASS

Then:

    & .\.venv\Scripts\python.exe .\tools\osint_runtime_identity_audit_v3.py

Expected:
    httpx status=READY identity=projectdiscovery_httpx

Send the complete console output back to ChatGPT.

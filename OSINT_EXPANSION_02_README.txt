OSINT Intelligence Platform
OSINT Expansion 02 — Runtime Capability Audit

Why this exists:
The first architecture audit showed many A/100 targets, but many connector
executables are not actually installed. This audit measures local runtime
readiness connector-by-connector.

It performs:
- local executable discovery
- local --version/--help smoke probes
- API/config key PRESENCE checks (never values)
- conservative classification:
  READY / PARTIAL / BLOCKED / UNKNOWN

It performs NO:
- network requests
- OSINT searches
- database writes
- credential output

Run:

    cd C:\osintxz
    & .\.venv\Scripts\python.exe .\tools\osint_runtime_capability_audit.py

Outputs:

    storage\cache\osint_runtime_capability_audit\runtime_audit.json
    storage\cache\osint_runtime_capability_audit\runtime_audit.md

After this audit, the next block will install/enable the highest-value free
runtime tools first, prioritizing discovery and archival intelligence over
vulnerability scanning.

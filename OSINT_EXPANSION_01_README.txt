OSINT Intelligence Platform
OSINT Expansion 01 — Free Maximum Coverage Audit

This is the first block after the post-Astra stable baseline.

It changes no production code and performs no network requests.

Run:
    cd C:\osintxz
    & .\.venv\Scripts\python.exe .\tools\osint_free_maximum_audit.py

Outputs:
    storage\cache\osint_free_maximum_audit\audit.json
    storage\cache\osint_free_maximum_audit\audit.md

The audit measures, per target type:
- dedicated source/provider components
- routing/capability path
- persistence/provenance path
- recursive pivot path
- content extraction/hydration path
- automated test coverage
- locally installed tools

Targets:
username, email, phone, domain, ip, url, person, company, document, location

The resulting priority order determines which OSINT target we improve first.

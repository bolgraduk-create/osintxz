OSINT Intelligence Platform
OSINT Expansion 05D — Controlled HTTP Discovery Chain

05C status:
- 6 targeted tests passed
- HTTPX production_available=True
- GHunt production_available=True
- full suite: 629 passed

05D changes no production code.

It performs a bounded live integration chain using current production wrappers:

    example.com
        ↓
    Subfinder + Assetfinder
        ↓
    max 3 host candidates
        ↓
    DNSX
        ↓
    HTTPX
        ↓
    GAU + Waybackurls
        ↓
    Katana

Every ConnectorRequest uses:
    limit = 3

Timeouts are bounded per tool.

No:
- DB writes
- persistence
- recursive enrichment
- vulnerability scanning

Run:

    cd C:\osintxz

    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"

    & .\.venv\Scripts\python.exe .\tools\osint_http_discovery_chain_05d.py

Output:

    storage\cache\osint_expansion_05d\http_discovery_chain.json

Expected terminal state:
    OSINT EXPANSION 05D HTTP DISCOVERY CHAIN: PASS

PARTIAL is acceptable for transient public-source failures and will tell us
exactly which stage needs hardening next.

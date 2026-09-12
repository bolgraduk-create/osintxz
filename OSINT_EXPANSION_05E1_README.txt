OSINT Intelligence Platform
OSINT Expansion 05E1 — Persistence / Entity / Pivot Contract Probe

Current verified baseline:
- 05D3 targeted: 20 passed
- live discovery chain: PASS
- full suite: 634 passed

Verified live chain:
    discovery -> DNS -> HTTP -> archive -> crawl

05E goal:
Wire the verified discovery chain into:
    findings -> persistence -> evidence -> entities -> recursive pivots

05E1 changes NO production code.

It captures the exact current post-04G2/post-05D3 contracts for:
- OsintEnrichmentService
- OsintRecursiveEnrichmentService
- EnrichmentExecution
- FindingPersistence
- NewEntityBudget
- Pivot candidates/policy/router
- relevant entity/evidence services and models

Run:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe .\tools\osint_persistence_pivot_contract_probe_05e1.py

Upload BOTH:
    storage\cache\osint_expansion_05e1\persistence_pivot_contract.json
    storage\cache\osint_expansion_05e1\osint_05e1_persistence_pivot_bundle.zip

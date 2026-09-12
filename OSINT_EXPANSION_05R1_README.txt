OSINT Intelligence Platform
OSINT Expansion 05R1 — Recursive E2E + Desktop UI Wiring Contract Probe

Current verified state:
- live discovery chain: PASS
- persistence -> Source/Evidence/Entity/EvidenceEntity: PASS
- pivot candidates: PASS
- PostgreSQL idempotency + rollback: PASS
- recursive budgets/policy: already tested

05R goal:
Prove one connected LIVE recursive investigation and determine whether the
desktop application already launches that same recursive production service.

05R1 makes NO production changes and performs NO network/DB operations.

It inspects:
- OsintRecursiveEnrichmentService
- OsintEnrichmentService
- enrichment execution
- pivot candidate/policy/router
- ServiceContainer definitions
- desktop/interface/application call sites

Run:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe .\tools\osint_recursive_ui_contract_probe_05r1.py

Upload BOTH:
    storage\cache\osint_expansion_05r1\recursive_ui_contract.json
    storage\cache\osint_expansion_05r1\osint_05r1_recursive_ui_bundle.zip

Then 05R2 will:
- run a benign real recursive seed such as example.com;
- prove at least one second-level pivot executes;
- keep max_depth/max_pivots/max_new_entities policy active;
- use a temporary DB Case + rollback;
- patch UI only if the existing desktop path does not call recursion.

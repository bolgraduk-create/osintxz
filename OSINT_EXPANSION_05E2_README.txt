OSINT Intelligence Platform
OSINT Expansion 05E2 — Discovery Persistence / Entity / Pivot Integration

Current verified baseline:
- 05D3 targeted: 20 passed
- live discovery chain: PASS
- full suite: 634 passed

05E1 confirmed the existing production architecture:
    EnrichmentExecution
        -> OsintFindingPersistenceService
        -> Source / Evidence / Entity / EvidenceEntity
        -> OsintPivotCandidatePolicy
        -> Recursive enrichment

05E2 fixes one real integration gap:
the verified live discovery chain emits categories that the persistence entity
extractor did not fully understand.

Added persistence semantics:
- subdomain -> DOMAIN (existing)
- dns -> DOMAIN
- dns metadata A/AAAA/host_ip/ip -> validated IP entities
- http -> URL
- http metadata A/AAAA/host_ip/ip -> validated IP entities
- endpoint -> URL
- historical_url -> URL (explicit mapping)

Evidence semantics:
- dns -> METADATA
- http -> LINK
- endpoint -> LINK
- historical_url -> LINK

Important:
- Raw findings still NEVER become recursive pivots directly.
- Only persisted Entity objects become pivot candidates.
- NewEntityBudget remains the hard creation boundary.
- Invalid metadata strings cannot become IP entities.
- Existing Source/Evidence/Entity idempotency remains unchanged.

Changed production file:
    app/osint/finding_persistence.py

Added tests:
    tests/test_osint_persistence_entity_pivot_integration.py

Run:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe -m pytest `
        .\tests\test_osint_persistence_entity_pivot_integration.py `
        .\tests\test_osint_recursive_budget_wiring.py `
        .\tests\test_osint_recursive_controlled_simulation.py -q

Then broader persistence/pivot regression:

    & .\.venv\Scripts\python.exe -m pytest .\tests -q `
        -k "osint and (persistence or entity or pivot or recursive or enrichment)"

Finally:

    & .\.venv\Scripts\python.exe -m pytest -q

If all tests are green, the next block is 05E3:
a controlled transactional DB integration gate using a temporary Case and
rollback, proving the same path against PostgreSQL without leaving test data.

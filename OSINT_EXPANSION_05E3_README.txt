OSINT Intelligence Platform
OSINT Expansion 05E3a — Transactional PostgreSQL Persistence/Pivot Gate

Current baseline:
- 05D live discovery chain: PASS
- 05E2 completed by user
- last explicitly reported full suite before 05E2: 634 passed

05E3 modifies NO production files.

It proves the current production persistence stack against the REAL PostgreSQL
schema, while leaving no test data behind.

Contract:
    synthetic discovery findings
        -> OsintFindingPersistenceService
        -> Source
        -> Evidence
        -> Entity
        -> EvidenceEntity
        -> OsintPivotCandidatePolicy

Expected pivot types:
    DOMAIN
    IP
    URL

Safety:
- no external OSINT calls
- no destructive SQL
- an OUTER SQLAlchemy transaction wraps the entire test
- a temporary Case is created inside that transaction
- the transaction is rolled back
- a fresh DB session verifies that the Case and all child rows are gone

It also persists the same execution twice inside the transaction and requires
the second pass to create zero duplicate Source/Evidence/Entity/link rows.

Run:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe .\tools\osint_postgresql_transaction_gate_05e3.py

Expected ending:

    IN-TRANSACTION CONTRACT: PASS
    case_exists=False
    surviving_counts={'sources': 0, 'evidences': 0, 'entities': 0, ...}
    OSINT EXPANSION 05E3 POSTGRESQL TRANSACTION GATE: PASS

Output:

    storage\cache\osint_expansion_05e3\postgresql_transaction_gate.json

After 05E3:
    05F0 — Chat Participant Identity Resolution

05F0 will correlate:
- stable Telegram/user IDs when present
- @username/current or historical username
- account display name / first_name / last_name
- chat/export participant labels and local nicknames
- message authorship/context

It will output confidence + provenance and preserve ambiguous matches instead
of silently merging people.


05E3a FIX
---------
The first 05E3 run correctly reached PostgreSQL and created the temporary Case,
but the diagnostic script attempted to synthesize OsintConnectorCapability and
did not provide the required ConnectorDisposition enum.

05E3a does NOT touch production code.

It now resolves the exact immutable production metadata using:
    app.osint.capabilities.get_capability()

Catalog entries used:
    assetfinder_connector
    dnsx_connector
    httpx_connector
    katana_connector
    gau_connector

This is both simpler and architecturally correct: provenance now uses the same
capability objects as the production router.

Run exactly:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe .\tools\osint_postgresql_transaction_gate_05e3.py


05E3b FIX
---------
The second run reached the real capability catalog correctly, but the
diagnostic still compared a guessed class name ("GAUConnector") against the
catalog's actual class name ("GauConnector").

05E3b removes this artificial class-name check entirely.

The module capability entry returned by get_capability() is authoritative.
No production code is changed.

Run:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe .\tools\osint_postgresql_transaction_gate_05e3.py

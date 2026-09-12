OSINT Intelligence Platform
OSINT Expansion 05R3c2 — Evidence -> Entity Candidate Diagnostic

Correction after reviewing the 05R3b UI result:
- OSINT findings: 5
- OSINT Evidence created: 5
- Entity created: 0
- Recursive candidates: 0

Therefore recursion had nothing to enqueue.

05R3c inspected zero Entity rows, but that was not enough to diagnose the
reason. 05R3c2 anchors itself to the newest OSINT Evidence instead of the
latest Case.updated_at and reconstructs the exact findings from Evidence
provenance.

It calls the real production:
    OsintFindingPersistenceService._entity_candidates()

For each Evidence it prints:
    connector
    finding category
    value
    URL
    predicted Entity candidates
    actually linked Entity rows

This distinguishes:
A) mapping gap:
       predicted_candidates = 0
B) persistence/budget bug:
       predicted_candidates > 0
       actual links = 0
C) healthy persistence:
       predicted_candidates > 0
       actual links > 0

NO writes.
NO network.

INSTALL / RUN
-------------
Extract into:
    C:\osintxz

Run:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe .\tools\osint_evidence_candidate_diagnostic_05r3c2.py

Upload:
    storage\cache\osint_expansion_05r3c2\evidence_candidate_diagnostic.json

Paste the console output too.

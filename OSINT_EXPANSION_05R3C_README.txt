OSINT Intelligence Platform
OSINT Expansion 05R3c — Recursive Candidate Diagnostic

Observed after 05R3b:
    OSINT findings: 5
    New Entity: 5
    Recursive targets processed: 1
    Recursive candidates: 0
    enqueued: 0
    stop: queue_exhausted

This means budget fairness is fixed, but the five persisted Entity objects did
not become recursive candidates.

05R3c is READ ONLY.

It prints:
- Entity type
- Entity value
- originating connector
- finding category
- EvidenceEntity link count
- whether OsintPivotCandidatePolicy accepts it
- resulting pivot target type

Run:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe .\tools\osint_recursive_candidate_diagnostic_05r3c.py

Upload:
    storage\cache\osint_expansion_05r3c\candidate_diagnostic.json

Also paste the console output.

Do not change production code before this diagnostic identifies the exact
entity-type mismatch.

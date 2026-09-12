OSINT Intelligence Platform
OSINT Expansion 05R2 — Controlled LIVE Recursive E2E Gate

05R1 findings:
- OsintRecursiveEnrichmentService exists in the production ServiceContainer.
- Case Workspace Investigation Search has a checkbox:
      "Автоматически продолжать поиск по найденным сущностям"
- current UI recursion goes through OpenWebRecursivePivotService.
- the general OSINT Workspace still runs one-shot OsintPipeline targets.
- EMAIL/USERNAME recursive expansion is explicitly deferred by the current
  InvestigationSearchWorker.

05R2 changes NO production files.

Goal:
Prove one REAL second-level OSINT pivot independently of the UI.

Path:
    example.com
        -> live passive/public connector
        -> Finding
        -> real PostgreSQL Source/Evidence/Entity/EvidenceEntity
        -> recursive candidate
        -> SECOND live OSINT target

Live network access is deliberately restricted in this gate to:
    crt.sh
    GAU

Everything else selected by the production router is treated as unavailable.

Additional bounds:
    per-live-connector findings: 3
    per-live-connector timeout: <=18 seconds
    max_depth: 2
    max_pivots_per_entity: 3
    max_new_entities: 20

A temporary Case is wrapped in an outer SQLAlchemy transaction and rolled back.
A fresh DB session must show zero surviving rows.

Run:

    cd C:\osintxz

    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"

    & .\.venv\Scripts\python.exe .\tools\osint_live_recursive_e2e_05r2.py

Ideal ending:

    second_level_runs=1 or more
    case_exists=False
    surviving_counts={... all zeros ...}

    OSINT EXPANSION 05R2 LIVE RECURSIVE E2E: PASS

PARTIAL means live collection/persistence worked but current public-source
responses did not produce a second-level candidate during that run.

Output:
    storage\cache\osint_expansion_05r2\live_recursive_e2e_gate.json

After PASS:
05R3 will make the desktop recursive checkbox use the root production recursive
service directly, instead of limiting recursion to the Open-Web bridge only.
The Open-Web layer will remain available as a separate source.

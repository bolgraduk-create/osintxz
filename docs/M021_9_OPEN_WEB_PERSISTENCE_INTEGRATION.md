# M021.9 — Open-Web Discovery → Extraction → Persistence

Production chain:

`OpenWebQuery`
→ `OpenWebDiscoveryService`
→ `OpenWebDocument`
→ `OpenWebIdentifierExtractionBridge`
→ `OsintFinding`
→ `OsintFindingPersistenceService`
→ `Source / Evidence / Entity / EvidenceEntity`

M021.9 adds a generic `persist_findings()` entry point to the existing M021.3
persistence service. It delegates every finding to the same `_persist_finding()`
implementation used by connector execution, so there is no second persistence
implementation.

Open-Web findings are grouped by provider before persistence. This preserves
independent evidence provenance when two public providers expose the same
identifier. Entity Resolution can still converge both pieces of evidence on
the same canonical Entity.

`DiscoveryGoal.OPEN_WEB_DISCOVERY` is used as the provenance goal.

No ownership relationship inference, recursive execution, network provider,
transaction commit, or database migration is added in this block.

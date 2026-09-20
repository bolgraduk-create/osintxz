# OSINTXZ R13.21.2 — Strict Identity & Pre-Persistence Relevance Gate

This hotfix tightens the live Investigation Search after R13.21.1.

## What changes

- Person-name matching ignores query/search/target echo metadata.
- A different surname can no longer become a `Full name match` merely because an upstream response repeats the original query.
- Identity scoring is limited to person-like records (person, researcher, public user/profile, sole trader, etc.). Publications, datasets and documents can remain useful search candidates, but they do not appear as people in the Identity view.
- Adds a dedicated **Candidates** tab. Review-only candidate records no longer occupy the normal Results list.
- Adds an optional pre-persistence finding gate to the existing OSINT persistence service. It is enabled only by Unified Investigation Search.
- Exact targets (username, email, phone, domain, URL, IP and hash) must be demonstrably present in a finding before that finding can create Source/Evidence/Entity records.
- Classic OSINT/Open-Web recursion therefore follows only findings that passed the same persistence relevance boundary.
- Raw provider output remains available even when a finding is not persisted.

## Safety / architecture

- No database migration.
- No new database tables.
- No source/API changes.
- Existing OSINT workflows keep their previous persistence behaviour because `finding_gate` defaults to `None`.
- The unified worker uses its own ServiceContainer/session and installs the gate only inside that run.
- Gate exceptions fail closed for persistence but do not erase raw provider output.
- No secret/raw credential storage is introduced.

## Expected effect on the Linus Torvalds test

- `Dr. Linus Orokpo Idoko`, `Linus Schrage`, etc. must not be full-name matches.
- DataCite publications/datasets must not appear as Identity people.
- The GitHub public profile can remain a person-like identity candidate.
- Candidate-only publications/data move to Candidates/Raw rather than normal Results.
- Evidence/Entity creation should drop substantially because unrelated recursive findings are rejected before persistence.

# OSINTXZ R13.23 — Person Intelligence Card v2

This package upgrades the existing PERSON card without changing the database, persistence model, connectors, source policies, or evidence semantics.

## Added / changed

- Adds **Intelligence Summary** with counts for Accounts, Contacts, Organizations, Locations, Evidence, and Review candidates.
- Adds **Core Intelligence** grouped into Contacts, Organizations, Locations, and Web & Technical identifiers.
- Renames **Profiles & Accounts** to **Accounts & Profiles**.
- Renames **Related Identifiers** to **Intelligence Attributes** and keeps provenance / analyst-selected / manual labeling.
- Clarifies that the existing confidence field is **Entity confidence**, not proof of identity.
- Preserves the existing Add item and From intelligence workflows.
- Keeps photo/file handling, supporting evidence, provenance warnings, and person/account separation intact.

## Not changed

- No database migration.
- No Entity/Evidence/Source schema changes.
- No automatic identity verification.
- No connector changes.
- No API keys or external requests.
- No deletion or rewriting of existing investigation data.

## Prerequisite

R13.22 must already be installed. The installer verifies that the Search page contains the Mentions UI.

## Install

```powershell
python .\OSINTXZ_R13_23_PERSON_CARD_V2\install_r13_23_person_card_v2.py C:\osintxz --run-tests
```

Backups are written under `storage/patch_backups/r13_23_*`.

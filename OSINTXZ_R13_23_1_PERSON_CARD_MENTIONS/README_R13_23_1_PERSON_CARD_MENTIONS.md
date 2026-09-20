# OSINTXZ R13.23.1 — Person Card Polish + Mentions Integration

This hotfix connects R13.22 Corroborating Mentions to R13.23 Person Intelligence Card v2 and fixes the card layout/review count observed during manual testing.

## Added / changed

- Fixes `Intelligence Summary` vertical overflow by giving metric cards enough content height.
- Adds a **Mentions** summary metric.
- `Review` now counts only unlinked candidates whose exact `origin`, `value`, or URL is already connected to the current PERSON; unrelated case-wide OSINT candidates are no longer counted as this person's review queue.
- Splits the old `WEB & TECHNICAL` group into **WEB PROFILES / PAGES** and **TECHNICAL**.
- Avoids duplicating an already-linked account/profile URL in Core Intelligence.
- Adds **Corroborating Mentions** to Person Card v2.
- Adds **Add to person** on Search → Mentions.
- The analyst selects a PERSON from the current investigation before saving a mention.
- A saved mention creates provenance using the existing `Source -> Evidence -> EvidenceEntity` model with workflow `person_mention_selection`.
- Persists only bounded safe mention fields: title, public HTTP(S) URL, source, detail, score, matched signals, lane/status.
- Duplicate attachment of the same mention to the same PERSON is idempotent.
- A mention must contain at least two matched signals before it can be saved.
- The action explicitly records analyst relevance and does **not** mark identity as verified.
- Installer prefers `C:\osintxz\.venv\Scripts\python.exe` for compile/tests, fixing the R13.23 system-Python/pytest issue.

## Not changed

- No database migration.
- No new database table.
- No connector/source routing changes.
- No changes to R13.21.2 pre-persistence relevance gates.
- No automatic PERSON/account ownership assertion.
- No raw secret values are persisted.
- Existing manual attachments, photos, profile selections and supporting Evidence remain untouched.

## Installation

From the OSINTXZ project root:

```powershell
python .\OSINTXZ_R13_23_1_PERSON_CARD_MENTIONS\install_r13_23_1_person_card_mentions.py C:\osintxz --run-tests
```

The installer creates a timestamped backup under:

```text
storage/patch_backups/r13_23_1_YYYYMMDD_HHMMSS_xxxxxx/
```

## Manual verification

1. Open **Search** and run a query that produces at least one item in **Mentions**.
2. Open **Mentions** and press **Add to person**.
3. Select a PERSON from the current case and save.
4. Open that PERSON card.
5. Confirm the new **Corroborating Mentions** section contains the linked mention, matched-signal summary and mention score.
6. Confirm `Intelligence Summary` no longer overlaps `Core Intelligence`.
7. Confirm `Review` is no longer the count of all unlinked OSINT entities in the case.
8. Confirm Core Intelligence has separate **WEB PROFILES / PAGES** and **TECHNICAL** groups.

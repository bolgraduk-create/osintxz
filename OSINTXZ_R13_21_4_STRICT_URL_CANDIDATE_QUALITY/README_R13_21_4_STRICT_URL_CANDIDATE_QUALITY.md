# OSINTXZ R13.21.4 — Strict URL Relevance & Candidate Quality

Focused hotfix on top of R13.21.3.

## Added / changed

- Removed the remaining URL-route fallback that could promote unrelated GAU/Wayback/Common-Crawl-style URLs into Clean merely because a historical-web provider ran for a URL seed.
- URL pivots are now scoped: an exact URL or a descendant of the searched profile/path may remain relevant; another account/path on the same host is Raw-only.
- Username evidence is stricter at the persistence gate: the username must occupy an account-owner/profile path position (`/torvalds/...`, `/users/torvalds/...`), not an arbitrary deep URL segment.
- Identity-review rows are no longer duplicated in the generic Candidates tab.
- Person-name document/archive candidates require the structured matched-person marker produced from `author/creator/person` data before they remain reviewable. Query echoes and generic title/body matches are Raw-only.
- The Identity summary card keeps the existing `Identity Leads` title for compatibility but now shows total identity rows and a clearer `supported / review / conflicts` breakdown.

## Not changed

- No database migration.
- No connector/API-key changes.
- R13.21.2 pre-persistence Evidence/Entity gate remains enabled and is not weakened.
- Related Accounts remain signals, not identity proof.
- Raw results are retained for analyst review.

## Verification

The package runs `py_compile` and a regression gate covering R13.20.1 through R13.21.4 plus available Common Crawl, persistence, recursion and QML bridge tests.

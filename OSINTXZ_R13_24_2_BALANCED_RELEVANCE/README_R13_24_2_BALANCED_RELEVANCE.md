# OSINTXZ R13.24.2 — Balanced Relevance

This hotfix loosens analyst visibility without weakening persistence or automatic pivots.

## What changes

- `Results` remains the strict high-confidence view.
- `Possible` now also accepts exact-identifier results when the returned record has a real, inspectable relation to the searched value.
- Exact username findings may appear in `Possible` when the username is present in the record/URL or a username-checking connector explicitly reports a positive account observation.
- URL seeds may surface same-host pages as `Possible` even when they are outside the strict path scope.
- Domain seeds may surface matching subdomains as `Possible`.
- Email/phone/hash/CVE/DOI/etc. still require the searched identifier itself or a positive structured account observation where appropriate.
- Explicit negative results (`available=true`, `match=false`, conflicting data) remain suppressed.
- Completely unrelated URLs/records remain suppressed.

## What does NOT change

- Pre-persistence relevance gate.
- Evidence/Entity creation rules.
- Automatic pivot rules.
- Connector configuration or source count.
- Database schema or migrations.

The intent is: **show related leads, trust only verified/strict matches**.

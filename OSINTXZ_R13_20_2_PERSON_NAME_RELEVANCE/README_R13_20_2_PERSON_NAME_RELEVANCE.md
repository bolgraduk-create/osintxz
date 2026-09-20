# OSINTXZ R13.20.2 — Person Name Relevance Hotfix

## Problem fixed
R13.20 unified person-name search could accept upstream token-OR results. A query such as
`Марк Кириченко` could therefore surface people who only shared the surname, or records
matching only `Марк` (for example Mark Twain works/authors).

## What changed
- Adds a strict person-name relevance layer before automatic pivots.
- A two-part name requires both name tokens; order does not matter.
- A three-or-more-part name requires first + last; patronymic/middle-name is optional.
- Supports conservative Cyrillic/Latin transliteration matching (e.g. Кириченко ↔ Kirichenko/Kyrychenko).
- Structured author/creator/name metadata can validate a record even when the record title is a publication title.
- Name-search records rejected by relevance stay available in Raw results but are suppressed from Clean.
- Rejected name rows can never generate recursive pivots.
- Generic `archive_search`/`keyword` capabilities are no longer automatic for PERSON_NAME. Use the explicit Keyword field for broad archive discovery.
- Positive name relevance is still only a candidate match; it does not prove identity.

## Not touched
- Database schema / migrations.
- Existing stored Evidence/Entity/Source data.
- OSINT connector implementations.
- Registry provider implementations.
- API credentials/configuration.
- Raw-result inspection mode.

## Tests
`tests/test_r13_20_2_person_name_relevance.py` covers:
- full two-token matching;
- same-surname rejection;
- Mark Twain-style first-name-only rejection;
- reversed-name order;
- Cyrillic/Latin transliteration;
- optional patronymic/middle-name;
- structured author metadata;
- Clean-vs-Raw semantics;
- pre-pivot filtering;
- automatic capability routing.

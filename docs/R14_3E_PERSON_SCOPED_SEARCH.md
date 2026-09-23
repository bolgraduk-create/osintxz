# R14.3e — PERSON-Scoped Search & People Directory

R14.3e changes the user-facing investigation model without deleting the
technical Entity graph.

## Entity Directory

The desktop Entity Directory now displays only PERSON entities.

Email, phone, username, account, URL, domain, IP, location and other technical
Entity rows are still persisted internally because they are required for:

- Source -> Evidence -> Entity provenance;
- deduplication;
- graph analysis;
- pivots;
- identity resolution;
- Person Card data.

They are no longer presented as top-level investigation subjects.

## Creating people

A PERSON can now be created:

- from the People directory with Add Person;
- directly from Investigation Search with + New Person.

PERSON creation deliberately does not deduplicate only by normalized name.
Different people may have the same name.

## Search target requirement

All-source Investigation Search now requires an explicit PERSON target before it
can run.

The selected PERSON must:

- exist;
- be a PERSON entity;
- belong to the same investigation.

The worker validates these rules again in its own thread.

## Search attribution

All persisted Evidence produced by Classic/Open-Web search is linked to the
selected PERSON.

Persisted technical entities are additionally grouped under one append-only
person_search_attribution Evidence item.

This means:

"collected while investigating this person"

not:

"verified to belong to this person".

Account ownership still requires the R14.3 Confirm / Review / Reject workflow.

## Person Card provenance

Technical values attached by a scoped search use the
search_attributed provenance label. Confirmed identity associations continue to
use analyst_confirmed.

## Registry and Federation

The current unified search workflow keeps Federation and Registry results
review-first/read-only where they were already read-only. Only actually
persisted data is attached to the PERSON.

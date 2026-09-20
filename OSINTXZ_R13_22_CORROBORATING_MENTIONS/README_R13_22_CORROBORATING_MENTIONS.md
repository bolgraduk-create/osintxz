# OSINTXZ R13.22 — Corroborating Mentions

## What this package changes

R13.22 adds a dedicated **Mentions** view to Unified Investigation Search.

A Mention is not a generic keyword result and not an identity assertion.
It is a content/page/document record that contains multiple independent
signals already known about the investigated person.

Examples:
- full name + organization;
- full name + username;
- full name + city/location;
- full name + another exact identifier;
- three independent contextual signals on a strongly relevant record.

A full-name-only publication remains a review Candidate, not a Mention.
Accounts remain in Accounts and person-like records remain in Identity.

## Search UI

The result tabs become:

Results | Identity | Candidates | Accounts | Mentions | Providers | Pivots | Errors

Mentions display:
- mention strength;
- which known signals matched;
- source and corroboration count;
- original URL when available.

Mention rows are separated from generic Results to keep the normal Clean
view compact.

## Safety / semantics

- A Mention does not prove identity or ownership.
- Weak keyword overlap is not enough.
- Candidate-only records require a direct full-name anchor.
- Existing pre-persistence relevance gates are unchanged.
- No database migration.
- No new external source.
- No bulk dataset download.

## Person Card

This package intentionally does not rewrite Person.qml. The existing card
already has working photo, accounts, identifiers and evidence/provenance.
The recommended next UI stage is Person Card v2 with structured sections:
Identity, Contacts, Accounts, Organizations, Locations, Mentions, Evidence,
Timeline and Relationships.

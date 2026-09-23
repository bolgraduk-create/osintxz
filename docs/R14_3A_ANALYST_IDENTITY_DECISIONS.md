# R14.3a — Analyst Identity Decisions

R14.3 begins human-in-the-loop identity resolution on the existing Person Card.

## Implemented

Candidate profile/account entities now support four states:

- UNREVIEWED — derived state; nothing has been decided yet;
- CONFIRMED — analyst states that the account/profile belongs to the PERSON;
- REVIEW — analyst wants more evidence before deciding;
- REJECTED — analyst states that the candidate does not belong to the PERSON.

Only CONFIRMED / REVIEW / REJECTED are persisted. UNREVIEWED is derived from
the absence of a decision.

## Persistence model

No parallel identity database was introduced.

Each decision creates append-only Source + Evidence provenance with workflow:

`person_identity_review`

The Evidence is linked to both:
- the PERSON entity;
- the reviewed account/profile entity.

Changing a decision creates a new Evidence record. The newest decision is the
effective state while older decisions remain available as audit history.

## Machine confidence remains independent

A manual CONFIRMED decision does not overwrite Entity.confidence.

The review Evidence stores the machine confidence observed at decision time so
the system can later explain:

- what the automated system believed;
- what the analyst decided;
- when the decision changed.

## Person Card behavior

CONFIRMED:
- persists the analyst decision;
- immediately reuses PersonProfileSelectionService;
- adds the account/profile to the Person Card;
- renders the relationship as analyst_confirmed.

REVIEW:
- remains in the identity review queue;
- is not treated as a confirmed account.

REJECTED:
- remains auditable;
- is suppressed from confirmed Person Card account/profile relations;
- can be reconsidered later by recording a new decision.

The current UI exposes Confirm / Review / Reject directly in the existing
From intelligence candidate dialog.

## Next R14.3 slices

R14.3b — Review queue and rationale UX:
- optional analyst note/reason;
- filters for Unreviewed / Needs review / Rejected;
- decision history drawer;
- undo by recording a new decision, never deleting history.

R14.3c — Relationship corroboration:
- known-associate overlap;
- direct/repeated interaction signals;
- shared-event signals;
- negative relationship evidence;
- provenance lineage so a signal cannot confirm itself circularly.

R14.3d — Identity calibration:
- combine deterministic identity, activity and relationship signals;
- conflict penalties;
- review benchmark corpus;
- calibrated WHY explanation.

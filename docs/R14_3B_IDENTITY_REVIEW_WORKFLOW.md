# R14.3b — Identity Review Workflow

R14.3b turns the R14.3a manual decision controls into a repeatable analyst
workflow without changing the Source -> Evidence -> Entity architecture.

## Added

The Person Card identity-review dialog now supports:

- status filters: All / Unreviewed / Needs review / Confirmed / Rejected;
- free-text filtering across candidate value, source, connector, status and
  analyst note;
- an optional analyst decision note;
- newest-first decision history;
- previous-decision display;
- machine-confidence snapshot beside each historical human decision;
- reconsideration of an already confirmed account without deleting history.

## Decision changes are append-only

Changing:

CONFIRMED -> REJECTED

does not edit or delete the original confirmation Evidence.

Instead a second `person_identity_review` Evidence row is created. The newest
decision is effective while the previous decision remains part of the audit
trail.

## Confirmed candidates remain reviewable

A confirmed profile is immediately linked to the Person Card, but it is not
removed from the identity-review workflow. This is required so an analyst can:

- inspect how the decision was made;
- add a reason;
- revise the decision later if contradictory evidence appears.

Already-linked non-identity data such as email, phone and organization records
continue to be suppressed from duplicate add workflows.

## Human vs machine state

The UI deliberately shows both:

- analyst decision;
- machine confidence captured at the time of the decision.

Human confirmation still does not rewrite the machine confidence value.

## Next slice

R14.3c — Relationship Corroboration:
- known-associate overlap;
- account interaction with confirmed associates;
- repeated interaction strength;
- shared-event corroboration;
- negative/conflicting relationship signals;
- provenance lineage and circular-confidence protection.

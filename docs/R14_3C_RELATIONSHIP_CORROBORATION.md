# R14.3c — Relationship Corroboration

R14.3c adds social-graph evidence as a bounded, explainable identity signal.

## Core rule

If the investigation already knows that PERSON A is associated with PERSON B,
and an account candidate for A is independently associated with the same
PERSON B, the candidate's effective confidence may increase.

This is supporting evidence only. It never proves account ownership by itself.

## Confidence separation

The persisted Entity.confidence remains unchanged.

The engine returns:

- base confidence;
- relationship support;
- effective confidence;
- confidence boost;
- supporting associate signals;
- suppressed circular signals.

The Person Card can therefore display values such as:

`63% -> 71%`

without rewriting the original machine observation.

## Correlation-safe aggregation

Each distinct shared associate contributes at most 25% of the remaining
uncertainty. Multiple associates use noisy-OR aggregation and the total social
support is capped at 45%.

This prevents dozens of correlated edges from linearly inflating identity
confidence.

## Provenance and circular-confidence protection

Relationship metadata is inspected for provenance identifiers including
Evidence, Source, message and finding IDs.

If both sides of a supposed corroboration come from the same provenance token,
that signal is suppressed entirely.

If provenance is missing, the signal is not treated as fully independent and is
downweighted.

## Supported inputs

Current R14.3c signals include:

- shared PERSON neighbors through persisted Relationship objects;
- candidate metadata references such as mentioned_entity_ids or
  related_entity_ids when they point to an already-known PERSON.

This makes the engine compatible with the future Account Activity Intelligence
stage: extracted comments/posts can later attach mentioned PERSON entity IDs and
feed the same corroboration logic.

## Relationship semantics

Stronger direct interaction types carry more weight, for example knows,
messaged, contacted, called and emailed. Generic related_to, membership,
location and unknown relations are intentionally weaker.

## Next slice

R14.3d will calibrate identity scoring across deterministic identifiers,
relationship corroboration, contradictions and later activity/event signals.

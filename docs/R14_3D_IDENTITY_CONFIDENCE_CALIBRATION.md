# R14.3d — Identity Confidence Calibration

R14.3d unifies machine identity confidence without merging human decisions into
the numeric model.

## Inputs

The calibrator can consume:

- persisted/base candidate confidence;
- deterministic IdentityResolution from the existing R13.21 engine;
- relationship corroboration from R14.3c;
- analyst review state from R14.3a/b.

The analyst decision is carried beside the machine score. It is never converted
into a numeric confidence contribution.

## Calibration model

Deterministic identity support is intentionally bounded:

- strong: at most 45% support;
- supported: at most 32%;
- possible: at most 15%;
- insufficient / not applicable / conflicting: no positive identity support.

Relationship support remains capped at the R14.3c ceiling of 45%.

Independent positive support is combined with noisy-OR and applied only to the
remaining uncertainty above the base confidence.

## Conflicts dominate corroboration

Soft identity conflicts apply a bounded penalty.

Hard identifier conflicts include:

- birth date;
- ORCID;
- NPI.

A hard conflict caps calibrated machine confidence at 25%, even if social-graph
support is strong.

A generic conflicting IdentityResolution is capped at 35%.

This prevents a known-associate overlap from overriding contradictory
high-value identity evidence.

## Name-only safety

An insufficient/name-only IdentityResolution contributes zero positive support.
It therefore cannot raise confidence by itself and cannot enable a pivot.

## Human decision separation

CONFIRMED and REJECTED are authoritative workflow decisions, but neither changes
the calibrated machine confidence.

Example:

- machine calibrated confidence: 71%;
- analyst decision: CONFIRMED.

The UI can show both facts without pretending the machine had 100% confidence.

## Person Card fields

Candidates now expose:

- baseConfidence;
- calibratedConfidence / effectiveConfidence;
- calibrationIdentitySupport;
- calibrationRelationshipSupport;
- calibrationConflictPenalty;
- calibrationHardConflict;
- calibrationPositiveSignals;
- calibrationNegativeSignals;
- calibrationReviewRequired;
- calibrationPivotAllowed;
- socialEffectiveConfidence for comparison with the R14.3c-only value.

## R14.3 exit condition

R14.3 is complete when R14.3d is green:

- manual Confirm / Review / Reject works;
- confirmed accounts bind immediately to Person Card;
- decision history is append-only;
- known-associate corroboration is provenance-safe;
- deterministic conflicts dominate social support;
- machine confidence and analyst decision remain separate;
- name-only evidence cannot silently establish identity.

After R14.3, the fixed production roadmap proceeds to R14.4 Registry Legal
Semantics before Account Activity Intelligence.

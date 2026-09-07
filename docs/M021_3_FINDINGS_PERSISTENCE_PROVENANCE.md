# M021.3 — Findings Persistence + Provenance

## Production contract

`OsintResult / OsintFinding -> Source(OSINT) -> Evidence -> Entity -> EvidenceEntity`

This block deliberately reuses the existing investigation domain model.

## Idempotency

A connector execution source receives a deterministic synthetic source path:

`osint://<connector>:<sha256(connector|target_type|target_value|goal)>`

A finding receives a deterministic evidence key over:

- source key
- category
- value
- provider/source
- URL
- stable JSON metadata

Repeat persistence reuses the same Source and Evidence.

Entity deduplication is delegated to the existing EntityService /
EntityNormalizer contract.

EvidenceEntity linking uses `EvidenceLinkService.ensure_link()`.

## Provenance

Evidence metadata stores:

- connector
- capability module
- finding index/category/value/source/URL
- connector confidence and reliability
- complete connector finding metadata
- originating target type/value
- discovery goal
- parent entity ID when available

The parent entity is linked to the Evidence itself. This records:

"this evidence was discovered while enriching this entity"

It does **not** assert:

"the discovered account/domain/URL belongs to this entity"

That stronger semantic relationship requires a separate, evidence-aware
relationship policy and is intentionally deferred.

## No migration

SourceType.OSINT, Evidence, Entity and EvidenceEntity already exist, so this
block introduces no database schema changes.

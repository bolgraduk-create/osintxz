# Block 10.10 — Structured Retrieval + Fusion Integration

## Purpose

Add the missing typed retrieval path to Unified Investigation Search.

Structured retrieval is intended for explicit database-backed questions such as:

- all `Entity` objects of type `bank_card` in a case;
- all `Entity` objects of type `phone` in a case;
- specific `Entity`/`Evidence` object IDs;
- evidence of a given type/source;
- exact persisted values or normalized Entity values.

It does **not** interpret natural-language intent. AI/query routing will be connected later.

## Canonical flow

`InvestigationSearchQuery -> StructuredSearchRetriever -> InvestigationSearchHit -> RankFusionService -> SearchRankingService -> InvestigationSearchResponse`

Structured results use the same stable identity as every other retriever:

`(case_id, object_type, object_id)`

Therefore an Entity found by both structured and lexical/semantic retrieval is fused into one hit instead of becoming a duplicate.

## Safety / identity rules

- every query is case-scoped;
- soft-deleted records are excluded unless explicitly requested;
- unknown Entity/Evidence types are rejected at the retriever boundary;
- AUTO text search does not dump every Entity merely because the structured retriever is registered;
- no fuzzy Entity merge is performed here;
- no AI inference is performed here.

## Database

No schema changes. No Alembic migration is required.

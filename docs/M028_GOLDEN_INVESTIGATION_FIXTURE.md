# M028 — Golden Investigation Fixtures

## Purpose

This fixture is the deterministic Stage 23 regression reference for the current
Investigation Engine foundation.

It verifies the integrated path:

Telegram JSON -> Message -> Extraction -> Entity Resolution -> Evidence provenance
-> Structured/Lexical/Fuzzy/Semantic signals -> Rank Fusion -> Mathematical Ranking
-> Confidence -> Explainability -> Unified Result.

## Stability rule

The golden gate is intentionally offline. It does not depend on Ollama, network
services, external APIs, or live embedding models. Those systems have their own
integration/performance tests and must not make the deterministic golden fixture
flaky.

## Fixture files

- `tests/fixtures/golden_investigation/result.json`
- `tests/fixtures/golden_investigation/expected.json`
- `tests/test_golden_investigation_fixture.py`
- `tools/run_stage23_integration_gate.py`

## Expected identity set

The fixture must produce exactly one canonical Entity for each expected
identifier type, while preserving repeated-occurrence provenance for the phone.

## Gate semantics

A PASS means the already implemented Stage 23 foundation remains integrated and
regression-safe. It does **not** mean every Stage 23 roadmap item is complete.
OSINT enrichment, Registry enrichment, quality calibration, AI routing, and other
unfinished roadmap items remain separate work.

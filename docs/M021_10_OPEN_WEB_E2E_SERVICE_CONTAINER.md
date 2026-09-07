# M021.10 — Open-Web E2E + ServiceContainer wiring

## E2E

The deterministic test executes:

`OpenWebQuery`
→ real `OpenWebProviderRegistry`
→ real `OpenWebDiscoveryService`
→ deterministic passive provider
→ real `OpenWebDocument`
→ real `UnifiedExtractionService`
→ real `OpenWebIdentifierExtractionBridge`
→ real `OsintFindingPersistenceService`
→ in-memory Source / Evidence / Entity / EvidenceEntity storage

It confirms public page content can create typed EMAIL / PHONE / URL entities
without network access.

A second complete run must not create duplicate Source, Evidence, Entity or
EvidenceEntity records.

## Composition root

ServiceContainer receives exactly one instance of:

- OpenWebProviderRegistry
- OpenWebDiscoveryService
- OpenWebIdentifierExtractionBridge
- OpenWebEnrichmentService

The extraction bridge reuses `self.unified_extraction_service`.
The enrichment service reuses `self.osint_finding_persistence_service`.

The Open-Web registry intentionally starts empty. Concrete providers are added
in later blocks.

No second OsintManager or OsintPipeline is created.
No recursive execution is added.
No database migration is required.

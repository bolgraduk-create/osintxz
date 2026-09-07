# M021.8 — Open-Web Document → Identifier Extraction Bridge

## Production flow

`OpenWebDocument`
→ `URL + title + snippet + text`
→ `UnifiedExtractionService.extract_text()`
→ `ExtractionCandidate[]`
→ deduplicate by `(entity_type, normalized_value)`
→ `OsintFinding[]`

The bridge does not persist anything. Existing M021 persistence remains the
single persistence path. It also does not infer account ownership,
relationships, or execute recursive pivots.

The page URL itself is included in the extraction text so it passes through
the same existing URL/domain extraction logic rather than being manually
invented as a separate candidate.

Finding confidence is conservatively capped by the Open-Web document
confidence. Provider reliability remains the finding reliability.

Every finding retains:
- provider
- document URL
- document metadata
- normalized identifier value
- extraction candidate metadata
- original OpenWebQuery target/depth/parent entity when provided

No network provider is added in M021.8.
No database migration is required.

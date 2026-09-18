# OSINTXZ — R13.12 Exposure Federation Core

Baseline: `main` at/after commit `b1426c026dbbf3715eca4951b7945f2f1096c146` (`Update project through R13.11`).

## Why this step

The project already had the pieces, but they were separated:

- R13.6: HIBP breach metadata + Pwned Passwords k-anonymity.
- R13.7: bounded public Tor v3 `.onion` observation.
- R13.9–R13.11: generic Remote Adapter Registry/Service.
- Legacy OSINT connectors: HIBP, Intelligence X, Holehe, Gitleaks/TruffleHog and others.

What was missing was one safe exposure-intelligence path that can combine breach metadata,
leak-index metadata and public dark-web observations without turning OSINTXZ into a store of
raw stolen credentials.

## Added

### 1. Exposure Federation Service

`app/exposure_intelligence/service.py`

Explicit target routing:

- email -> HIBP + Intelligence X metadata search
- domain -> Intelligence X metadata search
- URL -> Intelligence X metadata search
- IP -> Intelligence X metadata search
- phone -> Intelligence X metadata search
- crypto address -> Intelligence X metadata search
- onion URL -> Tor public-page observation

The service produces a normalized summary:

- total exposure records
- breach records
- dark-web records
- indexed leak/search records
- whether a password exposure was reported
- provider statuses
- whether raw secret values were stored (must remain false)

### 2. HIBP Remote Adapter

Wraps the already tested R13.6 service and exposes breach records through the generic
Remote Adapter contract.

It preserves useful facts such as `password_exposed=true`, breach/date/data classes, but
it does not return a password value.

### 3. Intelligence X Metadata Adapter

Implements the real asynchronous search lifecycle:

1. `POST /intelligent/search`
2. poll `GET /intelligent/search/result`
3. terminate unfinished searches when the local result limit is reached

The adapter is intentionally **metadata-only**. It does not call:

- `/file/read`
- `/file/view`
- `/file/preview`
- search export ZIP/content endpoints

It also deliberately drops upstream `name`, `description`, and tag text from persisted
records because those fields can contain fragments from indexed leaked documents.

The following metadata is retained when available:

- IntelX system/storage IDs
- bucket / bucket label
- timestamps
- size
- media/content type metadata
- access metadata
- X-score
- whether the bucket represents darknet content

IntelX is credential/contract gated and never runs automatically in a generic federation query.

### 4. Tor Public Adapter

Bridges the R13.7 `DarkWebIntelligenceService` into Remote Adapter Federation.

Existing R13.7 safety boundaries stay unchanged:

- public v3 `.onion` only
- local Tor SOCKS proxy only
- no authentication bypass
- no automatic redirects
- no binary/attachment downloads
- no direct-network fallback
- no raw HTML/page text persistence

### 5. Generic adapter execution policy

`RemoteSourceAdapter` gets `automatic_enabled`.

Adapters such as HIBP subscription lookup, Intelligence X and Tor observation set it to false.
They execute only when explicitly selected through `RemoteSourceQuery.sources`.

This prevents an unrelated generic search from unexpectedly:

- spending contract/API quota
- querying a privacy-sensitive exposure provider
- fetching a Tor page

### 6. Defense-in-depth sanitizer metadata

The generic Remote Adapter Service now records the number of redacted secret fields and always
marks the normalized provider result with:

`raw_secret_values_stored = false`

### 7. Exposure persistence

`app/exposure_intelligence/persistence.py`

Uses the existing `Source` + `Evidence` models. **No database migration.**

Persistence rules:

- sanitize again at the persistence boundary
- store exposure metadata as `EvidenceType.METADATA`
- deduplicate identical snapshots
- never auto-create/link a Person entity from an exposure hit
- never infer account ownership or person identity
- never persist raw password/token/cookie/private-key values
- preserve safe facts such as `password_exposed=true`

## Existing work confirmed during the audit

Already present/active before this patch:

- Federation Core and recursive secret sanitizer (R13.5)
- HIBP breach intelligence (R13.6)
- Tor public onion fetch/extraction (R13.7)
- 40+ source catalog / coverage model (R13.8)
- Remote Adapter Packs 1–3 (R13.9–R13.11)
- France, Australia ABN, Corporations Canada, UK Charity, Poland REGON
- SEC EDGAR, EU TED, SAM.gov, Trade.gov CSL
- GLEIF, VIES, OpenCorporates, Companies House, Poland KRS, CourtListener/RECAP
- legacy OSINT connectors including Intelligence X, HIBP, Holehe, TruffleHog and Gitleaks

## Still unfinished after R13.12

This patch is foundation, not the end of leak/dark-web coverage.

Next high-value blocks:

1. Replace/deprecate the legacy IntelligenceX connector in favor of the new metadata adapter.
2. Add additional lawful breach/exposure providers where API terms and access are clear.
3. Add paste/public-leak index adapters that return metadata/indicators without persisting raw secrets.
4. Add dark-web source discovery/index catalog instead of requiring the analyst to already know an onion URL.
5. Add UI integration for Exposure Intelligence and person/entity cards.
6. Add scheduled monitoring/change detection after the interactive search path is stable.

## Configuration

Add only real keys to your local `.env`, never to Git:

```env
HAVEIBEENPWNED_API_KEY=
INTELLIGENCEX_API_KEY=
INTELLIGENCEX_API_URL=https://2.intelx.io
DARKWEB_TOR_SOCKS_PROXY=socks5h://127.0.0.1:9050
```

For Intelligence X, use the official API instance assigned to your account/license.

## Install

With the OSINTXZ virtual environment active:

```powershell
cd C:\osintxz
python <EXTRACTED_PATCH_FOLDER>\install_r13_12_exposure_federation.py C:\osintxz --run-tests
```

The installer creates a backup under:

`storage/patch_backups/r13_12_<timestamp>/`

It precomputes all semantic text patches before changing the project so an incompatible
baseline fails before a half-installed patch is written.

## Test set

The installer runs:

```text
tests/test_r13_12_exposure_federation.py
tests/test_breach_intelligence_hibp.py
tests/test_darkweb_intelligence.py
tests/test_intelligence_source_federation.py
tests/test_remote_adapter_pack_1.py
tests/test_remote_adapter_pack_2.py
tests/test_remote_adapter_pack_3.py
```

The new tests cover:

- explicit vs automatic provider execution
- secret sanitization and redaction counters
- IntelX init + polling lifecycle
- `previewlines=0`
- no IntelX `/file/*` calls
- HIBP password-exposure fact without password value
- Tor observation without raw page body/text
- cross-source exposure summary
- catalog/coverage state
- persistence redaction and snapshot deduplication

## External API references checked for this patch

- Intelligence X API: `https://help.intelx.io/api/`
- Intelligence X SDK/OpenAPI: `https://github.com/IntelligenceX/SDK`
- HIBP API v3: `https://haveibeenpwned.com/API/v3`
- Tor onion services: `https://support.torproject.org/tor-browser/features/onion-services/`

# OSINTXZ — R13.5 Intelligence Source Federation Core

This patch creates the policy/catalog foundation for scaling OSINTXZ from a
small registry list to hundreds of remote intelligence sources.

It does **not** replace the existing execution systems:

- `RegistryProviderRegistry` continues to execute Registry Intelligence providers.
- `app.osint.registry.ConnectorRegistry` continues to execute OSINT connectors.
- the Federation Core is a cross-subsystem catalog/policy layer above them.

## What it adds

### Intelligence Source Catalog

A generic source descriptor records:

- source category
- capabilities
- country/global coverage
- transport
- access mode
- cost
- remote-query vs bulk-only delivery
- credentials requirement
- default sensitivity
- origin/provenance class
- redistribution policy
- documentation/terms metadata

This supports future sources such as:

- national/company registries
- SEC/TED/SAM and other open-data APIs
- sanctions/watchlists
- breach-intelligence APIs
- public dark-web observations
- research/charity/professional datasets
- archives and threat-intelligence sources

### Automatic-access policy

A source cannot become an automatic candidate when it is:

- bulk-download-only
- paid
- restricted/manual/contract access
- missing required credentials
- verified-scope access without verified scope

This is independent from provider implementation and does not bypass existing
Registry access controls.

### Data sensitivity policy

The core introduces:

- `PUBLIC`
- `PUBLIC_SENSITIVE`
- `BREACH_METADATA`
- `DARKWEB_PUBLIC`
- `RESTRICTED`
- `SECRET_MATERIAL`
- `PROHIBITED`

`SECRET_MATERIAL` may be detected transiently, but is not approved for
persistence, display, analysis or export.

### Secret sanitizer

The recursive sanitizer preserves useful intelligence such as:

```text
password_exposed = true
token_exposed = true
email = person@example.com
breach_name = ExampleLeak
```

while replacing raw secret values:

```text
password = [REDACTED]
access_token = [REDACTED]
session_cookie = [REDACTED]
private_key = [REDACTED]
```

It also handles nested dictionaries, lists/tuples and dataclasses.

## Defense in depth

The sanitizer is integrated at two Registry boundaries:

1. `RegistryIntelligenceService.search()` — before records are returned to UI/callers.
2. `RegistryPersistenceService.persist()` — before Evidence metadata is created.

Therefore a raw credential should not reach ordinary Registry search output or
immutable Evidence metadata even if a future provider accidentally returns one.

## Install

With `C:\osintxz\.venv` active:

```powershell
python .\install_source_federation_r13_5.py C:\osintxz --run-tests
```

No database migration and no new dependency are required.

## Next blocks

After this foundation:

- R13.6 Breach Intelligence adapters
- R13.7 Dark Web public-source/Tor transport
- R13.8 Massive remote-source catalog
- then deeper country/source integrations

# OSINTXZ — R5 OpenCorporates Registry Patch

Adds OpenCorporates as an optional Registry Intelligence aggregator provider.

## Access rule

The current OpenCorporates REST API requires an API token. This patch does not
add, generate, or embed a token.

Without `OPENCORPORATES_API_TOKEN`:
- the provider is registered;
- `requires_credentials=True`;
- the existing `RegistryQueryRouter` blocks automatic execution;
- all other Registry Intelligence providers keep working.

With a configured token:
- the provider becomes eligible under the existing router policy;
- no router or Registry contract change is needed.

## Supported queries

- `RegistryDomain.BUSINESS`
- `RegistryQueryKind.NAME`
- `RegistryQueryKind.REGISTRATION_ID`

Registration-number searches are restricted to OpenCorporates
`company_number`, then exact-matched again inside OSINTXZ.

## Provenance

OpenCorporates is kept as `RegistrySourceType.AGGREGATOR`, not promoted to an
official source. Returned records preserve OpenCorporates URL, registry URL,
source publisher/source URL/source retrieval time when supplied.

## Install

Extract this ZIP to a separate folder, activate `C:\osintxz\.venv`, then:

```powershell
python .\install_opencorporates_patch.py C:\osintxz --run-tests
```

The installer makes timestamped backups before modifying:
- `app/core/config.py`
- `.env.example`
- `app/core/service_container.py`

New files:
- `app/infrastructure/registries/opencorporates_client.py`
- `app/registry_intelligence/providers/opencorporates.py`
- `tests/test_registry_opencorporates.py`

No database migration or new dependency is required.

## Optional activation later

If you obtain a token, add it only to your local `.env`:

```text
OPENCORPORATES_API_TOKEN=your_token_here
```

Do not commit the real token.

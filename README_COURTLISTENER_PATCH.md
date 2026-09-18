# OSINTXZ — R10 CourtListener Patch

Adds CourtListener Legal Search API v4 as a Registry Intelligence provider for US case law.

## Scope

This R10 patch intentionally covers **case-law opinion clusters only** (`type=o`). It does not search PACER/RECAP; that remains R11.

Supported Registry queries:
- `COURT + CASE_NUMBER` — fielded `docketNumber` search plus exact normalized post-filter.
- `COURT/LEGAL + NAME` — fielded `caseName` search.

CourtListener is represented as `RegistrySourceType.AGGREGATOR`, not as an official government registry.

All records are `sensitive_legal_data=True`. A returned case or case-name hit is never treated as proof of identity, guilt, liability, or conviction. No legal outcome is inferred.

## Authentication

CourtListener v4 allows some unauthenticated experimentation, but its developer documentation recommends authentication for programmatic/deployed use. OSINTXZ therefore keeps automatic execution blocked until `COURTLISTENER_API_TOKEN` is configured.

The patch does not add a token.

## Install

Activate the project `.venv`, extract the ZIP, then run:

```powershell
python .\install_courtlistener_patch.py C:\osintxz --run-tests
```

The installer is idempotent and creates timestamped backups before changing:
- `app/core/config.py`
- `.env.example`
- `app/core/service_container.py`

New files:
- `app/infrastructure/registries/courtlistener_client.py`
- `app/registry_intelligence/providers/courtlistener.py`
- `tests/test_registry_courtlistener.py`

No DB migration and no new dependency are required.

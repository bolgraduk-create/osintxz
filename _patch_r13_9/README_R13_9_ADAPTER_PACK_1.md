# OSINTXZ — R13.9 Remote Adapter Pack 1

Five cataloged sources become real query adapters:

- Norway BRREG / Enhetsregisteret
- Czech ARES (exact ICO lookup in Pack 1)
- Crossref
- ROR
- OpenAlex

A small `RemoteSourceAdapterService` federates these adapters, isolates provider
failures and returns normalized records. This is an execution layer on top of
the R13.5/R13.8 catalog — not another catalog-only stage.

## OpenAlex

OpenAlex's current production API model uses free API keys / usage budgets.
The adapter is installed but returns NOT_CONFIGURED until:

OPENALEX_API_KEY=...

is configured.

## No migrations

No database migration and no new dependency.

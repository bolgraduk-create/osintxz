# OSINTXZ — R12 UK Companies House

Adds the official UK Companies House Public Data API to Registry Intelligence.

## Supported queries

- `BUSINESS + NAME`
  - `GET /search/companies`
- `BUSINESS + REGISTRATION_ID`
  - `GET /company/{companyNumber}`

The direct company-profile endpoint is used for registration-number queries so
the identifier is resolved exactly instead of relying on fuzzy search.

## Authentication

Companies House requires an API key for the Public Data API.

The patch adds only the configuration field:

```text
COMPANIES_HOUSE_API_KEY=
```

No key is bundled or invented.

Without a key:
- provider stays registered;
- `requires_credentials=True`;
- the current RegistryQueryRouter blocks automatic execution.

With a key:
- provider becomes automatically eligible;
- the key is sent using HTTP Basic authentication as the username with an
  empty password, matching Companies House documentation.

Do not commit a real key.

## Provenance

Records are marked:

```text
RegistrySourceType.OFFICIAL_API
country = GB
trust_score = 0.98
```

For exact company profiles, OSINTXZ preserves useful official fields such as:
- company status
- company type
- registered office address
- incorporation/cessation date
- SIC codes
- previous company names
- accounts summary
- confirmation statement summary

## Rate limit

The standard Companies House API limit is currently 600 requests in a
five-minute window. HTTP 429 is handled as a retryable partial provider result.

## Install

With the OSINTXZ virtualenv active:

```powershell
python .\install_companies_house_r12_patch.py C:\osintxz --run-tests
```

New files:
- `app/infrastructure/registries/companies_house_client.py`
- `app/registry_intelligence/providers/companies_house.py`
- `tests/test_registry_companies_house.py`

Patched:
- `app/core/config.py`
- `.env.example`
- `app/core/service_container.py`

No database migration is required.


## v2 recovery note

The v2 installer uses semantic Registry configuration anchors instead of the
decorative PostgreSQL section heading. It is safe to run after the first R12
installer copied the three new files and then aborted: those files are refreshed
and the remaining changes are applied idempotently.

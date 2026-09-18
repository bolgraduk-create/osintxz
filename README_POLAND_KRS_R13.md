# OSINTXZ — R13 Poland KRS

Adds the official Polish Krajowy Rejestr Sądowy (KRS) Open API.

## Scope

This first Poland provider intentionally supports exact KRS registration-number
lookups only:

- `BUSINESS + REGISTRATION_ID`
- `country = PL`

A short numeric KRS identifier is normalized to 10 digits.

The provider first requests register `P` (entrepreneurs). On HTTP 404 it retries
register `S` (associations, foundations and other entities). If both return 404,
the query is considered successfully completed with zero records.

## Source

Official Ministry of Justice KRS Open API:

`GET /api/krs/OdpisAktualny/{KRS}?rejestr=P|S&format=json`

No API key or login is required for this Open API.

The official portal states that personal names and PESEL values exposed through
the Open API are anonymized according to applicable rules.

## Provenance

Records use:

- `RegistrySourceType.OFFICIAL_OPEN_DATA`
- country `PL`
- trust score `0.98`
- exact KRS number as `registration_id`
- NIP and REGON when returned by the source

## Why name search is not in this first patch

The stable, officially documented Open API contract is exact KRS-number based.
R13 starts with that deterministic source instead of depending on a less stable
search endpoint. CEIDG for sole traders is also intentionally separate.

## Install

```powershell
python .\install_poland_krs_r13_patch.py C:\osintxz --run-tests
```

No database migration and no new dependency are required.

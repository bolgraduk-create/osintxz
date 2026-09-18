# OSINTXZ — R13.10 Remote Adapter Pack 2

This pack turns four more R13.8 catalog entries into real remote adapters.

## Added

- **SEC EDGAR** — exact CIK -> live submissions/company metadata. No bulk ZIPs.
  SEC requires `SEC_EDGAR_USER_AGENT` so OSINTXZ does not operate as an
  undeclared automated client.
- **EU TED** — keyless official v3 Search API. Pack 2 accepts the official TED
  expert-query string and returns a bounded first page of notices.
- **SAM.gov Entity Management v4** — partial company name or exact UEI. The
  adapter requests only `entityRegistration,coreData` public sections and
  never requests FOUO/Sensitive CUI. Requires `SAM_GOV_API_KEY`.
- **US Consolidated Screening List (CSL)** — name/fuzzy screening through
  Trade.gov. Requires `TRADE_GOV_API_KEY`.

## Screening safety

A CSL result is a screening candidate, not identity proof. Records contain:

- `candidate_only = true`
- `identity_confirmed = false`
- `restriction_status_inferred = false`
- `due_diligence_required = true`

The source list and provider score are preserved when supplied.

## Configuration

```text
SEC_EDGAR_USER_AGENT=OSINTXZ admin@example.com
SAM_GOV_API_KEY=
TRADE_GOV_API_KEY=
```

SEC is keyless. SAM.gov and Trade.gov keys are free account/API credentials and
are not bundled in the patch.

No database migration and no new Python dependency.

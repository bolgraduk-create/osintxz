# OSINTXZ — R13.15 Free Public Data Mega Pack 1

## What this patch adds

Seven real read-only adapters for large free/public datasets:

1. **Wikidata Entity Search** — names, persons, organizations, locations and exact QIDs.
2. **ORCID Anonymous/Public API** — public researcher profiles and ORCID identifiers.
3. **NIST NVD CVE API 2.0** — CVEs, keyword/product/vendor vulnerability search.
4. **openFDA** — drug labels, manufacturers, devices and enforcement records.
5. **OpenFEC** — candidates, committees and contribution metadata.
6. **ICIJ Offshore Leaks Reconciliation API** — candidate matches across Pandora Papers, Panama Papers, Paradise Papers, Bahamas Leaks and Offshore Leaks.
7. **US NPPES / NPI Registry** — public healthcare-provider and organization records.

## Safety / identity rules

- Name/fuzzy matches are **candidate-only** until independently resolved.
- ICIJ matches are never treated as proof that the investigation subject is the same person/entity or that they engaged in wrongdoing.
- NPI issuance is not treated as proof of current licensure or credential status.
- FEC adapter deliberately does not retain contributor street-address fields.
- Adapters are read-only and do not modify upstream systems.
- Existing secret sanitizer remains in the shared Remote Adapter service.
- No database schema change and no Alembic migration.

## Free-access behavior

- Wikidata: no key.
- ORCID: anonymous/public read-only endpoint; no key required for this adapter.
- NVD: no key required; optional key can increase practical quota.
- openFDA: works without a key at anonymous limits; optional free key increases daily quota.
- OpenFEC: uses the documented `DEMO_KEY` when no user key is configured; a free personal key can be supplied.
- ICIJ: no key.
- NPPES/NPI: no key.

Optional `.env` settings:

```env
NVD_API_KEY=
OPENFDA_API_KEY=
FEC_API_KEY=
```

## Install

From an activated OSINTXZ virtual environment:

```powershell
python .\OSINTXZ_R13_15_FREE_PUBLIC_DATA_MEGA_PACK_1\install_r13_15_free_public_data_mega_pack_1.py C:\osintxz --run-tests
```

The installer creates a backup under:

`storage/patch_backups/r13_15_<timestamp>`

## Why this step

R13.15 increases live free-source breadth without introducing a new database subsystem. The next logical step is **R13.16 Bulk Open Dataset Ingestion**: download, verify, index and incrementally refresh large public dumps such as ICIJ Offshore Leaks CSV and NPPES monthly/weekly dissemination files instead of depending only on remote query rate limits.

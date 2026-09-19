# OSINTXZ — R13.17 Low-Footprint Remote Data Mega Pack 2

R13.17 continues the low-disk strategy: more free public sources, no bulk datasets and no new database tables.

## Added sources

1. **RDAP.org bootstrap** — exact domain, IP and ASN registration-data lookup through the modern RDAP protocol.
2. **RIPEstat Data API** — exact IP/prefix and ASN overview information.
3. **PeeringDB guest API** — exact ASN/network metadata without requesting restricted contact data.
4. **Google Public DNS JSON API** — bounded A/AAAA/CNAME/MX/NS/TXT lookup with DNSSEC requested.
5. **USAspending.gov** — public U.S. federal-award recipient/organization search, including public UEI/DUNS identifiers when returned.
6. **Federal Register API** — metadata search across U.S. rules, notices and other Federal Register documents; PDFs are not downloaded.
7. **DataCite Public API** — DOI/research-output metadata, including datasets, publications and creators.
8. **Zenodo public records API** — published research-output metadata only; record files are not downloaded.
9. **Internet Archive Advanced Search** — item metadata search only; archive items/media are not downloaded.
10. **UN Security Council Consolidated Sanctions List** — explicit sanctions-name search only. The small official XML feed is read transiently in memory and is never written to disk.

## Low-footprint rules

R13.17 intentionally does not create a local data warehouse.

- No Alembic migration.
- No new database tables.
- No ZIP/CSV/JSON/XML dataset archives written to disk.
- No background synchronization.
- No downloaded PDFs, media, Zenodo files or Internet Archive items.
- Ordinary JSON API responses are bounded to small sizes and converted directly to `RemoteSourceRecord` objects.
- The UN sanctions XML is bounded to 4 MB, processed in memory and immediately discarded.
- `RemoteSourceAdapterService` keeps the existing federation sanitizer boundary.

## Identity / legal guardrails

- RDAP, RIPEstat, PeeringDB and DNS are exact technical-resource lookups; they do not establish ownership of a person.
- USAspending name matches are candidates, not proof that an organization is the same investigation entity.
- Federal Register name/organization searches are document mentions only.
- DataCite, Zenodo and Internet Archive fuzzy/name searches remain candidates until independently resolved.
- UN sanctions search is **not** registered for generic `name` capability. It runs only for explicit `sanctions_name`, `sanctions_entity` or `un_sanctions` queries.
- A sanctions-list name match is not proof that the investigation subject is the listed person/entity and must not be used to infer guilt or criminality.

## API / access notes

No new paid credentials are required for R13.17.

- RIPEstat exposes a public Data API.
- PeeringDB permits guest API queries without authentication, with lower rate limits and restricted contact visibility.
- Google Public DNS exposes a JSON DoH endpoint.
- USAspending endpoints currently require no authorization.
- DataCite Public API does not require authentication for metadata retrieval.
- Zenodo supports anonymous public record search with lower limits than authenticated use.
- Internet Archive Advanced Search returns JSON metadata.
- UN Security Council publishes the consolidated sanctions list as XML.

## Install

From the active project virtual environment:

```powershell
cd C:\osintxz
python .\OSINTXZ_R13_17_LOW_FOOTPRINT_REMOTE_MEGA_PACK_2\install_r13_17_low_footprint_remote_mega_pack_2.py C:\osintxz --run-tests
```

Backup is created under:

```text
storage/patch_backups/r13_17_YYYYMMDD_HHMMSS/
```

## Test gate

The new R13.17 unit gate contains **17 mocked tests**, so it consumes no live API quota. `--run-tests` also runs the existing R13.12–R13.16 regression gates and federation tests.

# OSINTXZ — R13.8 Massive Remote Source Catalog

Adds a cross-subsystem coverage catalog for 40+ remotely queryable intelligence sources.

## What changes

- adds implementation status (`active`, `existing_connector`, `cataloged`, `manual_assisted`);
- registers current Registry/Breach/Dark-Web sources in the Federation catalog;
- adds existing OSINT connectors to the same coverage view;
- catalogs the next remote-only sources without pretending adapters already exist;
- keeps bulk-only datasets out of this stage.

## New catalog candidates

Examples: SEC EDGAR, SAM.gov entities/exclusions/opportunities, US CSL, TED procurement, Norway BRREG, Czech ARES, France SIRENE, Australia ABN Lookup, Corporations Canada, UK Charity Commission, Poland REGON, Crossref, ROR, OpenAlex, ORCID, Wikidata SPARQL, NVD, openFDA, FEC, OpenSanctions and ICIJ Offshore Leaks (manual-assisted).

## Important

`cataloged` means the source is known and its access policy is modeled. It does **not** mean Search All already queries it. This prevents false coverage claims. Subsequent adapter packs promote entries to `active`.

No database migration and no new dependency.

# OSINTXZ — R13.16 Low-Footprint Remote Data Mega Pack

R13.16 replaces the postponed bulk-download stage. It expands free public data coverage while keeping local disk usage close to zero.

## Added sources

1. GitHub Public User API — exact public username profiles.
2. GitLab Public Users API — exact public username profiles.
3. Semantic Scholar Academic Graph — authors and papers.
4. Europe PMC — publications, authors, DOI and PMID search.
5. Library of Congress JSON API — archive / historical metadata search.
6. FBI Wanted Public API — explicit public-notice candidate search with legal-safety flags.
7. FIRST EPSS — exact CVE exploitation probability.
8. CIRCL hashlookup — exact MD5/SHA-1/SHA-256 known-file context.
9. Shodan InternetDB — free IP snapshot: ports, hostnames, CPEs, tags and CVE IDs.
10. CISA KEV — exact CVE lookup in the Known Exploited Vulnerabilities catalog.

## Storage policy

R13.16 does **not** download or build local bulk datasets.

- No new database tables or Alembic migrations.
- No background synchronization jobs.
- No downloaded ZIP/CSV/JSON dataset archives.
- No media/article/archive file downloads.
- API responses are bounded and mapped directly into RemoteSourceRecord objects.
- CISA KEV is read transiently in memory for an exact CVE lookup; the catalog itself is not written to disk or Evidence.
- Library of Congress returns metadata only; linked media/resources are not downloaded.
- Shodan InternetDB does not return service banners.
- RemoteSourceAdapterService's existing sanitizer still protects secret-like fields before results leave the federation boundary.

Only ordinary OSINTXZ evidence/results that the application explicitly persists can occupy normal project storage.

## Identity and legal guardrails

- GitHub/GitLab accounts are platform accounts, not automatic proof of a real-world person's identity.
- Semantic Scholar / Europe PMC author-name searches are candidates until independently resolved.
- FBI Wanted results are public notices only. A result must not be interpreted as proof of identity, guilt, conviction, or a legal outcome.
- CIRCL hashlookup provides known-file context; a match is not itself proof that a file is malicious.

## Install

From the project virtual environment:

```powershell
cd C:\osintxz
python .\OSINTXZ_R13_16_LOW_FOOTPRINT_REMOTE_MEGA_PACK\install_r13_16_low_footprint_remote_mega_pack.py C:\osintxz --run-tests
```

The installer creates a backup under:

```text
storage/patch_backups/r13_16_YYYYMMDD_HHMMSS/
```

## New test gate

The new R13.16 unit gate contains 17 tests and uses mocked HTTP transports, so it consumes no live API quota.

# OSINTXZ R13.20.1 — Result Cleanup / Consolidation Hotfix

This hotfix fixes noisy and repeated rows in the R13.20 Unified Investigation Search UI without reducing source coverage.

## What changes

- cross-source semantic deduplication: the same exact identifier found by multiple sources becomes one consolidated result;
- corroboration is preserved as `N sources` rather than discarded;
- URLs are canonicalized for display grouping (fragment/default port/tracking-only query differences do not create duplicates);
- exact identifiers such as email/domain/IP/hash/LEI/ORCID/NPI/CVE/DOI/case/registration IDs are normalized before grouping;
- registry/federation records sharing an exact identifier can merge even when display names differ;
- person and organization names are never fuzzy-merged merely because they look similar;
- obvious seed self-echo rows with no additional provenance/value are suppressed from the clean view;
- results receive a bounded presentation relevance score and are sorted by usefulness/corroboration/depth;
- Search UI defaults to `Clean`, with `Raw` available beside it for complete provider-level inspection;
- summary shows clean count, raw count, duplicates merged and low-value rows suppressed.

## What is not changed

- no database migration;
- no source/connector is disabled;
- no provider output is deleted from the raw view;
- no Evidence/Entity/Source persistence records are rewritten;
- no fuzzy identity resolution is introduced;
- no safety/access-policy behavior is weakened.

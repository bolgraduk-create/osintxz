# R14.2c — Untrusted File & Archive Boundaries

This slice hardens local file import before OSINTXZ begins the human identity
review work.

## Implemented boundaries

- imported source files are checked by a shared UntrustedFilePolicy;
- symbolic-link imports are rejected;
- a default 4 GiB single-file security ceiling exists even when the caller
  does not configure a smaller application-specific limit;
- generated managed-storage destinations are checked for root confinement;
- ZIP/TAR containers receive metadata preflight before import;
- absolute, drive-qualified and parent-traversal archive member paths are
  rejected;
- ZIP symbolic-link entries are rejected;
- TAR links, devices, FIFOs and other special entries are rejected;
- archive member count is bounded;
- single-member uncompressed size is bounded;
- total advertised uncompressed size is bounded;
- ZIP compression ratio is bounded;
- archive path depth and nested-archive candidates are bounded;
- RAR/7z/single-stream compressed formats remain opaque evidence;
- automatic extraction remains disabled for every imported archive.

## Important architectural decision

R14.2c does not add archive extraction. The current product did not need it for
the existing import contract, and adding extraction before a safe extractor is
available would increase attack surface. A future archive importer must consume
this policy and extract only into a freshly created confined directory.

## Default security limits

- file size: 4 GiB
- archive entries: 10,000
- single uncompressed member: 512 MiB
- total advertised uncompressed bytes: 2 GiB
- ZIP compression ratio: 250:1
- member path depth: 32
- nested archive candidates: 100

These are security ceilings. Individual import features may apply stricter
limits.

## Next stage

After this gate is green, development moves to R14.3 Human-in-the-loop Identity
Resolution:
- CONFIRMED / REVIEW / REJECTED / UNREVIEWED decisions;
- direct Person Card binding;
- analyst decision audit trail;
- social-graph corroboration;
- negative evidence and conflict handling;
- circular-confidence protection.

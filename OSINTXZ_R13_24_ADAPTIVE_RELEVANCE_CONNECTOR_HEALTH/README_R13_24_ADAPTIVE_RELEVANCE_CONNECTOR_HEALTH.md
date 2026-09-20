# OSINTXZ R13.24 — Adaptive Relevance + Connector Health & Repair

## What changed

- Adds an analyst-facing `Possible` tier between strict `Results` and `Raw`.
- Keeps exact identifiers (username/email/domain/URL/IP/hash/etc.) strict; `Possible` never bypasses the persistence or pivot gates.
- Adds provider health classification: READY, PARTIAL, TIMEOUT, NOT INSTALLED, NOT CONFIGURED, AUTH/POLICY, RATE LIMITED, ENDPOINT/QUERY, TEMPORARY FAILURE, EXPLICIT ONLY, FAILED.
- Repairs Sherlock fast-pass: removes obsolete `--no-txt`, separates per-site timeout from process budget, and keeps partial CSV findings after a timeout when available.
- Repairs Maigret fast-pass: bounded top-sites scan, short per-site timeout, no recursion/extraction, zero retries, partial JSON recovery.
- Repairs User Scanner launch: detects the Python module as well as the console executable, uses the project interpreter, avoids version-specific `-t`/`--no-nsfw` flags, and retains partial JSON when possible.
- Improves Wikidata client identification with a descriptive contactable User-Agent plus `Api-User-Agent`.
- Optional `--repair-tools` installs missing local CLI packages into the project `.venv`.

## What is intentionally unchanged

- R13.21.x strict pre-persistence relevance gate.
- Automatic pivot policy.
- Database schema and migrations.
- Raw secret handling and sensitive-source policy.
- Registry/exposure safety rules.

## Install

```powershell
python .\OSINTXZ_R13_24_ADAPTIVE_RELEVANCE_CONNECTOR_HEALTH\install_r13_24_adaptive_relevance_connector_health.py C:\osintxz --repair-tools --run-tests
```

`--repair-tools` is explicit: without it no packages are installed or upgraded.

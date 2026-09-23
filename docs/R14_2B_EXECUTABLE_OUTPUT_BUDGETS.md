# R14.2b — Executable Inventory & Output Budgets

Status: implemented on `feature/r14-2b-executable-output-budgets`.

## Security changes

All canonical OSINT CLI execution now provides:

- explicit approved executable inventory;
- absolute-path executable resolution before subprocess creation;
- current Python runtime exception for approved module-style connectors;
- no shell execution;
- bounded stdout capture (default 8 MiB);
- bounded stderr capture (default 2 MiB);
- bounded reader chunks and bounded inter-thread queue;
- truncation flags on execution results;
- process-group/session creation;
- process-tree termination on timeout and controlled streaming stop;
- the legacy ExternalToolRunner delegates to the canonical ToolRunner and can
  no longer bypass the runtime security policy.

## Approved CLI inventory

The central inventory currently includes:

amass, aquatone, assetfinder, cloudenum, dnsx, feroxbuster, ffuf, gau, ghunt,
gitdorker, gitleaks, hakrawler, holehe, httpx, katana, maigret, naabu, nikto,
nmap, nuclei, phoneinfoga, s3scanner, secretfinder, sherlock, socialscan,
spiderfoot, sslyze, subfinder, subjs, testssl, theHarvester, trufflehog,
user-scanner/user_scanner, wappalyzer, waybackurls and whatweb.

A new third-party CLI connector must update this inventory before ToolRunner
will execute it.

## Result semantics

Policy rejection:
- success = false
- return_code = -4
- blocked_by_policy = true

Timeout:
- success = false
- return_code = -1
- partial captured output is preserved
- process tree is terminated

Controlled stdout line limit:
- success = true
- return_code = -3
- stopped_early = true

Output capture overflow:
- the subprocess continues to drain without growing application memory;
- additional captured text is discarded;
- stdout_truncated or stderr_truncated is set.

## Next R14.2 slice

R14.2c hardens untrusted files and archives:

- managed-storage path confinement;
- ZIP/TAR traversal prevention;
- decompressed-byte, file-count and nesting limits;
- archive-bomb fixtures;
- import file-size/type policy.

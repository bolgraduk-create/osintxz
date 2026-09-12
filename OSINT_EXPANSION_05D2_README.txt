OSINT Intelligence Platform
OSINT Expansion 05D2 — Archive Latency / Streaming Probe

05D result:
- discovery: working
- DNS: working
- HTTP: working
- crawl: working
- archive: failed because GAU and waybackurls exceeded 15 seconds
- no result-limit violations

This diagnostic determines whether archive tools can be safely changed from
"wait for the whole process" to "collect first N URLs and terminate".

Tests:
- GAU wayback provider
- GAU commoncrawl provider
- GAU OTX provider
- GAU URLScan provider
- GAU wayback+commoncrawl
- waybackurls

Each process is terminated after 3 unique stdout lines.
No production files are changed.

Run:

    cd C:\osintxz

    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"

    & .\.venv\Scripts\python.exe .\tools\osint_archive_latency_probe_05d2.py

Output:

    storage\cache\osint_expansion_05d2\archive_latency_probe.json

Send the console output and JSON to ChatGPT.

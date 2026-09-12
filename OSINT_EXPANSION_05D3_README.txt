OSINT Intelligence Platform
OSINT Expansion 05D3 — Archive Streaming + Fast-Provider Production Fix

05D2 live findings:
- GAU OTX: 3 URLs in ~0.626s.
- GAU URLScan: 2 URLs in ~1.449s.
- GAU Wayback: no output before 12s timeout.
- GAU Common Crawl: no output before 12s timeout.
- GAU Wayback+Common Crawl: no output before 15s timeout.
- waybackurls: completed with zero output for example.com.

Design:
1. Bounded/recursive GAU requests use low-latency URLScan + OTX.
2. Unbounded/manual GAU requests preserve the normal all-provider mode.
3. Wayback remains a separate Waybackurls connector.
4. The platform already has separate Common Crawl capability, so bounded GAU
   does not need to block on duplicate slow providers.
5. ToolRunner gains optional stdout_line_limit streaming early-stop.
   Existing callers are unchanged unless they explicitly set the option.
6. Managed tools/osint/config/gau.toml suppresses the missing-config warning.

Changed production files:
- app/osint/runner.py
- app/osint/connectors/gau_connector.py
- app/osint/connectors/waybackurls_connector.py

Added:
- tools/osint/config/gau.toml
- tests/test_osint_archive_streaming.py

Run targeted tests:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe -m pytest `
        .\tests\test_osint_archive_streaming.py `
        .\tests\test_osint_discovery_result_budget.py `
        .\tests\test_osint_discovery_connector_reliability.py -q

Then repeat 05D:

    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"

    & .\.venv\Scripts\python.exe .\tools\osint_http_discovery_chain_05d.py

Expected:
- GAU archive stage should become SUCCESS/PARTIAL quickly.
- No result-limit violations.
- The overall 05D chain should reach PASS even if Waybackurls itself returns
  no data or times out, because archive now has a working bounded source.

Finally:

    & .\.venv\Scripts\python.exe -m pytest -q

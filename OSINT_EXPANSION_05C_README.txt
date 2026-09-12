OSINT Intelligence Platform
OSINT Expansion 05C — HTTPX + GHunt Production Hardening

05B findings:
- Production HTTPXConnector works against https://example.com.
- But its source did not use managed tool_runtime.
- It did not explicitly honor ConnectorRequest.limit.
- It returned ProjectDiscovery JSON successfully.
- GHunt CLI was marked BROKEN because plain `ghunt --help` crashed on Windows
  cp1251 while printing an emoji in its banner.
- The production GHunt search path already had UTF-8 environment variables.

05C changes:
1. tool_runtime.py
   - adds managed tools/osint/bin/httpx.exe.

2. httpx_connector.py
   - resolves ProjectDiscovery httpx through tool_runtime.
   - uses -u / -silent / -json / -sc / -duc.
   - JSONL parsing is line-isolated.
   - deduplicates URLs.
   - honors ConnectorRequest.limit.
   - preserves partial findings on timeout.
   - records parse/duplicate/limit metadata.

3. ghunt_connector.py
   - does NOT change GHunt's query semantics.
   - adds UTF-8 CLI health-check.
   - is_available() now means "installed and runnable", not just "exists".
   - a traceback/UnicodeEncodeError returns NOT_AVAILABLE instead of entering
     automatic OSINT as a broken connector.
   - preserves the existing authenticated-session detection.
   - honors limit=0/1 semantics.

Targeted test:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe -m pytest `
        .\tests\test_osint_httpx_ghunt_runtime.py -q

Expected:
    6 passed

Then live 05B recheck:

    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"

    & .\.venv\Scripts\python.exe .\tools\osint_httpx_ghunt_contract_probe_05b.py

Expected:
- httpx status=success
- findings <= 5
- limit_honored=True
- GHunt CLI health should become READY_CLI if UTF-8 was the only problem in
  the diagnostic command. Note: the old 05B probe itself still calls GHunt
  help without UTF-8, so its GHunt health line may remain BROKEN; production
  GHunt health is validated by the new tests.

Finally:

    & .\.venv\Scripts\python.exe -m pytest -q

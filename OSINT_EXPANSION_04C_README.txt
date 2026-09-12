OSINT Intelligence Platform
OSINT Expansion 04C — Subfinder/Gau Wrapper Forensics

04B exposed two concrete anomalies:
- subfinder: 24,948 findings for example.com (implausible)
- gau: status=failed, 0 findings

04C captures only what is needed to patch those wrappers safely:
- status/errors/warnings/metadata
- finding count and unique count
- duplicate count
- domain-like and target-related counts
- bounded first/last/weird finding samples
- exact current source files for the two connectors and shared CLI/result layers

It creates:
    storage\cache\osint_expansion_04c\diagnostic.json
    storage\cache\osint_expansion_04c\osint_04c_diagnostic_bundle.zip

Run:
    cd C:\osintxz
    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"
    & .\.venv\Scripts\python.exe .\tools\osint_subfinder_gau_forensics_04c.py

Upload BOTH diagnostic.json and osint_04c_diagnostic_bundle.zip to ChatGPT.

No production code is modified by this block.

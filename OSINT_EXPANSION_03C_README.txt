OSINT Intelligence Platform
OSINT Expansion 03C — assetfinder Windows installer

Why 03B failed:
assetfinder uses an older release naming convention:
    assetfinder-windows-amd64-0.1.1.zip

This differs from the ProjectDiscovery naming convention the previous
installer expected.

03C first downloads the official v0.1.1 Windows amd64 asset directly.
If that fails and Go is installed, it falls back to the modern official
Go installation command:

    go install github.com/tomnomnom/assetfinder@v0.1.1

It does NOT reinstall:
- subfinder
- dnsx
- gau
- waybackurls
- katana

Run:
    cd C:\osintxz
    powershell -ExecutionPolicy Bypass -File .\tools\install_assetfinder_03c.ps1

Expected:
    assetfinder local execution: PASS
    READY=6 FAILED=0
    OSINT EXPANSION 03C ASSETFINDER INSTALL: PASS

Then:
    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"
    & .\.venv\Scripts\python.exe .\tools\verify_osint_discovery_runtime.py
    & .\.venv\Scripts\python.exe .\tools\osint_runtime_capability_audit.py

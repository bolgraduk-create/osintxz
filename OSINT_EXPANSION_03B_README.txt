OSINT Intelligence Platform
OSINT Expansion 03B — assetfinder prerelease fix

Cause:
tomnomnom/assetfinder's newest release is marked as a GitHub pre-release.
GitHub's /releases/latest endpoint therefore returned HTTP 404.

Fix:
This installer queries the normal releases list and selects the newest
non-draft release containing a Windows amd64 archive, including pre-releases.

It installs ONLY assetfinder and leaves the already working tools untouched:
- subfinder
- dnsx
- gau
- waybackurls
- katana

Run:

    cd C:\osintxz
    powershell -ExecutionPolicy Bypass -File .\tools\install_assetfinder_03b.ps1

Expected:

    READY=6 FAILED=0
    OSINT EXPANSION 03B ASSETFINDER FIX: PASS

Then:

    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"

    & .\.venv\Scripts\python.exe .\tools\verify_osint_discovery_runtime.py

    & .\.venv\Scripts\python.exe .\tools\osint_runtime_capability_audit.py

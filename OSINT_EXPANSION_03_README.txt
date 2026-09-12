OSINT Intelligence Platform
OSINT Expansion 03 — Discovery Runtime Pack

Installs current official Windows amd64 release binaries from GitHub for:

- subfinder
- dnsx
- gau
- waybackurls
- katana
- assetfinder

Location:
    C:\osintxz\tools\osint\bin

The installer:
- downloads from each project's official GitHub release
- does not require administrator rights
- adds tools\osint\bin to USER PATH
- adds downloaded binaries/artifacts to .gitignore
- creates tools\osint\runtime_manifest.json
- does not modify production Python code
- does not perform OSINT searches

Run:
    cd C:\osintxz
    powershell -ExecutionPolicy Bypass -File .\tools\install_osint_discovery_runtime.ps1

If PASS, update the current PowerShell process:
    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"

Verify:
    & .\.venv\Scripts\python.exe .\tools\verify_osint_discovery_runtime.py

Then rerun:
    & .\.venv\Scripts\python.exe .\tools\osint_runtime_capability_audit.py

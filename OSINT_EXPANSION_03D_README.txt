OSINT Intelligence Platform
OSINT Expansion 03D — assetfinder smoke-check fix

What happened:
assetfinder.exe installed successfully, but `assetfinder -h` writes Usage
text to stderr and returns a non-zero exit code. With PowerShell
$ErrorActionPreference = "Stop", stderr was surfaced as NativeCommandError.

03D:
- does NOT reinstall assetfinder
- uses the existing tools\osint\bin\assetfinder.exe
- captures stdout/stderr via Start-Process
- accepts the old tool's non-zero help exit code
- verifies all six discovery-runtime executables

Run:
    cd C:\osintxz
    powershell -ExecutionPolicy Bypass -File .\tools\verify_assetfinder_03d.ps1

Expected:
    assetfinder local execution: PASS
    READY=6 FAILED=0
    OSINT EXPANSION 03D ASSETFINDER SMOKE FIX: PASS

$ErrorActionPreference = "Stop"

Write-Host "OSINTXZ R14.2c Untrusted File & Archive Gate" -ForegroundColor Green

powershell -ExecutionPolicy Bypass -File tools\run_r14_2b_security_gate.ps1

if ($LASTEXITCODE -ne 0) {
    throw "R14.2b security gate failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "=== R14.2c untrusted file and archive tests ===" -ForegroundColor Cyan

python -m pytest -q tests/test_r14_2c_untrusted_file_archive_boundaries.py

if ($LASTEXITCODE -ne 0) {
    throw "R14.2c security tests failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "R14.2c SECURITY GATE: PASS" -ForegroundColor Green

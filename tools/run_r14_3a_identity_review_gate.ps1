$ErrorActionPreference = "Stop"

Write-Host "OSINTXZ R14.3a Analyst Identity Review Gate" -ForegroundColor Green

powershell -ExecutionPolicy Bypass -File tools\run_r14_2c_security_gate.ps1

if ($LASTEXITCODE -ne 0) {
    throw "R14.2c security gate failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "=== R14.3a analyst identity decision tests ===" -ForegroundColor Cyan

python -m pytest -q tests/test_r14_3a_analyst_identity_decisions.py

if ($LASTEXITCODE -ne 0) {
    throw "R14.3a identity review tests failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "R14.3a IDENTITY REVIEW GATE: PASS" -ForegroundColor Green

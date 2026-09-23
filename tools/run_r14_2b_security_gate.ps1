$ErrorActionPreference = "Stop"

Write-Host "OSINTXZ R14.2b Executable & Output Budget Gate" -ForegroundColor Green

powershell -ExecutionPolicy Bypass -File tools\run_r14_2a_security_gate.ps1

if ($LASTEXITCODE -ne 0) {
    throw "R14.2a security gate failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "=== R14.2b executable inventory and output budget tests ===" -ForegroundColor Cyan

python -m pytest -q tests/test_r14_2b_executable_output_budgets.py

if ($LASTEXITCODE -ne 0) {
    throw "R14.2b security tests failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "R14.2b SECURITY GATE: PASS" -ForegroundColor Green

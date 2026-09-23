$ErrorActionPreference = "Stop"

Write-Host "OSINTXZ R14.2a ToolRunner Security Gate" -ForegroundColor Green

powershell -ExecutionPolicy Bypass -File tools\run_r14_1_quality_gate.ps1

if ($LASTEXITCODE -ne 0) {
    throw "R14.1 baseline gate failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "=== R14.2a ToolRunner security tests ===" -ForegroundColor Cyan

python -m pytest -q tests/test_r14_2a_tool_runner_security.py

if ($LASTEXITCODE -ne 0) {
    throw "R14.2a security tests failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "R14.2a SECURITY GATE: PASS" -ForegroundColor Green

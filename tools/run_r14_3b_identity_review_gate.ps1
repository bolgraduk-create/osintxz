$ErrorActionPreference = "Stop"

Write-Host "OSINTXZ R14.3b Identity Review Workflow Gate" -ForegroundColor Green

powershell -ExecutionPolicy Bypass -File tools\run_r14_3a_identity_review_gate.ps1

if ($LASTEXITCODE -ne 0) {
    throw "R14.3a identity review gate failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "=== R14.3b identity review workflow tests ===" -ForegroundColor Cyan

python -m pytest -q tests/test_r14_3b_identity_review_workflow.py

if ($LASTEXITCODE -ne 0) {
    throw "R14.3b identity workflow tests failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "R14.3b IDENTITY REVIEW WORKFLOW GATE: PASS" -ForegroundColor Green

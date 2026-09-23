$ErrorActionPreference = "Stop"

Write-Host "OSINTXZ R14.3c Relationship Corroboration Gate" -ForegroundColor Green

powershell -ExecutionPolicy Bypass -File tools\run_r14_3b_identity_review_gate.ps1

if ($LASTEXITCODE -ne 0) {
    throw "R14.3b identity review workflow gate failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "=== R14.3c relationship corroboration tests ===" -ForegroundColor Cyan

python -m pytest -q tests/test_r14_3c_relationship_corroboration.py

if ($LASTEXITCODE -ne 0) {
    throw "R14.3c relationship corroboration tests failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "R14.3c RELATIONSHIP CORROBORATION GATE: PASS" -ForegroundColor Green

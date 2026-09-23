$ErrorActionPreference = "Stop"

Write-Host "OSINTXZ R14.3d Identity Confidence Calibration Gate" -ForegroundColor Green

powershell -ExecutionPolicy Bypass -File tools\run_r14_3c_relationship_corroboration_gate.ps1

if ($LASTEXITCODE -ne 0) {
    throw "R14.3c relationship corroboration gate failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "=== R14.3d identity confidence calibration tests ===" -ForegroundColor Cyan

python -m pytest -q tests/test_r14_3d_identity_confidence_calibration.py

if ($LASTEXITCODE -ne 0) {
    throw "R14.3d calibration tests failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "R14.3d IDENTITY CALIBRATION GATE: PASS" -ForegroundColor Green

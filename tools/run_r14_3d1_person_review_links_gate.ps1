$ErrorActionPreference = "Stop"

Write-Host "OSINTXZ R14.3d.1 Person Review Links Gate" -ForegroundColor Green

powershell -ExecutionPolicy Bypass -File tools\run_r14_3d_identity_calibration_gate.ps1

if ($LASTEXITCODE -ne 0) {
    throw "R14.3d identity calibration gate failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "=== R14.3d.1 Person review link tests ===" -ForegroundColor Cyan

python -m pytest -q tests/test_r14_3d1_person_review_links.py

if ($LASTEXITCODE -ne 0) {
    throw "R14.3d.1 person review link tests failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "R14.3d.1 PERSON REVIEW LINKS GATE: PASS" -ForegroundColor Green

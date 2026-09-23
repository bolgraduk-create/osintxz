$ErrorActionPreference = "Stop"

Write-Host "OSINTXZ R14.3e PERSON-Scoped Search Gate" -ForegroundColor Green

powershell -ExecutionPolicy Bypass -File tools\run_r14_3d1_person_review_links_gate.ps1

if ($LASTEXITCODE -ne 0) {
    throw "R14.3d.1 person review links gate failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "=== R14.3e PERSON-scoped search tests ===" -ForegroundColor Cyan

python -m pytest -q tests/test_r14_3e_person_scoped_search.py

if ($LASTEXITCODE -ne 0) {
    throw "R14.3e PERSON-scoped search tests failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "R14.3e PERSON-SCOPED SEARCH GATE: PASS" -ForegroundColor Green

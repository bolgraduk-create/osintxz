param()

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [string]$Label,
        [scriptblock]$Command
    )

    Write-Step $Label
    & $Command

    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

$RepoRoot = (Get-Location).Path

if (-not (Test-Path ".git")) {
    throw "Run this script from C:\\osintxz (repository root)."
}

$Python = ".\\.venv\\Scripts\\python.exe"
$SmokeCheck = ".\\tools\\final_import_smoke_check.py"

if (-not (Test-Path $Python)) {
    throw "Virtual environment Python was not found: $Python"
}

if (-not (Test-Path $SmokeCheck)) {
    throw "Smoke-check script was not found: $SmokeCheck"
}

Write-Host "Repository: $RepoRoot"
Write-Host "Python:     $Python"

Invoke-Checked "Python syntax / compile check" {
    & $Python -m compileall -q app tests
}

Invoke-Checked "Critical import smoke check" {
    & $Python $SmokeCheck
}

Invoke-Checked "Targeted stabilization contract tests" {
    & $Python -m pytest -q -ra --tb=short `
        tests/test_ai_factory_configuration.py `
        tests/test_bootstrap_architecture_contract.py `
        tests/test_investigation_analysis_runner.py `
        tests/test_investigation_analysis_runner_wiring.py `
        tests/test_legacy_processing_retirement.py `
        tests/test_final_stabilization_contract.py
}

Invoke-Checked "Complete pytest suite" {
    & $Python -m pytest -q -ra --tb=short
}

Invoke-Checked "Alembic heads" {
    & $Python -m alembic heads
}

Invoke-Checked "Alembic current" {
    & $Python -m alembic current
}

Write-Step "Git whitespace / patch integrity"
git --no-pager diff --check

if ($LASTEXITCODE -ne 0) {
    throw "git diff --check found whitespace errors."
}

Write-Step "Secret tracking check"
$TrackedEnv = git ls-files -- .env

if ($TrackedEnv) {
    throw ".env is still tracked by Git."
}

Write-Host ".env is not tracked: PASS"

Write-Step "Generated-artifact tracking check"

$GeneratedTracked = @(
    git ls-files |
        Select-String -Pattern '(^|/)__pycache__/|\.pyc$|\.pyo$|\.egg-info/'
)

if ($GeneratedTracked.Count -gt 0) {
    Write-Host ""
    Write-Host "Tracked generated artifacts found:" -ForegroundColor Red
    $GeneratedTracked | ForEach-Object { Write-Host $_ }
    throw "Generated artifacts are still tracked."
}

Write-Host "Generated artifacts not tracked: PASS"

Write-Step "Modern investigation wiring source check"

$ContainerSource = Get-Content .\app\core\service_container.py -Raw
$TelegramSource = Get-Content .\app\services\telegram_import_service.py -Raw

if ($ContainerSource -notmatch 'investigation_analysis_runner') {
    throw "ServiceContainer does not expose investigation_analysis_runner."
}

if ($ContainerSource -match 'self\.evidence_processing_service\s*=') {
    throw "Legacy EvidenceProcessingService is still composed in ServiceContainer."
}

if ($TelegramSource -match 'processing_service') {
    throw "TelegramImportService still contains processing_service dependency."
}

Write-Host "Modern runner active / legacy processing detached: PASS"

Write-Step "Git summary"
git --no-pager status --short

Write-Host ""
Write-Host "-- diff stat --"
git --no-pager diff --stat

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "FINAL STABILIZATION CHECK: PASS" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "The Astra stabilization phase can now be closed."
Write-Host "Review git status, then create the baseline commit."

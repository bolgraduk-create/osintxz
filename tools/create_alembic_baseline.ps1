param(
    [string]$TempDatabase = "intelligence_alembic_baseline"
)

$ErrorActionPreference = "Stop"

if ($TempDatabase -notmatch '^[A-Za-z0-9_]+$') {
    throw "TempDatabase may contain only letters, digits and underscores."
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "======================================"
Write-Host "OSINTXZ ALEMBIC BASELINE GENERATOR"
Write-Host "======================================"

if (-not (Test-Path "alembic.ini")) {
    throw "alembic.ini not found in $ProjectRoot"
}

$ExistingBaseline = Get-ChildItem `
    -Path "migrations\versions" `
    -Filter "*.py" `
    -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -ne "20260830_0000_enable_vector_extension.py"
    }

if ($ExistingBaseline) {
    throw (
        "migrations/versions already contains revisions after the " +
        "pgvector bootstrap. Review them before generating another baseline."
    )
}

Write-Host "Creating temporary database: $TempDatabase"

docker exec intelligence-postgres `
    psql `
    -U intelligence `
    -d postgres `
    -v ON_ERROR_STOP=1 `
    -c "DROP DATABASE IF EXISTS `"$TempDatabase`" WITH (FORCE);"

docker exec intelligence-postgres `
    psql `
    -U intelligence `
    -d postgres `
    -v ON_ERROR_STOP=1 `
    -c "CREATE DATABASE `"$TempDatabase`";"

$PreviousPostgresDb = $env:POSTGRES_DB

try {
    $env:POSTGRES_DB = $TempDatabase

    Write-Host "Applying bootstrap revision to temporary database..."
    python -m alembic upgrade head

    Write-Host "Generating full application-schema baseline..."
    python -m alembic revision `
        --autogenerate `
        -m "baseline application schema"

    Write-Host "Validating generated baseline on a clean rebuild..."

    docker exec intelligence-postgres `
        psql `
        -U intelligence `
        -d postgres `
        -v ON_ERROR_STOP=1 `
        -c "DROP DATABASE IF EXISTS `"$TempDatabase`" WITH (FORCE);"

    docker exec intelligence-postgres `
        psql `
        -U intelligence `
        -d postgres `
        -v ON_ERROR_STOP=1 `
        -c "CREATE DATABASE `"$TempDatabase`";"

    python -m alembic upgrade head
    python -m alembic current
}
finally {
    if ($null -eq $PreviousPostgresDb) {
        Remove-Item Env:POSTGRES_DB -ErrorAction SilentlyContinue
    }
    else {
        $env:POSTGRES_DB = $PreviousPostgresDb
    }

    Write-Host "Removing temporary database..."

    docker exec intelligence-postgres `
        psql `
        -U intelligence `
        -d postgres `
        -v ON_ERROR_STOP=1 `
        -c "DROP DATABASE IF EXISTS `"$TempDatabase`" WITH (FORCE);"
}

Write-Host "======================================"
Write-Host "BASELINE GENERATION COMPLETE"
Write-Host "======================================"
Write-Host ""
Write-Host "Next: review migrations/versions and run:"
Write-Host "python tools/check_schema_drift.py"

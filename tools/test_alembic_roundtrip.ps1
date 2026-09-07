param(
    [string]$TempDatabase = "intelligence_alembic_roundtrip"
)

$ErrorActionPreference = "Stop"

if ($TempDatabase -notmatch '^[A-Za-z0-9_]+$') {
    throw "TempDatabase may contain only letters, digits and underscores."
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$EnumNames = @(
    "workspace_role",
    "analysis_type",
    "artifact_type",
    "entity_type",
    "report_type",
    "search_object_type",
    "source_type",
    "source_status",
    "document_type",
    "evidence_type",
    "relationship_type",
    "timeline_event_type"
)

$EnumSqlList = ($EnumNames | ForEach-Object { "'$_'" }) -join ", "

Write-Host "======================================"
Write-Host "OSINTXZ ALEMBIC ROUNDTRIP TEST"
Write-Host "======================================"

$PreviousPostgresDb = $env:POSTGRES_DB

try {
    Write-Host "`n[1/7] Creating clean temporary database..."

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

    $env:POSTGRES_DB = $TempDatabase

    Write-Host "`n[2/7] Upgrade base -> head..."
    python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Initial alembic upgrade head failed."
    }

    Write-Host "`n[3/7] Checking schema at head..."
    python .\tools\check_schema_drift.py
    if ($LASTEXITCODE -ne 0) {
        throw "Schema drift check failed after initial upgrade."
    }

    Write-Host "`n[4/7] Downgrade head -> base..."
    python -m alembic downgrade base
    if ($LASTEXITCODE -ne 0) {
        throw "alembic downgrade base failed."
    }

    Write-Host "`n[5/7] Verifying application ENUM types were removed..."

    $EnumCheckSql = @"
SELECT typname
FROM pg_type
WHERE typname IN ($EnumSqlList)
ORDER BY typname;
"@

    $RemainingEnums = docker exec intelligence-postgres `
        psql `
        -U intelligence `
        -d $TempDatabase `
        -At `
        -v ON_ERROR_STOP=1 `
        -c $EnumCheckSql

    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL ENUM verification query failed."
    }

    if ($RemainingEnums) {
        Write-Host "Remaining ENUM types:"
        $RemainingEnums | ForEach-Object { Write-Host "  $_" }
        throw "Downgrade left application ENUM types behind."
    }

    Write-Host "ENUM cleanup: PASS"

    Write-Host "`n[6/7] Upgrade base -> head again..."
    python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Second alembic upgrade head failed."
    }

    Write-Host "`n[7/7] Final schema drift check..."
    python .\tools\check_schema_drift.py
    if ($LASTEXITCODE -ne 0) {
        throw "Final schema drift check failed."
    }

    Write-Host ""
    Write-Host "======================================"
    Write-Host "ALEMBIC ROUNDTRIP: PASS"
    Write-Host "base -> head -> base -> head succeeded"
    Write-Host "======================================"
}
finally {
    if ($null -eq $PreviousPostgresDb) {
        Remove-Item Env:POSTGRES_DB -ErrorAction SilentlyContinue
    }
    else {
        $env:POSTGRES_DB = $PreviousPostgresDb
    }

    Write-Host "`nRemoving temporary database..."

    docker exec intelligence-postgres `
        psql `
        -U intelligence `
        -d postgres `
        -v ON_ERROR_STOP=1 `
        -c "DROP DATABASE IF EXISTS `"$TempDatabase`" WITH (FORCE);"
}

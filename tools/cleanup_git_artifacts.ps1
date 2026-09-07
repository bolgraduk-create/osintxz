param(
    [switch]$KeepDiagnosticFiles
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Remove-PathSafe {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
        Write-Host "Removed: $Path"
    }
}

Write-Step "Validating repository root"

$insideRepo = git rev-parse --is-inside-work-tree 2>$null
if ($LASTEXITCODE -ne 0 -or $insideRepo.Trim() -ne "true") {
    throw "Run this script from the root of the Git repository."
}

$repoRoot = (git rev-parse --show-toplevel).Trim()
$current = (Get-Location).Path

if (
    [System.IO.Path]::GetFullPath($repoRoot).TrimEnd('\') -ne
    [System.IO.Path]::GetFullPath($current).TrimEnd('\')
) {
    throw "Run this script from repository root: $repoRoot"
}

Write-Host "Repository: $repoRoot"

Write-Step "Removing Python cache directories from disk"

Get-ChildItem -Path . -Directory -Filter "__pycache__" -Recurse -Force -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }

Write-Step "Removing generated Python bytecode from disk"

Get-ChildItem -Path . -File -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Extension -in @(".pyc", ".pyo")
    } |
    ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Force
    }

Write-Step "Removing standard local test/build caches"

@(
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "intelligence_platform.egg-info"
) | ForEach-Object {
    Remove-PathSafe $_
}

if (-not $KeepDiagnosticFiles) {
    Write-Step "Removing temporary review and diagnostic files"

    $patterns = @(
        "review_*.diff",
        "full_project_changes.diff",
        "full_project_status.txt",
        "codex_changes.diff",
        "compatibility_test_fixes.diff",
        "before_review_*.diff",
        "before_review_*.txt",
        "pytest_*.txt",
        "status_*.txt",
        "alembic_*.txt",
        "*_usage.txt",
        "db_schema_check.txt"
    )

    foreach ($pattern in $patterns) {
        Get-ChildItem -Path . -File -Filter $pattern -ErrorAction SilentlyContinue |
            ForEach-Object {
                Remove-Item -LiteralPath $_.FullName -Force
                Write-Host "Removed: $($_.Name)"
            }
    }
}
else {
    Write-Step "Keeping diagnostic files by request"
}

Write-Step "Removing generated artifacts from the Git index"

$trackedFiles = @(git ls-files)

$generatedTracked = @(
    $trackedFiles | Where-Object {
        $_ -match '(^|/)__pycache__/' -or
        $_ -match '\.py[co]$' -or
        $_ -match '(^|/)intelligence_platform\.egg-info/'
    }
)

if ($generatedTracked.Count -gt 0) {
    $batchSize = 80

    for ($i = 0; $i -lt $generatedTracked.Count; $i += $batchSize) {
        $end = [Math]::Min($i + $batchSize - 1, $generatedTracked.Count - 1)
        $batch = $generatedTracked[$i..$end]

        git rm --cached --ignore-unmatch -- $batch | Out-Null

        if ($LASTEXITCODE -ne 0) {
            throw "git rm --cached failed while removing generated artifacts."
        }
    }

    Write-Host "Untracked generated files: $($generatedTracked.Count)"
}
else {
    Write-Host "No tracked generated Python artifacts found."
}

Write-Step "Keeping .env on disk but removing it from Git tracking"

$envTracked = git ls-files --error-unmatch .env 2>$null
if ($LASTEXITCODE -eq 0) {
    git rm --cached -- .env | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to remove .env from Git tracking."
    }

    Write-Host ".env remains on disk and is now ignored by Git."
}
else {
    Write-Host ".env is already untracked."
}

Write-Step "Cleanup complete"

Write-Host ""
Write-Host "IMPORTANT:" -ForegroundColor Yellow
Write-Host "- Source code was not deleted by this script."
Write-Host "- Backup files were not deleted."
Write-Host "- .env was not deleted; only Git tracking was removed."
Write-Host "- Git will show staged deletions for previously tracked generated files."
Write-Host ""
Write-Host "Next commands:"
Write-Host "  git status --short"
Write-Host "  & .\.venv\Scripts\python.exe -m pytest -q -ra --tb=short"

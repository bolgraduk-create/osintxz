param()

$ErrorActionPreference = "Stop"

$RepoRoot = (Get-Location).Path

if (-not (Test-Path ".git")) {
    throw "Run this script from C:\osintxz."
}

Write-Host "Repository: $RepoRoot"

$IgnorePatterns = @(
    "/storage/",
    "/tools/exiftool/",
    "/tools/exiftool-*/",
    "/tools/phoneinfoga/",
    "/baseline_status.txt",
    "/git_status_after_cleanup.txt",
    "/STABILIZATION_*.txt"
)

$GitIgnorePath = ".\.gitignore"
$GitIgnore = ""

if (Test-Path $GitIgnorePath) {
    $GitIgnore = Get-Content $GitIgnorePath -Raw
}

$Added = @()

foreach ($Pattern in $IgnorePatterns) {
    if ($GitIgnore -notmatch [regex]::Escape($Pattern)) {
        Add-Content -Path $GitIgnorePath -Value $Pattern -Encoding utf8
        $GitIgnore += "`n$Pattern"
        $Added += $Pattern
    }
}

if ($Added.Count -gt 0) {
    Write-Host ""
    Write-Host "Added to .gitignore:"
    $Added | ForEach-Object { Write-Host "  $_" }
}
else {
    Write-Host ".gitignore baseline patterns already present: PASS"
}

$SuspiciousTest = ".\tests\д"

if (Test-Path -LiteralPath $SuspiciousTest) {
    $Item = Get-Item -LiteralPath $SuspiciousTest

    if ($Item.PSIsContainer) {
        throw "tests\д is a directory; refusing automatic deletion."
    }

    if ($Item.Length -ne 0) {
        throw "tests\д is not empty; refusing automatic deletion."
    }

    Remove-Item -LiteralPath $SuspiciousTest -Force
    Write-Host "Removed empty accidental file: tests\д"
}
else {
    Write-Host "Suspicious tests\д file already absent: PASS"
}

Write-Host ""
Write-Host "Local third-party binaries remain on disk but are ignored:"
foreach ($Path in @(
    ".\tools\exiftool",
    ".\tools\exiftool-13.59_64",
    ".\tools\phoneinfoga"
)) {
    if (Test-Path $Path) {
        Write-Host "  PRESENT (ignored): $Path"
    }
}

Write-Host ""
Write-Host "=== README CHECK ==="
if (Test-Path ".\README.md") {
    $Readme = Get-Item ".\README.md"
    Write-Host "README.md size: $($Readme.Length) bytes"
    Write-Host "--- README content ---"
    Get-Content ".\README.md" -Raw
    Write-Host "--- end README ---"
}
else {
    Write-Host "README.md is missing."
}

Write-Host ""
Write-Host "=== REMAINING UNTRACKED TOP-LEVEL / IMPORTANT ==="
git --no-pager status --short

Write-Host ""
Write-Host "=== GIT DIFF CHECK ==="
git --no-pager diff --check

if ($LASTEXITCODE -ne 0) {
    throw "git diff --check failed after hygiene preparation."
}

Write-Host ""
Write-Host "BASELINE GIT HYGIENE PREP: PASS"
Write-Host "Do not commit yet; review README output and status first."

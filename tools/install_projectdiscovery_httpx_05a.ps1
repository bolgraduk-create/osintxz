param()

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not (Test-Path ".git")) {
    throw "Run this script from C:\osintxz."
}

$RepoRoot = (Get-Location).Path
$ToolRoot = Join-Path $RepoRoot "tools\osint"
$BinDir = Join-Path $ToolRoot "bin"
$DownloadDir = Join-Path $ToolRoot "downloads"

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Headers = @{
    "User-Agent" = "osintxz-runtime-installer"
    "Accept" = "application/vnd.github+json"
}

$Repo = "projectdiscovery/httpx"
$ExpectedExe = "httpx.exe"

Write-Host "============================================================"
Write-Host "OSINT Expansion 05A - ProjectDiscovery httpx installer"
Write-Host "============================================================"

$Release = Invoke-RestMethod `
    -Uri "https://api.github.com/repos/$Repo/releases/latest" `
    -Headers $Headers `
    -Method Get

$Candidates = @(
    $Release.assets |
        Where-Object {
            $_.name -match '(?i)windows' -and
            $_.name -match '(?i)(amd64|x86_64)' -and
            $_.name -match '(?i)\.zip$'
        }
)

if ($Candidates.Count -eq 0) {
    throw "No Windows amd64 ZIP asset found for $Repo release $($Release.tag_name)."
}

$Asset = $Candidates |
    Sort-Object {
        if ($_.name -match '(?i)amd64') { 0 } else { 1 }
    } |
    Select-Object -First 1

Write-Host "Release: $($Release.tag_name)"
Write-Host "Asset:   $($Asset.name)"

$Archive = Join-Path $DownloadDir $Asset.name
$Extract = Join-Path $DownloadDir "extract_httpx_05a"

Invoke-WebRequest `
    -Uri $Asset.browser_download_url `
    -Headers $Headers `
    -OutFile $Archive

if (Test-Path $Extract) {
    Remove-Item $Extract -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $Extract | Out-Null

Expand-Archive `
    -LiteralPath $Archive `
    -DestinationPath $Extract `
    -Force

$Exe = Get-ChildItem `
    -Path $Extract `
    -Recurse `
    -File `
    -Filter $ExpectedExe |
    Select-Object -First 1

if (-not $Exe) {
    throw "$ExpectedExe not found in release archive."
}

$Target = Join-Path $BinDir $ExpectedExe

Copy-Item `
    -LiteralPath $Exe.FullName `
    -Destination $Target `
    -Force

if (-not (Test-Path $Target)) {
    throw "httpx installation failed."
}

Write-Host ""
Write-Host "Installed:"
Write-Host "  $Target"
Write-Host "  $((Get-Item $Target).Length) bytes"

# Fingerprint using help output. ProjectDiscovery httpx exposes distinctive
# single-dash flags not present in the Python encode/httpx CLI.
$StdOut = Join-Path $env:TEMP "osintxz_httpx_stdout.txt"
$StdErr = Join-Path $env:TEMP "osintxz_httpx_stderr.txt"

Remove-Item $StdOut, $StdErr -Force -ErrorAction SilentlyContinue

$Process = Start-Process `
    -FilePath $Target `
    -ArgumentList "-h" `
    -WorkingDirectory $RepoRoot `
    -NoNewWindow `
    -Wait `
    -PassThru `
    -RedirectStandardOutput $StdOut `
    -RedirectStandardError $StdErr

$HelpText = ""

if (Test-Path $StdOut) {
    $HelpText += Get-Content $StdOut -Raw -ErrorAction SilentlyContinue
}
if (Test-Path $StdErr) {
    $HelpText += "`n"
    $HelpText += Get-Content $StdErr -Raw -ErrorAction SilentlyContinue
}

$RequiredPatterns = @(
    '(?im)(^|\s)-u,\s*-target',
    '(?im)(^|\s)-silent',
    '(?im)(^|\s)-json',
    '(?im)(^|\s)-sc,\s*-status-code'
)

$MissingPatterns = @()

foreach ($Pattern in $RequiredPatterns) {
    if ($HelpText -notmatch $Pattern) {
        $MissingPatterns += $Pattern
    }
}

if ($MissingPatterns.Count -gt 0) {
    Write-Host ""
    Write-Host "HTTPX IDENTITY CHECK: FAIL" -ForegroundColor Red
    throw "Installed httpx does not match the ProjectDiscovery CLI fingerprint."
}

Write-Host ""
Write-Host "HTTPX IDENTITY CHECK: PASS" -ForegroundColor Green
Write-Host "ProjectDiscovery httpx: $($Release.tag_name)"

Remove-Item $StdOut, $StdErr -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "OSINT EXPANSION 05A HTTPX INSTALL: PASS" -ForegroundColor Green

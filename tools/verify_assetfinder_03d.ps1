param()

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".git")) {
    throw "Run this script from C:\osintxz."
}

$RepoRoot = (Get-Location).Path
$BinDir = Join-Path $RepoRoot "tools\osint\bin"
$Assetfinder = Join-Path $BinDir "assetfinder.exe"

Write-Host "============================================================"
Write-Host "OSINT Expansion 03D - assetfinder smoke-check fix"
Write-Host "============================================================"

if (-not (Test-Path $Assetfinder)) {
    throw "assetfinder.exe is missing: $Assetfinder"
}

Write-Host "Using existing installation:"
Write-Host "  $Assetfinder"
Write-Host "  $((Get-Item $Assetfinder).Length) bytes"
Write-Host ""

# Old assetfinder writes its help/usage text to stderr and can return a
# non-zero exit code. PowerShell may surface stderr as NativeCommandError.
# Use Start-Process with explicit redirection so stderr is treated as data.
$StdOut = Join-Path $env:TEMP "osintxz_assetfinder_stdout.txt"
$StdErr = Join-Path $env:TEMP "osintxz_assetfinder_stderr.txt"

Remove-Item $StdOut, $StdErr -Force -ErrorAction SilentlyContinue

$Process = Start-Process `
    -FilePath $Assetfinder `
    -ArgumentList "-h" `
    -WorkingDirectory $RepoRoot `
    -NoNewWindow `
    -Wait `
    -PassThru `
    -RedirectStandardOutput $StdOut `
    -RedirectStandardError $StdErr

$OutputParts = @()

if (Test-Path $StdOut) {
    $OutputParts += Get-Content $StdOut -Raw -ErrorAction SilentlyContinue
}

if (Test-Path $StdErr) {
    $OutputParts += Get-Content $StdErr -Raw -ErrorAction SilentlyContinue
}

$SmokeText = ($OutputParts -join "`n").Trim()

Write-Host "assetfinder help output:"
if ($SmokeText) {
    ($SmokeText -split "`r?`n") |
        Select-Object -First 20 |
        ForEach-Object { Write-Host $_ }
}
else {
    Write-Host "<no output>"
}

Write-Host ""
Write-Host "Exit code: $($Process.ExitCode)"

if ($SmokeText -notmatch '(?i)usage|subs-only|assetfinder') {
    throw "assetfinder exists but its local help output was not recognized."
}

Write-Host "assetfinder local execution: PASS"

Remove-Item $StdOut, $StdErr -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "============================================================"
Write-Host "DISCOVERY RUNTIME PACK CHECK"
Write-Host "============================================================"

$Expected = @(
    "subfinder.exe",
    "dnsx.exe",
    "gau.exe",
    "waybackurls.exe",
    "katana.exe",
    "assetfinder.exe"
)

$Missing = @()

foreach ($ExeName in $Expected) {
    $Path = Join-Path $BinDir $ExeName

    if (Test-Path $Path) {
        Write-Host ("READY  {0,-20} {1,12} bytes" -f $ExeName, (Get-Item $Path).Length)
    }
    else {
        Write-Host ("FAILED {0}" -f $ExeName) -ForegroundColor Red
        $Missing += $ExeName
    }
}

Write-Host ""

if ($Missing.Count -gt 0) {
    throw "Missing runtime tools: $($Missing -join ', ')"
}

Write-Host "READY=6 FAILED=0"
Write-Host ""
Write-Host "OSINT EXPANSION 03D ASSETFINDER SMOKE FIX: PASS" -ForegroundColor Green
Write-Host ""
Write-Host "Next:"
Write-Host '$env:Path = "C:\osintxz\tools\osint\bin;$env:Path"'
Write-Host '& .\.venv\Scripts\python.exe .\tools\verify_osint_discovery_runtime.py'
Write-Host '& .\.venv\Scripts\python.exe .\tools\osint_runtime_capability_audit.py'

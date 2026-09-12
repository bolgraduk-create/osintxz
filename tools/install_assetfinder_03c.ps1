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
$ExtractDir = Join-Path $DownloadDir "extract_assetfinder_03c"

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Version = "0.1.1"
$Tag = "v$Version"
$ArchiveName = "assetfinder-windows-amd64-$Version.zip"
$ArchivePath = Join-Path $DownloadDir $ArchiveName
$DownloadUrl = "https://github.com/tomnomnom/assetfinder/releases/download/$Tag/$ArchiveName"
$Target = Join-Path $BinDir "assetfinder.exe"

Write-Host "============================================================"
Write-Host "OSINT Expansion 03C - assetfinder Windows installer"
Write-Host "============================================================"
Write-Host "Version: $Tag"
Write-Host "Asset:   $ArchiveName"
Write-Host ""

$Installed = $false
$DirectError = $null

try {
    Write-Host "Trying official GitHub release asset..."
    Invoke-WebRequest `
        -Uri $DownloadUrl `
        -Headers @{
            "User-Agent" = "osintxz-runtime-installer"
        } `
        -OutFile $ArchivePath

    if (-not (Test-Path $ArchivePath)) {
        throw "Archive was not created."
    }

    if ((Get-Item $ArchivePath).Length -lt 1024) {
        throw "Downloaded archive is unexpectedly small."
    }

    if (Test-Path $ExtractDir) {
        Remove-Item $ExtractDir -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null

    Expand-Archive `
        -LiteralPath $ArchivePath `
        -DestinationPath $ExtractDir `
        -Force

    $Exe = Get-ChildItem `
        -Path $ExtractDir `
        -Recurse `
        -File `
        -Filter "assetfinder.exe" |
        Select-Object -First 1

    if (-not $Exe) {
        throw "assetfinder.exe not found inside the official release archive."
    }

    Copy-Item `
        -LiteralPath $Exe.FullName `
        -Destination $Target `
        -Force

    $Installed = Test-Path $Target
}
catch {
    $DirectError = $_.Exception.Message
    Write-Host "Direct release install failed: $DirectError" -ForegroundColor Yellow
}

if (-not $Installed) {
    Write-Host ""
    Write-Host "Trying official Go build fallback..."

    $Go = Get-Command go -ErrorAction SilentlyContinue

    if (-not $Go) {
        throw @"
assetfinder could not be installed from the official release asset,
and Go is not installed for the fallback build.

Direct error:
$DirectError
"@
    }

    $GoBinTemp = Join-Path $DownloadDir "gobin_assetfinder"

    if (Test-Path $GoBinTemp) {
        Remove-Item $GoBinTemp -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $GoBinTemp | Out-Null

    $OldGoBin = $env:GOBIN

    try {
        $env:GOBIN = $GoBinTemp

        & $Go.Source install "github.com/tomnomnom/assetfinder@$Tag"

        if ($LASTEXITCODE -ne 0) {
            throw "go install returned exit code $LASTEXITCODE."
        }
    }
    finally {
        $env:GOBIN = $OldGoBin
    }

    $BuiltExe = Join-Path $GoBinTemp "assetfinder.exe"

    if (-not (Test-Path $BuiltExe)) {
        throw "Go build completed but assetfinder.exe was not found."
    }

    Copy-Item `
        -LiteralPath $BuiltExe `
        -Destination $Target `
        -Force

    $Installed = Test-Path $Target
}

if (-not $Installed) {
    throw "assetfinder installation did not produce $Target."
}

Write-Host ""
Write-Host "Installed: $Target"
Write-Host "Size:      $((Get-Item $Target).Length) bytes"

# Local non-network smoke check.
Write-Host ""
Write-Host "Local smoke check:"
$Smoke = & $Target -h 2>&1
$Exit = $LASTEXITCODE

$Smoke | Select-Object -First 20 | ForEach-Object {
    Write-Host $_
}

# assetfinder's old flag parser commonly returns a nonzero code for help;
# presence of the Usage output is what matters here.
$SmokeText = ($Smoke | Out-String)

if ($SmokeText -notmatch '(?i)usage|subs-only|assetfinder') {
    throw "assetfinder.exe exists but the local help output was not recognized."
}

Write-Host ""
Write-Host "assetfinder local execution: PASS"

# Update manifest without disturbing the five tools already installed.
$ManifestPath = Join-Path $ToolRoot "runtime_manifest.json"
$ExistingTools = @()

if (Test-Path $ManifestPath) {
    try {
        $ExistingManifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

        if ($ExistingManifest.tools) {
            $ExistingTools = @(
                $ExistingManifest.tools |
                    Where-Object { $_.name -ne "assetfinder" }
            )
        }
    }
    catch {
        $ExistingTools = @()
    }
}

$Record = [pscustomobject]@{
    name = "assetfinder"
    repo = "tomnomnom/assetfinder"
    release = $Tag
    executable = $Target
    install_method = if ($DirectError) { "go_fallback" } else { "official_release_asset" }
}

$Manifest = [pscustomobject]@{
    installed_at = (Get-Date).ToString("o")
    bin_dir = $BinDir
    tools = @($ExistingTools) + @($Record)
}

$Manifest |
    ConvertTo-Json -Depth 8 |
    Set-Content -Path $ManifestPath -Encoding utf8

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
Write-Host "OSINT EXPANSION 03C ASSETFINDER INSTALL: PASS" -ForegroundColor Green

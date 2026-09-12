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

$Repo = "tomnomnom/assetfinder"
$ExecutableName = "assetfinder.exe"

Write-Host "============================================================"
Write-Host "OSINT Expansion 03B - assetfinder prerelease installer"
Write-Host "============================================================"

$ReleasesUri = "https://api.github.com/repos/$Repo/releases?per_page=20"
$Releases = @(
    Invoke-RestMethod `
        -Uri $ReleasesUri `
        -Headers $Headers `
        -Method Get
)

if ($Releases.Count -eq 0) {
    throw "GitHub returned no releases for $Repo."
}

$SelectedRelease = $null
$SelectedAsset = $null

foreach ($Release in $Releases) {
    if ($Release.draft) {
        continue
    }

    $Candidates = @(
        $Release.assets |
            Where-Object {
                $_.name -match '(?i)windows' -and
                $_.name -match '(?i)(amd64|x86_64|64)' -and
                $_.name -match '(?i)\.(zip|tar\.gz|tgz)$'
            }
    )

    if ($Candidates.Count -eq 0) {
        continue
    }

    $SelectedRelease = $Release
    $SelectedAsset = $Candidates |
        Sort-Object {
            if ($_.name -match '(?i)amd64') { 0 }
            elseif ($_.name -match '(?i)x86_64') { 1 }
            else { 2 }
        } |
        Select-Object -First 1

    break
}

if (-not $SelectedRelease -or -not $SelectedAsset) {
    throw "No usable Windows amd64 asset found in the available assetfinder releases."
}

Write-Host "Release:     $($SelectedRelease.tag_name)"
Write-Host "Prerelease:  $($SelectedRelease.prerelease)"
Write-Host "Asset:       $($SelectedAsset.name)"

$ArchivePath = Join-Path $DownloadDir $SelectedAsset.name

Invoke-WebRequest `
    -Uri $SelectedAsset.browser_download_url `
    -Headers $Headers `
    -OutFile $ArchivePath

$ExtractDir = Join-Path $DownloadDir "extract_assetfinder"

if (Test-Path $ExtractDir) {
    Remove-Item $ExtractDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null

if ($ArchivePath -match '(?i)\.zip$') {
    Expand-Archive `
        -LiteralPath $ArchivePath `
        -DestinationPath $ExtractDir `
        -Force
}
elseif ($ArchivePath -match '(?i)\.(tar\.gz|tgz)$') {
    tar -xzf $ArchivePath -C $ExtractDir

    if ($LASTEXITCODE -ne 0) {
        throw "tar extraction failed."
    }
}
else {
    throw "Unsupported asset archive: $ArchivePath"
}

$Executable = Get-ChildItem `
    -Path $ExtractDir `
    -Recurse `
    -File `
    -Filter $ExecutableName |
    Select-Object -First 1

if (-not $Executable) {
    throw "$ExecutableName not found after extraction."
}

$Target = Join-Path $BinDir $ExecutableName

Copy-Item `
    -LiteralPath $Executable.FullName `
    -Destination $Target `
    -Force

if (-not (Test-Path $Target)) {
    throw "assetfinder install failed: $Target missing."
}

Write-Host "Installed:   $Target"
Write-Host "Size:        $((Get-Item $Target).Length) bytes"

# Update runtime manifest without touching already installed binaries.
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
        Write-Host "Warning: existing runtime_manifest.json could not be parsed; rebuilding manifest."
        $ExistingTools = @()
    }
}

$AssetfinderRecord = [pscustomobject]@{
    name = "assetfinder"
    repo = $Repo
    release = $SelectedRelease.tag_name
    prerelease = [bool]$SelectedRelease.prerelease
    asset = $SelectedAsset.name
    executable = $Target
}

$Manifest = [pscustomobject]@{
    installed_at = (Get-Date).ToString("o")
    bin_dir = $BinDir
    tools = @($ExistingTools) + @($AssetfinderRecord)
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

foreach ($Exe in $Expected) {
    $Path = Join-Path $BinDir $Exe

    if (Test-Path $Path) {
        Write-Host ("READY  {0,-20} {1,12} bytes" -f $Exe, (Get-Item $Path).Length)
    }
    else {
        Write-Host ("FAILED {0}" -f $Exe) -ForegroundColor Red
        $Missing += $Exe
    }
}

Write-Host ""

if ($Missing.Count -gt 0) {
    Write-Host "OSINT EXPANSION 03B: FAIL" -ForegroundColor Red
    throw "Missing runtime tools: $($Missing -join ', ')"
}

Write-Host "READY=6 FAILED=0"
Write-Host ""
Write-Host "OSINT EXPANSION 03B ASSETFINDER FIX: PASS" -ForegroundColor Green

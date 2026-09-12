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

$Tools = @(
    @{
        Name = "subfinder"
        Repo = "projectdiscovery/subfinder"
        Executable = "subfinder.exe"
    },
    @{
        Name = "dnsx"
        Repo = "projectdiscovery/dnsx"
        Executable = "dnsx.exe"
    },
    @{
        Name = "gau"
        Repo = "lc/gau"
        Executable = "gau.exe"
    },
    @{
        Name = "waybackurls"
        Repo = "tomnomnom/waybackurls"
        Executable = "waybackurls.exe"
    },
    @{
        Name = "katana"
        Repo = "projectdiscovery/katana"
        Executable = "katana.exe"
    },
    @{
        Name = "assetfinder"
        Repo = "tomnomnom/assetfinder"
        Executable = "assetfinder.exe"
    }
)

function Get-LatestRelease {
    param([string]$Repo)

    $Uri = "https://api.github.com/repos/$Repo/releases/latest"
    return Invoke-RestMethod -Uri $Uri -Headers $Headers -Method Get
}

function Select-WindowsAmd64Asset {
    param($Release)

    $Candidates = @(
        $Release.assets |
            Where-Object {
                $_.name -match '(?i)windows' -and
                $_.name -match '(?i)(amd64|x86_64|64)' -and
                $_.name -match '(?i)\.(zip|tar\.gz|tgz)$'
            }
    )

    if ($Candidates.Count -eq 0) {
        $Candidates = @(
            $Release.assets |
                Where-Object {
                    $_.name -match '(?i)windows' -and
                    $_.name -match '(?i)\.(zip|tar\.gz|tgz)$'
                }
        )
    }

    if ($Candidates.Count -eq 0) {
        return $null
    }

    return $Candidates |
        Sort-Object {
            if ($_.name -match '(?i)amd64') { 0 }
            elseif ($_.name -match '(?i)x86_64') { 1 }
            else { 2 }
        } |
        Select-Object -First 1
}

function Expand-ToolArchive {
    param(
        [string]$ArchivePath,
        [string]$Destination
    )

    if (Test-Path $Destination) {
        Remove-Item $Destination -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    if ($ArchivePath -match '(?i)\.zip$') {
        Expand-Archive -LiteralPath $ArchivePath -DestinationPath $Destination -Force
        return
    }

    if ($ArchivePath -match '(?i)\.(tar\.gz|tgz)$') {
        tar -xzf $ArchivePath -C $Destination

        if ($LASTEXITCODE -ne 0) {
            throw "tar extraction failed: $ArchivePath"
        }
        return
    }

    throw "Unsupported archive format: $ArchivePath"
}

function Install-Tool {
    param($Spec)

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Installing $($Spec.Name) from $($Spec.Repo)"
    Write-Host "============================================================"

    $Release = Get-LatestRelease -Repo $Spec.Repo
    $Asset = Select-WindowsAmd64Asset -Release $Release

    if (-not $Asset) {
        throw "No Windows amd64 release asset found for $($Spec.Repo)."
    }

    Write-Host "Release: $($Release.tag_name)"
    Write-Host "Asset:   $($Asset.name)"

    $ArchivePath = Join-Path $DownloadDir $Asset.name
    Invoke-WebRequest `
        -Uri $Asset.browser_download_url `
        -Headers $Headers `
        -OutFile $ArchivePath

    $ExtractDir = Join-Path $DownloadDir ("extract_" + $Spec.Name)
    Expand-ToolArchive -ArchivePath $ArchivePath -Destination $ExtractDir

    $Executable = Get-ChildItem `
        -Path $ExtractDir `
        -Recurse `
        -File `
        -Filter $Spec.Executable |
        Select-Object -First 1

    if (-not $Executable) {
        throw "Executable $($Spec.Executable) not found after extracting $($Asset.name)."
    }

    $Target = Join-Path $BinDir $Spec.Executable
    Copy-Item -LiteralPath $Executable.FullName -Destination $Target -Force

    if (-not (Test-Path $Target)) {
        throw "Install failed: $Target was not created."
    }

    Write-Host "Installed: $Target"

    return @{
        name = $Spec.Name
        repo = $Spec.Repo
        release = $Release.tag_name
        asset = $Asset.name
        executable = $Target
    }
}

$Installed = @()

foreach ($Spec in $Tools) {
    try {
        $Installed += Install-Tool -Spec $Spec
    }
    catch {
        Write-Host ""
        Write-Host "FAILED: $($Spec.Name)" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red

        $Installed += @{
            name = $Spec.Name
            repo = $Spec.Repo
            release = $null
            asset = $null
            executable = $null
            error = $_.Exception.Message
        }
    }
}

# Ensure project-local OSINT tools are available to future processes.
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathEntries = @()

if ($UserPath) {
    $PathEntries = @(
        $UserPath.Split(";") |
            Where-Object { $_ -and $_.Trim() }
    )
}

$NormalizedBin = [System.IO.Path]::GetFullPath($BinDir).TrimEnd("\")

$AlreadyPresent = $false
foreach ($Entry in $PathEntries) {
    try {
        $NormalizedEntry = [System.IO.Path]::GetFullPath(
            [Environment]::ExpandEnvironmentVariables($Entry)
        ).TrimEnd("\")

        if ($NormalizedEntry -ieq $NormalizedBin) {
            $AlreadyPresent = $true
            break
        }
    }
    catch {
        # Ignore malformed pre-existing PATH entries.
    }
}

if (-not $AlreadyPresent) {
    $NewUserPath = if ($UserPath) {
        "$BinDir;$UserPath"
    }
    else {
        $BinDir
    }

    [Environment]::SetEnvironmentVariable(
        "Path",
        $NewUserPath,
        "User"
    )

    Write-Host ""
    Write-Host "Added to user PATH: $BinDir"
}
else {
    Write-Host ""
    Write-Host "User PATH already contains: $BinDir"
}

# Make the tools available inside this installer process too.
if (-not (($env:Path -split ";") -contains $BinDir)) {
    $env:Path = "$BinDir;$env:Path"
}

# Ignore downloaded binaries/artifacts while keeping our scripts trackable.
$GitIgnorePath = Join-Path $RepoRoot ".gitignore"
$IgnoreLines = @(
    "/tools/osint/bin/",
    "/tools/osint/downloads/"
)

$GitIgnore = ""
if (Test-Path $GitIgnorePath) {
    $GitIgnore = Get-Content $GitIgnorePath -Raw
}

foreach ($Line in $IgnoreLines) {
    if ($GitIgnore -notmatch [regex]::Escape($Line)) {
        Add-Content -Path $GitIgnorePath -Value $Line -Encoding utf8
        $GitIgnore += "`n$Line"
        Write-Host "Added to .gitignore: $Line"
    }
}

$Manifest = @{
    installed_at = (Get-Date).ToString("o")
    bin_dir = $BinDir
    tools = $Installed
}

$ManifestPath = Join-Path $ToolRoot "runtime_manifest.json"
$Manifest |
    ConvertTo-Json -Depth 8 |
    Set-Content -Path $ManifestPath -Encoding utf8

Write-Host ""
Write-Host "============================================================"
Write-Host "LOCAL EXECUTABLE CHECK"
Write-Host "============================================================"

$ReadyCount = 0
$FailedCount = 0

foreach ($Spec in $Tools) {
    $Path = Join-Path $BinDir $Spec.Executable

    if (Test-Path $Path) {
        $Size = (Get-Item $Path).Length
        Write-Host ("READY  {0,-14} {1,12} bytes" -f $Spec.Name, $Size)
        $ReadyCount++
    }
    else {
        Write-Host ("FAILED {0}" -f $Spec.Name) -ForegroundColor Red
        $FailedCount++
    }
}

Write-Host ""
Write-Host "READY=$ReadyCount FAILED=$FailedCount"

if ($FailedCount -gt 0) {
    Write-Host ""
    Write-Host "OSINT EXPANSION 03 DISCOVERY RUNTIME PACK: PARTIAL" -ForegroundColor Yellow
    Write-Host "Send the full output back to ChatGPT; do not manually improvise installs."
    exit 2
}

Write-Host ""
Write-Host "OSINT EXPANSION 03 DISCOVERY RUNTIME PACK: PASS" -ForegroundColor Green
Write-Host ""
Write-Host "For the CURRENT PowerShell window, run:"
Write-Host '$env:Path = "C:\osintxz\tools\osint\bin;$env:Path"'
Write-Host ""
Write-Host "Then rerun the runtime capability audit."

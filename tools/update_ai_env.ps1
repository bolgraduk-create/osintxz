param()

$ErrorActionPreference = "Stop"

$EnvPath = Join-Path (Get-Location) ".env"

if (-not (Test-Path -LiteralPath $EnvPath)) {
    throw ".env was not found. Run this script from C:\osintxz."
}

$BackupPath = Join-Path (Get-Location) ".env.ai_config_backup"
Copy-Item -LiteralPath $EnvPath -Destination $BackupPath -Force

$Lines = Get-Content -LiteralPath $EnvPath

$Values = @{}

foreach ($Line in $Lines) {

    if ($Line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {

        $Key = $Matches[1]
        $Value = $Matches[2].Trim()

        $Values[$Key] = $Value
    }
}

$Provider = $Values["AI_PROVIDER"]

if ([string]::IsNullOrWhiteSpace($Provider)) {
    $Provider = "ollama"
}

$Provider = $Provider.Trim().ToLowerInvariant()

if ($Provider -notin @("ollama", "openai")) {
    Write-Warning "Unsupported existing AI_PROVIDER '$Provider'. Falling back to ollama."
    $Provider = "ollama"
}

$OllamaModel = $Values["OLLAMA_MODEL"]

if ([string]::IsNullOrWhiteSpace($OllamaModel)) {
    $OllamaModel = $Values["AI_MODEL"]
}

if ([string]::IsNullOrWhiteSpace($OllamaModel)) {
    $OllamaModel = $Values["DEFAULT_MODEL"]
}

if ([string]::IsNullOrWhiteSpace($OllamaModel)) {
    $OllamaModel = "qwen3:8b"
}

$OpenAIModel = $Values["OPENAI_MODEL"]

if ([string]::IsNullOrWhiteSpace($OpenAIModel)) {
    $OpenAIModel = "gpt-4.1-mini"
}

$KeysToReplace = @(
    "AI_PROVIDER",
    "AI_MODEL",
    "OLLAMA_MODEL",
    "OPENAI_MODEL"
)

$Filtered = @(
    $Lines | Where-Object {

        $CurrentLine = $_
        $Remove = $false

        foreach ($Key in $KeysToReplace) {

            if (
                $CurrentLine -match (
                    '^\s*' +
                    [regex]::Escape($Key) +
                    '\s*='
                )
            ) {

                $Remove = $true
                break
            }
        }

        -not $Remove
    }
)

while (
    $Filtered.Count -gt 0 -and
    [string]::IsNullOrWhiteSpace(
        $Filtered[
            $Filtered.Count - 1
        ]
    )
) {

    $Filtered = $Filtered[
        0..(
            $Filtered.Count - 2
        )
    ]
}

$NewBlock = @(
    "",
    "",
    "# ==========================================",
    "# AI PROVIDER CONFIGURATION",
    "# ==========================================",
    "",
    "# Explicit provider selection.",
    "# OPENAI_API_KEY no longer changes this automatically.",
    "AI_PROVIDER=$Provider",
    "",
    "# Provider-specific model names.",
    "OLLAMA_MODEL=$OllamaModel",
    "OPENAI_MODEL=$OpenAIModel",
    "",
    "# AI_MODEL is deprecated and intentionally removed.",
    ""
)

$Output = @(
    $Filtered
    $NewBlock
)

Set-Content `
    -LiteralPath $EnvPath `
    -Value $Output `
    -Encoding UTF8

Write-Host ""
Write-Host "AI configuration updated." -ForegroundColor Green
Write-Host "Provider:      $Provider"
Write-Host "Ollama model:  $OllamaModel"
Write-Host "OpenAI model:  $OpenAIModel"
Write-Host ""
Write-Host "Backup:"
Write-Host "  $BackupPath"
Write-Host ""
Write-Host "OPENAI_API_KEY and all unrelated .env values were preserved."

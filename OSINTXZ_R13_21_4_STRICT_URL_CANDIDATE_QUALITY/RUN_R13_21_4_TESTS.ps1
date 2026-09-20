$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python (Join-Path $PSScriptRoot "install_r13_21_4_strict_url_candidate_quality.py") $root --run-tests

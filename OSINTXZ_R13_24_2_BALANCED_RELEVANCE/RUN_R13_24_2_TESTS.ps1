$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
& $python -m pytest -q tests/test_r13_24_2_balanced_relevance.py tests/test_r13_24_1_username_recovery.py tests/test_r13_24_adaptive_relevance_connector_health.py
